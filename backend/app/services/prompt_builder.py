import json
from pathlib import Path
from string import Template

from app.llm import ChatMessage
from app.schemas import MEMORY_KIND_DESCRIPTIONS, Learner, Memory, Message

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# The free LLM tier limits tokens per minute, so only the latest part of a long conversation
# is sent: about 8,000 characters, roughly 2,000 tokens.
HISTORY_CHAR_BUDGET = 8_000
# The memory extractor reads more of the session, but still within the token limit.
TRANSCRIPT_CHAR_BUDGET = 12_000
# Keeps the tutor's prompt small even for a learner with a long history.
MEMORIES_PER_KIND = 8

LLM_ROLES = {"learner": "user", "tutor": "assistant"}


def load_prompt(name: str) -> Template:
    # Read on every use (a tiny file next to an LLM call), so edits apply without a restart:
    # `fastapi dev` only reloads when a .py file changes.
    return Template((PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8"))


def build_tutor_messages(
    learner: Learner,
    topic: str,
    memories: list[Memory],
    history: list[Message],
    new_message: str | None = None,
) -> list[ChatMessage]:
    """The tutor's input: rules and memory, an opening request, recent history, the new message."""
    system_prompt = load_prompt("tutor_system").substitute(
        learner_name=learner.name, topic=topic, learner_memory=render_memory(memories)
    )
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


def render_memory(memories: list[Memory]) -> str:
    """Active memories grouped by kind, in the order given (newest first), capped per kind."""
    if not memories:
        return "New learner: no memories yet."
    sections = []
    for kind in MEMORY_KIND_DESCRIPTIONS:
        lines = [
            f"- {memory.content}" + (" (edited by the learner)" if memory.user_edited else "")
            for memory in memories
            if memory.kind == kind
        ][:MEMORIES_PER_KIND]
        if lines:
            heading = kind.replace("_", " ").capitalize()  # "knowledge_gap" -> "Knowledge gap"
            sections.append(f"{heading}:\n" + "\n".join(lines))
    return "\n\n".join(sections)


def build_extraction_messages(
    topic: str, memories: list[Memory], history: list[Message]
) -> list[ChatMessage]:
    """The memory extractor's input: its rules, then the current memories and the transcript."""
    kinds = "\n".join(f"- {kind}: {text}" for kind, text in MEMORY_KIND_DESCRIPTIONS.items())
    current_memories = json.dumps(
        [
            {"id": m.id, "kind": m.kind, "content": m.content, "user_edited": m.user_edited}
            for m in memories
        ],
        indent=2,
    )
    transcript = "\n".join(
        f"{message.role.capitalize()}: {message.content}"
        for message in recent_history(history, TRANSCRIPT_CHAR_BUDGET)
    )
    rules = load_prompt("memory_extraction").substitute(memory_kinds=kinds)
    data = load_prompt("memory_extraction_input").substitute(
        memories=current_memories, topic=topic, transcript=transcript
    )
    return [{"role": "system", "content": rules}, {"role": "user", "content": data}]


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
