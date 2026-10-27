import json

import httpx2
import pytest

from app.config import Settings
from app.llm import LLMError, OpenAICompatibleClient

API_KEY = "sk-test-secret-key"
MESSAGES = [{"role": "user", "content": "What is a fraction?"}]


def completion(content: str | None, finish_reason: str = "stop") -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "openai/gpt-oss-120b",
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                # gpt-oss also returns its reasoning in a separate field, which must be ignored.
                "message": {"role": "assistant", "content": content, "reasoning": "hidden"},
            }
        ],
    }


def make_client(handler, **settings_overrides) -> OpenAICompatibleClient:
    values = {"llm_api_key": API_KEY, "llm_base_url": "http://llm.invalid/v1", "llm_max_retries": 0}
    settings = Settings(_env_file=None, **(values | settings_overrides))
    http_client = httpx2.Client(transport=httpx2.MockTransport(handler))
    return OpenAICompatibleClient(settings, http_client=http_client)


def test_returns_the_reply_text_without_surrounding_whitespace():
    client = make_client(lambda request: httpx2.Response(200, json=completion("  Why?  ")))

    assert client.complete(MESSAGES, temperature=0.7) == "Why?"


def test_sends_the_model_messages_and_options():
    sent = {}

    def handler(request):
        sent["url"] = str(request.url)
        sent["body"] = json.loads(request.content)
        return httpx2.Response(200, json=completion("Why?"))

    make_client(handler).complete(MESSAGES, temperature=0.7)

    assert sent["url"] == "http://llm.invalid/v1/chat/completions"
    assert sent["body"]["model"] == "openai/gpt-oss-120b"
    assert sent["body"]["messages"] == MESSAGES
    assert sent["body"]["temperature"] == 0.7
    assert sent["body"]["reasoning_effort"] == "low"
    assert sent["body"]["max_completion_tokens"] == 1024
    assert "response_format" not in sent["body"]


def test_json_mode_asks_for_a_json_object():
    sent = {}

    def handler(request):
        sent.update(json.loads(request.content))
        return httpx2.Response(200, json=completion('{"operations": []}'))

    make_client(handler).complete(MESSAGES, temperature=0.2, json_mode=True)

    assert sent["response_format"] == {"type": "json_object"}


def test_reasoning_effort_can_be_turned_off():
    sent = {}

    def handler(request):
        sent.update(json.loads(request.content))
        return httpx2.Response(200, json=completion("Why?"))

    make_client(handler, llm_reasoning_effort="").complete(MESSAGES, temperature=0.7)

    assert "reasoning_effort" not in sent


@pytest.mark.parametrize(
    "status, expected",
    [
        (401, "rejected the API key"),
        (429, "rate limit"),
        (400, "returned an error"),
        (500, "returned an error"),
    ],
)
def test_provider_errors_become_llm_errors(status, expected):
    client = make_client(
        lambda request: httpx2.Response(status, json={"error": {"message": f"HTTP {status}"}})
    )

    with pytest.raises(LLMError, match=expected):
        client.complete(MESSAGES, temperature=0.7)


def test_timeout_becomes_llm_error():
    def handler(request):
        raise httpx2.ReadTimeout("timed out", request=request)

    with pytest.raises(LLMError, match="took too long"):
        make_client(handler).complete(MESSAGES, temperature=0.7)


def test_connection_failure_becomes_llm_error():
    def handler(request):
        raise httpx2.ConnectError("connection refused", request=request)

    with pytest.raises(LLMError, match="Couldn't reach"):
        make_client(handler).complete(MESSAGES, temperature=0.7)


@pytest.mark.parametrize("content", [None, "", "   "])
def test_empty_reply_becomes_llm_error(content):
    client = make_client(
        lambda request: httpx2.Response(200, json=completion(content, finish_reason="length"))
    )

    with pytest.raises(LLMError, match="empty reply"):
        client.complete(MESSAGES, temperature=0.7)


def test_missing_api_key_fails_without_calling_the_provider():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx2.Response(200, json=completion("Why?"))

    with pytest.raises(LLMError, match="LLM_API_KEY"):
        make_client(handler, llm_api_key="").complete(MESSAGES, temperature=0.7)
    assert calls == []


def test_the_api_key_never_appears_in_errors_or_settings():
    client = make_client(
        lambda request: httpx2.Response(401, json={"error": {"message": "Invalid API Key"}})
    )

    with pytest.raises(LLMError) as error:
        client.complete(MESSAGES, temperature=0.7)

    assert API_KEY not in str(error.value)
    assert API_KEY not in repr(client._settings)
