import pytest

# 2**63 is one past SQLite's largest integer.
INVALID_IDS = ["abc", "0", "-1", str(2**63)]


def test_start_session_creates_an_active_session(client, make_learner):
    learner = make_learner()

    response = client.post(
        f"/api/learners/{learner['id']}/sessions", json={"topic": "  Fractions  "}
    )

    assert response.status_code == 201
    session = response.json()
    assert session["topic"] == "Fractions"
    assert session["status"] == "active"
    assert session["learner_id"] == learner["id"]
    assert session["ended_at"] is None
    assert session["messages"] == []


def test_topic_at_the_length_limit_is_accepted(client, make_learner):
    learner = make_learner()

    response = client.post(f"/api/learners/{learner['id']}/sessions", json={"topic": "x" * 120})

    assert response.status_code == 201


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
