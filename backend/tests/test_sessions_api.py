import sqlite3

import pytest

from app.llm import LLMError

# 2**63 is one past SQLite's largest integer.
INVALID_IDS = ["abc", "0", "-1", str(2**63)]


def test_start_session_opens_with_the_tutors_question(client, fake_llm, make_learner):
    learner = make_learner("Alex")
    fake_llm.chat_replies.append("Hi Alex! What do you already know about fractions?")

    response = client.post(
        f"/api/learners/{learner['id']}/sessions", json={"topic": "  Fractions  "}
    )

    assert response.status_code == 201
    session = response.json()
    assert session["topic"] == "Fractions"
    assert session["status"] == "active"
    assert session["learner_id"] == learner["id"]
    assert session["ended_at"] is None
    assert [(m["role"], m["content"]) for m in session["messages"]] == [
        ("tutor", "Hi Alex! What do you already know about fractions?")
    ]


def test_the_opening_question_is_asked_with_the_tutor_prompt(client, fake_llm, start_session):
    learner = client.post("/api/learners", json={"name": "Alex"}).json()

    start_session(learner["id"], "Fractions")

    [call] = fake_llm.calls
    assert not call.json_mode
    assert [message["role"] for message in call.messages] == ["system", "user"]
    assert "Alex" in call.messages[0]["content"]
    assert "Fractions" in call.messages[0]["content"]


def test_llm_failure_on_start_saves_nothing(client, fake_llm, make_learner):
    learner = make_learner()
    fake_llm.chat_replies.append(LLMError("The AI provider took too long to answer."))

    response = client.post(f"/api/learners/{learner['id']}/sessions", json={"topic": "Fractions"})

    assert response.status_code == 502
    assert response.json() == {"detail": "The AI provider took too long to answer."}
    assert client.get(f"/api/learners/{learner['id']}/sessions").json() == []


def test_a_failed_save_on_start_leaves_no_session(client, fake_llm, make_learner, db):
    learner = make_learner()
    db.execute(
        "CREATE TRIGGER fail_messages BEFORE INSERT ON messages "
        "BEGIN SELECT RAISE(ABORT, 'simulated write failure'); END"
    )
    fake_llm.chat_replies.append("Hi! What do you know about fractions?")

    with pytest.raises(sqlite3.IntegrityError):
        client.post(f"/api/learners/{learner['id']}/sessions", json={"topic": "Fractions"})

    assert client.get(f"/api/learners/{learner['id']}/sessions").json() == []


def test_session_started_elsewhere_during_the_opening_question_wins(
    client, fake_llm, make_learner, db
):
    learner = make_learner()

    def another_start_finishes_first(messages):
        db.execute(
            "INSERT INTO sessions (learner_id, topic, created_at) VALUES (?, 'Algebra', ?)",
            (learner["id"], "2026-01-01T00:00:00Z"),
        )
        return "What do you already know about fractions?"

    fake_llm.chat_replies.append(another_start_finishes_first)

    response = client.post(f"/api/learners/{learner['id']}/sessions", json={"topic": "Fractions"})

    assert response.status_code == 409
    assert [row["topic"] for row in db.execute("SELECT topic FROM sessions")] == ["Algebra"]


def test_topic_at_the_length_limit_is_accepted(client, make_learner, start_session):
    learner = make_learner()

    session = start_session(learner["id"], "x" * 120)

    assert session["topic"] == "x" * 120


def test_start_session_for_unknown_learner_returns_404(client):
    response = client.post("/api/learners/999/sessions", json={"topic": "Fractions"})

    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [{}, {"topic": ""}, {"topic": "x" * 121}, {"topic": "a\nb"}, {"topic": "Fractions", "x": 1}],
)
def test_start_session_rejects_invalid_body(client, make_learner, payload):
    learner = make_learner()

    response = client.post(f"/api/learners/{learner['id']}/sessions", json=payload)

    assert response.status_code == 422


def test_only_one_active_session_per_learner(client, make_learner, start_session):
    alex = make_learner("Alex")
    start_session(alex["id"], "Fractions")

    response = client.post(f"/api/learners/{alex['id']}/sessions", json={"topic": "Algebra"})

    assert response.status_code == 409
    assert "Fractions" in response.json()["detail"]
    sam = make_learner("Sam")
    assert start_session(sam["id"], "Algebra")["status"] == "active"


def test_list_sessions_newest_first(client, make_learner, start_session, db):
    learner = make_learner()
    first = start_session(learner["id"], "Fractions")
    # Ending sessions arrives with the memory pipeline; end this one directly for now.
    db.execute("UPDATE sessions SET status = 'ended' WHERE id = ?", (first["id"],))
    second = start_session(learner["id"], "Algebra")

    sessions = client.get(f"/api/learners/{learner['id']}/sessions").json()

    assert [session["id"] for session in sessions] == [second["id"], first["id"]]


def test_list_sessions_only_returns_the_learners_own_sessions(client, make_learner, start_session):
    alex = make_learner("Alex")
    sam = make_learner("Sam")
    start_session(alex["id"], "Fractions")
    sams_session = start_session(sam["id"], "Algebra")

    sessions = client.get(f"/api/learners/{sam['id']}/sessions").json()

    assert [session["id"] for session in sessions] == [sams_session["id"]]


def test_list_sessions_for_unknown_learner_returns_404(client):
    assert client.get("/api/learners/999/sessions").status_code == 404


def test_get_session_detail(client, make_learner, start_session):
    learner = make_learner()
    session = start_session(learner["id"])

    response = client.get(f"/api/learners/{learner['id']}/sessions/{session['id']}")

    assert response.status_code == 200
    assert response.json() == session


def test_get_unknown_session_returns_404(client, make_learner):
    learner = make_learner()

    response = client.get(f"/api/learners/{learner['id']}/sessions/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Session 999 not found."}


def test_session_of_unknown_learner_reports_the_learner(client, make_learner, start_session):
    learner = make_learner()
    session = start_session(learner["id"])

    response = client.get(f"/api/learners/999/sessions/{session['id']}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Learner 999 not found."}


def test_session_of_another_learner_returns_404(client, make_learner, start_session):
    alex = make_learner("Alex")
    sam = make_learner("Sam")
    session = start_session(alex["id"])

    response = client.get(f"/api/learners/{sam['id']}/sessions/{session['id']}")

    assert response.status_code == 404


@pytest.mark.parametrize("bad_id", INVALID_IDS)
def test_invalid_session_id_returns_422(client, make_learner, bad_id):
    learner = make_learner()

    response = client.get(f"/api/learners/{learner['id']}/sessions/{bad_id}")

    assert response.status_code == 422


@pytest.mark.parametrize("bad_id", INVALID_IDS)
@pytest.mark.parametrize(
    "method, path",
    [
        ("POST", "/api/learners/{id}/sessions"),
        ("GET", "/api/learners/{id}/sessions"),
        ("GET", "/api/learners/{id}/sessions/1"),
    ],
)
def test_invalid_learner_id_on_session_routes_returns_422(client, method, path, bad_id):
    body = {"topic": "Fractions"} if method == "POST" else None

    response = client.request(method, path.format(id=bad_id), json=body)

    assert response.status_code == 422
