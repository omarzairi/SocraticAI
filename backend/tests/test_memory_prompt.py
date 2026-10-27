from app.schemas import Learner, Memory
from app.services.prompt_builder import MEMORIES_PER_KIND, build_tutor_messages, render_memory

LEARNER = Learner(id=1, name="Alex", created_at="2026-01-01T00:00:00Z")


def memory(memory_id: int, kind: str, content: str, user_edited: bool = False) -> Memory:
    return Memory(
        id=memory_id,
        learner_id=1,
        kind=kind,
        content=content,
        status="active",
        user_edited=user_edited,
        source_session_id=None,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


def test_a_new_learner_has_an_empty_memory_block():
    assert render_memory([]) == ""


def test_memories_are_grouped_by_kind():
    text = render_memory(
        [
            memory(1, "preference", "Likes pizza examples.", user_edited=True),
            memory(2, "misconception", "Adds the denominators."),
        ]
    )

    assert text == (
        "Misconception:\n- Adds the denominators.\n\nPreference:\n- Likes pizza examples."
    )


def test_at_most_eight_memories_per_kind_are_shown_in_the_given_order():
    many = [memory(index, "progress", f"Skill {index}.") for index in range(10)]

    lines = render_memory(many).splitlines()

    assert lines == ["Progress:"] + [f"- Skill {index}." for index in range(MEMORIES_PER_KIND)]


def test_memories_reach_the_tutors_system_prompt():
    memories = [memory(1, "misconception", "Adds the denominators.")]

    system_prompt = build_tutor_messages(LEARNER, "Fractions", memories, history=[])[0]["content"]

    assert "<learner_memory>\nMisconception:\n- Adds the denominators.\n</learner_memory>" in (
        system_prompt
    )
