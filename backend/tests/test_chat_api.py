import pytest

from app.llm import LLMError
from tests.fakes import OPENING_QUESTION

# 2**63 is one past SQLite's largest integer.
INVALID_IDS = ["abc", "0", "-1", str(2**63)]


@pytest.fixture
def session(make_learner, start_session) -> dict:
    learner = make_learner("Alex")
    return start_session(learner["id"], "Fractions")


def messages_url(session: dict) -> str:
    return f"/api/learners/{session['learner_id']}/sessions/{session['id']}/messages"


def stored_messages(client, session: dict) -> list[tuple[str, str]]:
    detail = client.get(f"/api/learners/{session['learner_id']}/sessions/{session['id']}").json()
    return [(message["role"], message["content"]) for message in detail["messages"]]


def test_send_message_saves_the_message_and_the_tutors_reply(client, fake_llm, session):
    fake_llm.chat_replies.append("What do you notice about the denominators?")

    response = client.post(messages_url(session), json={"content": "  1/2 + 1/3 = 2/5  "})

    assert response.status_code == 201
    turn = response.json()
    assert turn["learner_message"]["role"] == "learner"
    assert turn["learner_message"]["content"] == "1/2 + 1/3 = 2/5"
    assert turn["tutor_message"]["role"] == "tutor"
    assert turn["tutor_message"]["content"] == "What do you notice about the denominators?"
    assert stored_messages(client, session) == [
        ("tutor", OPENING_QUESTION),
        ("learner", "1/2 + 1/3 = 2/5"),
        ("tutor", "What do you notice about the denominators?"),
    ]


def test_the_tutor_sees_the_conversation_in_order(client, fake_llm, session):
    fake_llm.chat_replies += ["Why do you add them?", "Can you show me with a drawing?"]

    client.post(messages_url(session), json={"content": "I add the tops and the bottoms."})
    client.post(messages_url(session), json={"content": "Because that's how it works."})

    last_call = fake_llm.chat_calls[-1]
    assert not last_call.json_mode
    assert [(m["role"], m["content"]) for m in last_call.messages[2:]] == [
        ("assistant", OPENING_QUESTION),
        ("user", "I add the tops and the bottoms."),
        ("assistant", "Why do you add them?"),
        ("user", "Because that's how it works."),
    ]


def test_llm_failure_saves_nothing(client, fake_llm, session):
    fake_llm.chat_replies.append(
        LLMError("The AI provider's rate limit was reached. Wait a minute and try again.")
    )

    response = client.post(messages_url(session), json={"content": "I add them."})

    assert response.status_code == 502
    assert response.json() == {
        "detail": "The AI provider's rate limit was reached. Wait a minute and try again."
    }
    assert stored_messages(client, session) == [("tutor", OPENING_QUESTION)]


def test_message_to_an_ended_session_returns_409_without_calling_the_llm(
    client, fake_llm, session, db
):
    db.execute("UPDATE sessions SET status = 'ended' WHERE id = ?", (session["id"],))

    response = client.post(messages_url(session), json={"content": "Hello?"})

    assert response.status_code == 409
    assert len(fake_llm.calls) == 1  # only the opening question
    assert stored_messages(client, session) == [("tutor", OPENING_QUESTION)]


def test_session_ended_while_the_tutor_was_replying_saves_nothing(client, fake_llm, session, db):
    def session_ends_meanwhile(messages):
        db.execute("UPDATE sessions SET status = 'ended' WHERE id = ?", (session["id"],))
        return "Why do you think so?"

    fake_llm.chat_replies.append(session_ends_meanwhile)

    response = client.post(messages_url(session), json={"content": "I add them."})

    assert response.status_code == 409
    assert stored_messages(client, session) == [("tutor", OPENING_QUESTION)]


def test_no_database_lock_is_held_while_waiting_for_the_llm(client, fake_llm, session, db):
    def write_from_another_connection(messages):
        # db uses busy_timeout = 0, so this write fails at once if the request holds a lock.
        db.execute("INSERT INTO learners (name, created_at) VALUES ('Sam', '2026-01-01T00:00Z')")
        return "Why do you think so?"

    fake_llm.chat_replies.append(write_from_another_connection)

    response = client.post(messages_url(session), json={"content": "I add them."})

    assert response.status_code == 201


def test_message_to_unknown_session_returns_404(client, session):
    response = client.post(
        f"/api/learners/{session['learner_id']}/sessions/999/messages", json={"content": "Hi"}
    )

    assert response.status_code == 404


def test_message_to_another_learners_session_returns_404(client, make_learner, session):
    sam = make_learner("Sam")

    response = client.post(
        f"/api/learners/{sam['id']}/sessions/{session['id']}/messages", json={"content": "Hi"}
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [{}, {"content": ""}, {"content": "   "}, {"content": "x" * 2001}, {"content": "Hi", "x": 1}],
)
def test_invalid_message_returns_422(client, session, payload):
    assert client.post(messages_url(session), json=payload).status_code == 422


@pytest.mark.parametrize("content", ["x" * 2000, "Step 1: common denominator.\nStep 2: add."])
def test_long_and_multi_line_messages_are_accepted(client, fake_llm, session, content):
    fake_llm.chat_replies.append("Why?")

    assert client.post(messages_url(session), json={"content": content}).status_code == 201


@pytest.mark.parametrize("bad_id", INVALID_IDS)
def test_invalid_session_id_returns_422(client, session, bad_id):
    response = client.post(
        f"/api/learners/{session['learner_id']}/sessions/{bad_id}/messages",
        json={"content": "Hi"},
    )

    assert response.status_code == 422
