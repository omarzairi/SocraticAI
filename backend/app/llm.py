import json
import logging
from typing import Literal, Protocol, TypedDict

import httpx2
import openai
from openai.types.chat import ChatCompletion

from app.config import Settings

logger = logging.getLogger(__name__)

# Room for a short tutor reply (or a memory update) plus the model's hidden reasoning.
MAX_COMPLETION_TOKENS = 1024
# Give up quickly when the provider can't be reached; the read timeout comes from settings.
CONNECT_TIMEOUT_SECONDS = 5.0
UNREADABLE_REPLY = "The AI provider sent an unreadable reply. Please try again."


class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMError(Exception):
    """The LLM could not produce a usable reply. The message is safe to show to the learner."""


class LLMClient(Protocol):
    def complete(
        self, messages: list[ChatMessage], *, temperature: float, json_mode: bool = False
    ) -> str:
        """Return the reply text, or raise LLMError."""
        ...


class OpenAICompatibleClient:
    """LLMClient for any OpenAI-compatible chat API (Groq by default)."""

    def __init__(self, settings: Settings, http_client: httpx2.Client | None = None) -> None:
        self._settings = settings
        self._client = openai.OpenAI(
            # The SDK refuses to start without a key, but the server should still start (history
            # and memories stay browsable). The placeholder is never sent: complete() checks first.
            api_key=settings.llm_api_key.get_secret_value() or "not-configured",
            base_url=settings.llm_base_url,
            timeout=httpx2.Timeout(settings.llm_timeout_seconds, connect=CONNECT_TIMEOUT_SECONDS),
            # The SDK retries timeouts, 429s and 5xx with backoff, honouring Retry-After.
            max_retries=settings.llm_max_retries,
            http_client=http_client,
        )

    def complete(
        self, messages: list[ChatMessage], *, temperature: float, json_mode: bool = False
    ) -> str:
        if not self._settings.llm_api_key.get_secret_value():
            raise LLMError(
                "The tutor isn't configured: copy backend/.env.example to backend/.env, "
                "set LLM_API_KEY and restart the server."
            )

        options = {}
        if json_mode:
            options["response_format"] = {"type": "json_object"}
        if self._settings.llm_reasoning_effort:
            options["reasoning_effort"] = self._settings.llm_reasoning_effort

        try:
            response = self._client.chat.completions.create(
                model=self._settings.llm_model,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=MAX_COMPLETION_TOKENS,
                **options,
            )
        except openai.AuthenticationError as exc:
            logger.error("The LLM provider rejected the API key: %s", exc)
            raise LLMError(
                "The AI provider rejected the API key. Check LLM_API_KEY in backend/.env."
            ) from exc
        except openai.NotFoundError as exc:
            logger.error("The LLM provider doesn't offer the model or URL: %s", exc)
            raise LLMError(
                "The AI provider doesn't offer the configured model. "
                "Check LLM_MODEL and LLM_BASE_URL in backend/.env."
            ) from exc
        except openai.RateLimitError as exc:
            logger.warning("LLM rate limit reached: %s", exc)
            raise LLMError(
                "The AI provider's rate limit was reached. Wait a minute and try again "
                "(the free tier also has a daily limit)."
            ) from exc
        except openai.APITimeoutError as exc:
            logger.warning("LLM request timed out: %r", exc.__cause__)
            raise LLMError("The AI provider took too long to answer. Please try again.") from exc
        except openai.APIConnectionError as exc:
            logger.warning("Could not reach the LLM provider: %r", exc.__cause__)
            raise LLMError(
                "Couldn't reach the AI provider. Check your connection and LLM_BASE_URL."
            ) from exc
        except openai.APIError as exc:
            logger.error("The LLM provider returned an error: %s", exc)
            raise LLMError("The AI provider returned an error. Please try again.") from exc
        except json.JSONDecodeError as exc:
            logger.error("The LLM provider sent invalid JSON: %s", exc)
            raise LLMError(UNREADABLE_REPLY) from exc
        return _reply_text(response)


def _reply_text(response: object) -> str:
    """The reply's text, or LLMError when it is missing, unreadable or cut off."""
    if not isinstance(response, ChatCompletion) or not response.choices:
        # e.g. a proxy or captive portal answered with HTML instead of a chat completion.
        logger.error("Unexpected LLM response: %.200r", response)
        raise LLMError(UNREADABLE_REPLY)
    choice = response.choices[0]
    if choice.finish_reason in ("length", "content_filter"):
        # Saving a cut-off reply would show the learner half a sentence.
        logger.warning(
            "The LLM reply was cut off (finish_reason=%s, usage=%s)",
            choice.finish_reason,
            response.usage,
        )
        raise LLMError("The tutor's reply was cut off. Please try again.")
    content = choice.message.content if choice.message is not None else None
    if not isinstance(content, str) or not content.strip():
        logger.warning("The LLM returned an empty reply (finish_reason=%s)", choice.finish_reason)
        raise LLMError("The tutor returned an empty reply. Please try again.")
    return content.strip()
