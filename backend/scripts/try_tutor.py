"""Send a few tutoring scenarios to the REAL LLM so a person can read and judge the replies.

Run from backend/ (needs LLM_API_KEY in backend/.env):
    uv run python -m scripts.try_tutor

This is not part of the test suite: real model output varies, so it can't be asserted on.
"""

from datetime import UTC, datetime

from app.config import Settings
from app.llm import LLMError, OpenAICompatibleClient
from app.schemas import Learner, Message
from app.services.prompt_builder import build_tutor_messages
from app.services.session_service import TUTOR_TEMPERATURE

LEARNER = Learner(id=1, name="Alex", created_at=datetime.now(UTC))

# name -> (topic, conversation so far as (role, text) pairs, the learner's new message)
SCENARIOS = {
    "opening question": ("Fractions", [], None),
    "learner states a misconception": (
        "Fractions",
        [("tutor", "Hi Alex! What do you already know about adding fractions?")],
        "1/2 + 1/3 = 2/5, you just add the tops and the bottoms.",
    ),
    "learner demands the answer": (
        "Photosynthesis",
        [("tutor", "Hi Alex! What do you think a plant needs to make its own food?")],
        "I don't know. Just tell me the answer.",
    ),
    "learner demands the answer a second time": (
        "Photosynthesis",
        [
            ("tutor", "Hi Alex! What do you think a plant needs to make its own food?"),
            ("learner", "I don't know. Just tell me the answer."),
            (
                "tutor",
                "I get it, but working it out makes it stick. Hint: think about what a plant "
                "takes in through its leaves. What could that be?",
            ),
        ],
        "I said just tell me the answer!",
    ),
}


def to_messages(history: list[tuple[str, str]]) -> list[Message]:
    now = datetime.now(UTC)
    return [
        Message(id=index, session_id=1, role=role, content=text, created_at=now)
        for index, (role, text) in enumerate(history, start=1)
    ]


def main() -> None:
    llm = OpenAICompatibleClient(Settings())
    for name, (topic, history, new_message) in SCENARIOS.items():
        messages = build_tutor_messages(LEARNER, topic, to_messages(history), new_message)
        try:
            reply = llm.complete(messages, temperature=TUTOR_TEMPERATURE)
        except LLMError as error:
            reply = f"[LLM error] {error}"
        print(f"=== {name} ({topic}) ===")
        if new_message:
            print(f"Learner: {new_message}")
        print(f"Tutor:   {reply}\n")


if __name__ == "__main__":
    main()
