from datetime import datetime

import pytest

# 2**63 is one past SQLite's largest integer.
INVALID_IDS = ["abc", "0", "-1", str(2**63)]


def test_create_learner_strips_the_name(client):
    response = client.post("/api/learners", json={"name": "  Alex  "})

    assert response.status_code == 201
    learner = response.json()
    assert learner["name"] == "Alex"
    assert learner["id"] >= 1
    # Timezone-aware, so browsers don't misread it as local time.
    assert datetime.fromisoformat(learner["created_at"]).tzinfo is not None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": ""},
        {"name": "   "},
        {"name": "x" * 61},
        {"name": "Al\nex"},
        {"name": 5},
        {"name": "Alex", "age": 12},
    ],
)
def test_create_learner_rejects_invalid_body(client, payload):
    assert client.post("/api/learners", json=payload).status_code == 422


def test_name_at_the_length_limit_is_accepted(client):
    assert client.post("/api/learners", json={"name": "x" * 60}).status_code == 201


def test_list_learners_in_creation_order(client, make_learner):
    alex = make_learner("Alex")
    sam = make_learner("Sam")

    learners = client.get("/api/learners").json()

    assert [learner["id"] for learner in learners] == [alex["id"], sam["id"]]


def test_get_learner(client, make_learner):
    alex = make_learner("Alex")

    response = client.get(f"/api/learners/{alex['id']}")

    assert response.status_code == 200
    assert response.json() == alex


def test_get_unknown_learner_returns_404(client):
    response = client.get("/api/learners/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Learner 999 not found."}


@pytest.mark.parametrize("bad_id", INVALID_IDS)
def test_invalid_learner_id_returns_422(client, bad_id):
    assert client.get(f"/api/learners/{bad_id}").status_code == 422


def test_largest_valid_id_is_accepted(client):
    assert client.get(f"/api/learners/{2**63 - 1}").status_code == 404
