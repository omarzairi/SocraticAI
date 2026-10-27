import logging
from typing import Literal, Protocol, TypedDict

import httpx2
import openai

from app.config import Settings

logger = logging.getLogger(__name__)

# Room for a short tutor reply (or a memory update) plus the model's hidden reasoning.
MAX_COMPLETION_TOKENS = 1024


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
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,  # the SDK retries 429/5xx/timeouts with backoff
            http_client=http_client,
        )

    def complete(
        self, messages: list[ChatMessage], *, temperature: float, json_mode: bool = False
    ) -> str:
        if not self._settings.llm_api_key.get_secret_value():
            raise LLMError("The tutor isn't configured yet: set LLM_API_KEY in backend/.env.")

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
        except openai.RateLimitError as exc:
            logger.warning("LLM rate limit reached: %s", exc)
            raise LLMError(
                "The AI provider's rate limit was reached. Wait a minute and try again."
            ) from exc
        except openai.APITimeoutError as exc:
            logger.warning("LLM request timed out: %s", exc)
            raise LLMError("The AI provider took too long to answer. Please try again.") from exc
        except openai.APIConnectionError as exc:
            logger.warning("Could not reach the LLM provider: %s", exc)
            raise LLMError(
                "Couldn't reach the AI provider. Check your connection and try again."
            ) from exc
        except openai.APIError as exc:
            logger.error("The LLM provider returned an error: %s", exc)
            raise LLMError("The AI provider returned an error. Please try again.") from exc

        choice = response.choices[0] if response.choices else None
        content = (choice.message.content or "").strip() if choice else ""
        if not content:
            # e.g. the model spent its whole token budget reasoning (finish_reason "length").
            logger.warning(
                "The LLM returned an empty reply (finish_reason=%s)",
                choice.finish_reason if choice else None,
            )
            raise LLMError("The tutor returned an empty reply. Please try again.")
        return content
