"""Inspect, correct and remove memories; changes apply from the learner's next message."""

import json

import pytest

NOW = "2026-01-01T00:00:00Z"
# 2**63 is one past SQLite's largest integer.
INVALID_IDS = ["abc", "0", "-1", str(2**63)]


@pytest.fixture
def learner(make_learner) -> dict:
    return make_learner("Alex")


@pytest.fixture
def add_memory(db):
    def add(learner_id: int, content: str, kind: str = "knowledge_gap", status="active") -> int:
        return db.execute(
            "INSERT INTO memories (learner_id, kind, content, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (learner_id, kind, content, status, NOW, NOW),
        ).lastrowid

    return add


def memories_url(learner: dict, memory_id: int | str | None = None) -> str:
    base = f"/api/learners/{learner['id']}/memories"
    return base if memory_id is None else f"{base}/{memory_id}"


def test_list_memories_includes_archived_ones(client, learner, add_memory):
    gap = add_memory(learner["id"], "A gap.")
    old = add_memory(learner["id"], "An old misconception.", "misconception", "archived")

    memories = client.get(memories_url(learner)).json()

    assert [(m["id"], m["status"], m["user_edited"]) for m in memories] == [
        (gap, "active", False),
        (old, "archived", False),
    ]


def test_list_memories_of_unknown_learner_returns_404(client):
    assert client.get("/api/learners/999/memories").status_code == 404


def test_editing_a_memory_corrects_it_and_locks_it(client, learner, add_memory):
    memory_id = add_memory(learner["id"], "Struggles with fractions.")

    response = client.patch(memories_url(learner, memory_id), json={"content": "  Fine now.  "})

    assert response.status_code == 200
    memory = response.json()
    assert (memory["content"], memory["user_edited"]) == ("Fine now.", True)
    assert memory["updated_at"] != NOW


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"content": None},
        {"content": "   "},
        {"content": "two\nlines"},
        {"content": "x" * 301},
        {"content": "ok", "kind": "progress"},
    ],
)
def test_invalid_edit_returns_422(client, learner, add_memory, payload):
    memory_id = add_memory(learner["id"], "A gap.")

    assert client.patch(memories_url(learner, memory_id), json=payload).status_code == 422


def test_deleting_a_memory_removes_it(client, learner, add_memory):
    memory_id = add_memory(learner["id"], "Wrong about me.")

    assert client.delete(memories_url(learner, memory_id)).status_code == 204
    assert client.get(memories_url(learner)).json() == []
    assert client.delete(memories_url(learner, memory_id)).status_code == 404


def test_another_learners_memory_cannot_be_edited_or_deleted(
    client, learner, make_learner, add_memory
):
    sam = make_learner("Sam")
    sams_memory = add_memory(sam["id"], "Sam's gap.")

    assert (
        client.patch(memories_url(learner, sams_memory), json={"content": "x"}).status_code == 404
    )
    assert client.delete(memories_url(learner, sams_memory)).status_code == 404
    assert client.get(memories_url(sam)).json()[0]["content"] == "Sam's gap."


@pytest.mark.parametrize("bad_id", INVALID_IDS)
def test_invalid_memory_id_returns_422(client, learner, bad_id):
    assert client.patch(memories_url(learner, bad_id), json={"content": "x"}).status_code == 422
    assert client.delete(memories_url(learner, bad_id)).status_code == 422


def test_edits_and_deletes_apply_from_the_next_message(
    client, fake_llm, learner, add_memory, start_session
):
    session = start_session(learner["id"])
    edited = add_memory(learner["id"], "Prefers pizza examples.", "preference")
    deleted = add_memory(learner["id"], "Thinks 1/2 + 1/3 = 2/5.", "misconception")
    client.patch(memories_url(learner, edited), json={"content": "Prefers money examples."})
    client.delete(memories_url(learner, deleted))
    fake_llm.chat_replies.append("Let's use money: what is half of a euro?")

    client.post(
        f"/api/learners/{learner['id']}/sessions/{session['id']}/messages", json={"content": "Hi"}
    )

    system_prompt = fake_llm.chat_calls[-1].messages[0]["content"]
    assert "Prefers money examples." in system_prompt
    assert "pizza" not in system_prompt
    assert "2/5" not in system_prompt


def test_a_memory_edited_through_the_api_survives_the_extractor(
    client, fake_llm, learner, add_memory, start_session
):
    memory_id = add_memory(learner["id"], "Struggles with fractions.")
    client.patch(memories_url(learner, memory_id), json={"content": "I'm fine with fractions."})
    session = start_session(learner["id"])
    base = f"/api/learners/{learner['id']}/sessions/{session['id']}"
    fake_llm.chat_replies.append("Why?")
    client.post(f"{base}/messages", json={"content": "I still find fractions hard."})
    fake_llm.json_replies.append(
        json.dumps(
            {"operations": [{"action": "update", "memory_id": memory_id, "content": "Hard."}]}
        )
    )

    assert client.post(f"{base}/end").status_code == 200

    [memory] = client.get(memories_url(learner)).json()
    assert (memory["content"], memory["status"]) == ("I'm fine with fractions.", "active")
