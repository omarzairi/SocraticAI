from itertools import pairwise
from string import Template

import pytest

from app.schemas import Learner, Message
from app.services.prompt_builder import (
    HISTORY_CHAR_BUDGET,
    PROMPTS_DIR,
    build_tutor_messages,
    recent_history,
)

LEARNER = Learner(id=1, name="Alex", created_at="2026-01-01T00:00:00Z")


def message(message_id: int, role: str, content: str) -> Message:
    return Message(
        id=message_id, session_id=1, role=role, content=content, created_at="2026-01-01T00:00:00Z"
    )


def conversation(exchanges: int, length: int) -> list[Message]:
    """A stored conversation: the tutor's opening question, then learner/tutor pairs."""
    history = [message(1, "tutor", "t" * length)]
    for _ in range(exchanges):
        history.append(message(len(history) + 1, "learner", "l" * length))
        history.append(message(len(history) + 1, "tutor", "t" * length))
    return history


@pytest.mark.parametrize("path", sorted(PROMPTS_DIR.glob("*.md")), ids=lambda path: path.name)
def test_every_prompt_template_is_valid(path):
    # A stray "$" (for example "$5") would make substitute() fail at runtime.
    assert Template(path.read_text(encoding="utf-8")).is_valid()


def test_system_prompt_names_the_learner_and_the_topic():
    system = build_tutor_messages(LEARNER, "Fractions", history=[])[0]

    assert system["role"] == "system"
    assert "Alex" in system["content"]
    assert "Fractions" in system["content"]


def test_a_new_session_starts_with_a_learner_request_for_the_topic():
    messages = build_tutor_messages(LEARNER, "Fractions", history=[])

    assert len(messages) == 2
    assert messages[1]["role"] == "user"
    assert "Fractions" in messages[1]["content"]


def test_history_uses_llm_roles_and_the_new_message_comes_last():
    history = [
        message(1, "tutor", "What do you already know?"),
        message(2, "learner", "Not much."),
        message(3, "tutor", "What is half of 4?"),
    ]

    messages = build_tutor_messages(LEARNER, "Fractions", history, new_message="2")

    assert [(m["role"], m["content"]) for m in messages[2:]] == [
        ("assistant", "What do you already know?"),
        ("user", "Not much."),
        ("assistant", "What is half of 4?"),
        ("user", "2"),
    ]


def test_short_history_is_kept_whole():
    history = conversation(exchanges=3, length=10)

    assert recent_history(history, char_budget=1_000) == history


@pytest.mark.parametrize("exchanges", range(8))
def test_trimmed_history_is_the_newest_part_and_starts_with_the_tutor(exchanges):
    history = conversation(exchanges, length=10)

    kept = recent_history(history, char_budget=45)

    assert sum(len(m.content) for m in kept) <= 45
    assert kept == history[len(history) - len(kept) :]
    assert kept[0].role == "tutor"


def test_a_long_conversation_is_trimmed_before_it_is_sent():
    history = conversation(exchanges=10, length=HISTORY_CHAR_BUDGET // 4)

    sent = build_tutor_messages(LEARNER, "Fractions", history, new_message="Next")[2:-1]

    assert sum(len(m["content"]) for m in sent) <= HISTORY_CHAR_BUDGET
    assert sent[-1]["content"] == history[-1].content


@pytest.mark.parametrize("exchanges", range(8))
def test_roles_alternate_even_when_history_is_trimmed(exchanges):
    # 1,000-character messages: the 8,000 budget keeps a window of several messages.
    history = conversation(exchanges, length=1_000)

    messages = build_tutor_messages(LEARNER, "Fractions", history, new_message="Next")

    roles = [m["role"] for m in messages[1:]]
    assert all(current != following for current, following in pairwise(roles))
