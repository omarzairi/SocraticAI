"""Ending a session updates the learner's memory, all or nothing, across several sessions."""

import json

import pytest

from app.llm import LLMError

MISCONCEPTION = "The learner adds fractions by adding numerators and denominators."
GAP = "The learner doesn't know how to find a common denominator."
PROGRESS = "The learner can add fractions with unlike denominators."


def extraction(*operations: dict) -> str:
    return json.dumps({"operations": list(operations)})


def create(kind: str, content: str) -> dict:
    return {"action": "create", "kind": kind, "content": content}


@pytest.fixture
def learner(make_learner) -> dict:
    return make_learner("Alex")


@pytest.fixture
def chat(client, fake_llm):
    def send(session: dict, content: str, reply: str = "Why do you think so?") -> None:
        fake_llm.chat_replies.append(reply)
        url = f"/api/learners/{session['learner_id']}/sessions/{session['id']}/messages"
        assert client.post(url, json={"content": content}).status_code == 201

    return send


def end(client, session: dict):
    return client.post(f"/api/learners/{session['learner_id']}/sessions/{session['id']}/end")


def memories(db, learner_id: int) -> list[dict]:
    rows = db.execute(
        "SELECT id, kind, content, status, user_edited, source_session_id FROM memories "
        "WHERE learner_id = ? ORDER BY id",
        (learner_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def add_memory(db, learner_id: int, kind: str, content: str, user_edited: int = 0) -> int:
    cursor = db.execute(
        "INSERT INTO memories (learner_id, kind, content, user_edited, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, '2026-01-01T00:00Z', '2026-01-01T00:00Z')",
        (learner_id, kind, content, user_edited),
    )
    return cursor.lastrowid


def test_ending_a_session_saves_the_extracted_memories(
    client, fake_llm, learner, start_session, chat, db
):
    session = start_session(learner["id"], "Fractions")
    chat(session, "1/2 + 1/3 = 2/5")
    fake_llm.json_replies.append(
        extraction(create("misconception", MISCONCEPTION), create("knowledge_gap", GAP))
    )

    response = end(client, session)

    assert response.status_code == 200
    body = response.json()
    assert body["session"]["status"] == "ended"
    assert body["session"]["ended_at"] is not None
    assert [m["content"] for m in body["memory_update"]["created"]] == [MISCONCEPTION, GAP]
    assert [
        (m["kind"], m["content"], m["status"], m["source_session_id"])
        for m in memories(db, learner["id"])
    ] == [
        ("misconception", MISCONCEPTION, "active", session["id"]),
        ("knowledge_gap", GAP, "active", session["id"]),
    ]


def test_the_extractor_sees_the_transcript_and_the_current_memories(
    client, fake_llm, learner, start_session, chat, db
):
    add_memory(db, learner["id"], "preference", "The learner likes pizza examples.")
    session = start_session(learner["id"], "Fractions")
    chat(session, "I add the tops and the bottoms.")
    fake_llm.json_replies.append(extraction())

    end(client, session)

    [call] = [call for call in fake_llm.calls if call.json_mode]
    rules, data = call.messages[0]["content"], call.messages[1]["content"]
    assert "misconception: a specific incorrect belief" in rules
    assert '{"role": "learner", "content": "I add the tops and the bottoms."}' in data
    assert "The learner likes pizza examples." in data
    assert '"user_edited": false' in data


def test_ending_twice_returns_409_without_calling_the_llm(client, learner, start_session):
    session = start_session(learner["id"])
    assert end(client, session).status_code == 200  # no learner message: no LLM call

    response = end(client, session)

    assert response.status_code == 409


def test_a_session_without_learner_messages_ends_without_calling_the_llm(
    client, fake_llm, learner, start_session
):
    session = start_session(learner["id"])

    response = end(client, session)

    assert response.status_code == 200
    assert response.json()["memory_update"] == {"created": [], "updated": [], "archived": []}
    assert [call.json_mode for call in fake_llm.calls] == [False]  # only the opening question


@pytest.mark.parametrize(
    "failure",
    [
        "Here is what I learned about Alex!",
        '{"operations": [',
        LLMError("The AI provider's rate limit was reached. Wait a minute and try again."),
    ],
    ids=["prose", "truncated-json", "llm-error"],
)
def test_a_failed_memory_update_keeps_the_session_open_and_memory_unchanged(
    client, fake_llm, learner, start_session, chat, db, failure
):
    add_memory(db, learner["id"], "preference", "The learner likes pizza examples.")
    session = start_session(learner["id"])
    chat(session, "1/2 + 1/3 = 2/5")
    before = memories(db, learner["id"])
    fake_llm.json_replies.append(failure)

    response = end(client, session)

    assert response.status_code == 502
    assert memories(db, learner["id"]) == before
    detail = client.get(f"/api/learners/{learner['id']}/sessions/{session['id']}").json()
    assert detail["status"] == "active"

    fake_llm.json_replies.append(extraction(create("misconception", MISCONCEPTION)))
    assert end(client, session).status_code == 200  # ending again works


def test_the_extractor_never_changes_a_learner_edited_memory(
    client, fake_llm, learner, start_session, chat, db
):
    edited = add_memory(db, learner["id"], "preference", "I like money examples.", user_edited=1)
    normal = add_memory(db, learner["id"], "knowledge_gap", GAP)
    session = start_session(learner["id"])
    chat(session, "Now I get common denominators!")
    fake_llm.json_replies.append(
        extraction(
            {"action": "update", "memory_id": edited, "content": "The learner likes pizza."},
            {"action": "archive", "memory_id": edited},
            {"action": "update", "memory_id": normal, "content": "The learner is close to it."},
        )
    )

    body = end(client, session).json()

    rows = {row["id"]: row for row in memories(db, learner["id"])}
    assert rows[edited]["content"] == "I like money examples."
    assert rows[edited]["status"] == "active"
    assert rows[normal]["content"] == "The learner is close to it."
    assert [m["id"] for m in body["memory_update"]["updated"]] == [normal]
    assert body["memory_update"]["archived"] == []


def test_a_learner_edit_made_during_extraction_is_protected(
    client, fake_llm, learner, start_session, chat, db
):
    memory_id = add_memory(db, learner["id"], "knowledge_gap", GAP)
    session = start_session(learner["id"])
    chat(session, "I think I get it.")

    def learner_edits_the_memory_meanwhile(messages):
        db.execute(
            "UPDATE memories SET content = 'Edited by me.', user_edited = 1 WHERE id = ?",
            (memory_id,),
        )
        return extraction({"action": "archive", "memory_id": memory_id})

    fake_llm.json_replies.append(learner_edits_the_memory_meanwhile)

    assert end(client, session).status_code == 200
    [row] = memories(db, learner["id"])
    assert (row["content"], row["status"]) == ("Edited by me.", "active")


def test_operations_on_unknown_or_another_learners_memories_are_skipped(
    client, fake_llm, learner, make_learner, start_session, chat, db
):
    sam = make_learner("Sam")
    sams_memory = add_memory(db, sam["id"], "knowledge_gap", "Sam's gap.")
    session = start_session(learner["id"])
    chat(session, "Hello")
    fake_llm.json_replies.append(
        extraction(
            {"action": "update", "memory_id": sams_memory, "content": "Hijacked."},
            {"action": "archive", "memory_id": sams_memory},
            {"action": "archive", "memory_id": 999},
            create("progress", PROGRESS),
        )
    )

    body = end(client, session).json()

    assert memories(db, sam["id"])[0]["content"] == "Sam's gap."
    assert memories(db, sam["id"])[0]["status"] == "active"
    assert [m["content"] for m in body["memory_update"]["created"]] == [PROGRESS]
    assert body["memory_update"]["updated"] == body["memory_update"]["archived"] == []


def test_the_extractor_cannot_rewrite_an_archived_memory(
    client, fake_llm, learner, start_session, chat, db
):
    memory_id = add_memory(db, learner["id"], "misconception", MISCONCEPTION)
    db.execute("UPDATE memories SET status = 'archived' WHERE id = ?", (memory_id,))
    session = start_session(learner["id"])
    chat(session, "Hello")
    fake_llm.json_replies.append(
        extraction({"action": "update", "memory_id": memory_id, "content": "Rewritten."})
    )

    body = end(client, session).json()

    assert body["memory_update"]["updated"] == []
    assert memories(db, learner["id"])[0]["content"] == MISCONCEPTION


def test_a_duplicate_memory_is_not_created(client, fake_llm, learner, start_session, chat, db):
    add_memory(db, learner["id"], "knowledge_gap", GAP)
    session = start_session(learner["id"])
    chat(session, "Hello")
    fake_llm.json_replies.append(extraction(create("knowledge_gap", "  " + GAP.upper() + " ")))

    body = end(client, session).json()

    assert body["memory_update"]["created"] == []
    assert len(memories(db, learner["id"])) == 1


def test_a_message_arriving_during_extraction_keeps_the_session_open(
    client, fake_llm, learner, start_session, chat, db
):
    session = start_session(learner["id"])
    chat(session, "Hello")

    def another_tab_sends_a_message(messages):
        db.execute(
            "INSERT INTO messages (session_id, role, content, created_at) "
            "VALUES (?, 'learner', 'One more thing', '2026-01-01T00:00Z')",
            (session["id"],),
        )
        return extraction(create("progress", PROGRESS))

    fake_llm.json_replies.append(another_tab_sends_a_message)

    assert end(client, session).status_code == 409
    assert memories(db, learner["id"]) == []


def test_memory_evolves_across_sessions(client, fake_llm, learner, start_session, chat, db):
    first = start_session(learner["id"], "Fractions")
    chat(first, "1/2 + 1/3 = 2/5")
    fake_llm.json_replies.append(extraction(create("misconception", MISCONCEPTION)))
    misconception_id = end(client, first).json()["memory_update"]["created"][0]["id"]

    second = start_session(learner["id"], "Fractions")
    chat(second, "Oh, 1/2 + 1/3 = 3/6 + 2/6 = 5/6!")
    fake_llm.json_replies.append(
        extraction(
            {"action": "archive", "memory_id": misconception_id}, create("progress", PROGRESS)
        )
    )
    body = end(client, second).json()

    assert [m["id"] for m in body["memory_update"]["archived"]] == [misconception_id]
    assert [
        (row["content"], row["status"], row["source_session_id"])
        for row in memories(db, learner["id"])
    ] == [
        (MISCONCEPTION, "archived", second["id"]),
        (PROGRESS, "active", second["id"]),
    ]


def test_memories_personalize_later_sessions_and_archived_ones_drop_out(
    client, fake_llm, learner, start_session, chat
):
    first = start_session(learner["id"], "Fractions")
    chat(first, "1/2 + 1/3 = 2/5")
    fake_llm.json_replies.append(extraction(create("misconception", MISCONCEPTION)))
    misconception_id = end(client, first).json()["memory_update"]["created"][0]["id"]

    second = start_session(learner["id"], "Fractions")
    assert MISCONCEPTION in fake_llm.chat_calls[-1].messages[0]["content"]  # opening question
    chat(second, "1/2 + 1/3 = 5/6")
    assert MISCONCEPTION in fake_llm.chat_calls[-1].messages[0]["content"]  # every reply
    fake_llm.json_replies.append(
        extraction(
            {"action": "archive", "memory_id": misconception_id}, create("progress", PROGRESS)
        )
    )
    end(client, second)

    start_session(learner["id"], "Fractions")
    system_prompt = fake_llm.chat_calls[-1].messages[0]["content"]
    assert PROGRESS in system_prompt
    assert MISCONCEPTION not in system_prompt


def test_ending_an_unknown_session_returns_404(client, learner):
    assert client.post(f"/api/learners/{learner['id']}/sessions/999/end").status_code == 404


@pytest.mark.parametrize("bad_id", ["abc", "0", str(2**63)])
def test_ending_with_an_invalid_id_returns_422(client, learner, bad_id):
    assert client.post(f"/api/learners/{learner['id']}/sessions/{bad_id}/end").status_code == 422
