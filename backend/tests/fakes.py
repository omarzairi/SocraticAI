from collections.abc import Callable
from dataclasses import dataclass

from app.llm import ChatMessage

# The opening question the start_session fixture scripts for every new session.
OPENING_QUESTION = "Hi! What do you already know about this topic?"

# A scripted reply: the text to return, an exception to raise, or a function that runs while
# the "LLM is thinking" (to simulate a concurrent request) and returns the text.
Reply = str | Exception | Callable[[list[ChatMessage]], str]


@dataclass
class FakeCall:
    messages: list[ChatMessage]
    temperature: float
    json_mode: bool


class FakeLLMClient:
    """Stands in for the real LLM in tests.

    Tutor replies and JSON replies (memory updates) have separate queues, so a test scripts
    each kind without caring how they interleave. An unscripted call fails the test loudly.
    """

    def __init__(self) -> None:
        self.chat_replies: list[Reply] = []
        self.json_replies: list[Reply] = []
        self.calls: list[FakeCall] = []

    def complete(
        self, messages: list[ChatMessage], *, temperature: float, json_mode: bool = False
    ) -> str:
        self.calls.append(FakeCall(list(messages), temperature, json_mode))
        queue = self.json_replies if json_mode else self.chat_replies
        if not queue:
            kind = "JSON" if json_mode else "chat"
            raise AssertionError(f"FakeLLMClient received an unscripted {kind} call")
        reply = queue.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if callable(reply):
            return reply(messages)
        return reply

    @property
    def chat_calls(self) -> list[FakeCall]:
        return [call for call in self.calls if not call.json_mode]
