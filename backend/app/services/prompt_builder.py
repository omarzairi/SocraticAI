from pathlib import Path
from string import Template

from app.llm import ChatMessage
from app.schemas import Learner, Message

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# The free LLM tier limits tokens per minute, so only the latest part of a long conversation
# is sent: about 8,000 characters, roughly 2,000 tokens.
HISTORY_CHAR_BUDGET = 8_000

LLM_ROLES = {"learner": "user", "tutor": "assistant"}


def load_prompt(name: str) -> Template:
    # Read on every use (a tiny file next to an LLM call), so edits apply without a restart:
    # `fastapi dev` only reloads when a .py file changes.
    return Template((PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8"))


def build_tutor_messages(
    learner: Learner, topic: str, history: list[Message], new_message: str | None = None
) -> list[ChatMessage]:
    """The tutor's input: its rules, an opening request, recent history and the new message."""
    system_prompt = load_prompt("tutor_system").substitute(learner_name=learner.name, topic=topic)
    messages: list[ChatMessage] = [
        {"role": "system", "content": system_prompt},
        # Not stored: it makes the tutor open the session, and keeps user/assistant alternating.
        {"role": "user", "content": load_prompt("session_start").substitute(topic=topic).strip()},
    ]
    for message in recent_history(history, HISTORY_CHAR_BUDGET):
        messages.append({"role": LLM_ROLES[message.role], "content": message.content})
    if new_message is not None:
        messages.append({"role": "user", "content": new_message})
    return messages


def recent_history(history: list[Message], char_budget: int) -> list[Message]:
    """The newest messages that fit in char_budget, starting with a tutor message.

    The window follows the synthetic learner request, so it must start with the tutor:
    two learner messages in a row would break the user/assistant alternation.
    """
    kept: list[Message] = []
    used = 0
    for message in reversed(history):
        used += len(message.content)
        if used > char_budget:
            break
        kept.append(message)
    kept.reverse()
    while kept and kept[0].role != "tutor":
        kept.pop(0)
    return kept
