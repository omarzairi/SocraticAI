import pytest
from fastapi.testclient import TestClient

from app import main


def test_building_the_app_does_not_read_settings(monkeypatch):
    def fail_if_called():
        raise AssertionError("Settings() must only be read when the server starts")

    monkeypatch.setattr(main, "Settings", fail_if_called)

    main.create_app()


def test_health(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_data_survives_an_app_restart(settings, make_learner):
    alex = make_learner("Alex")

    with TestClient(main.create_app(settings)) as restarted:
        assert restarted.get("/api/learners").json() == [alex]


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://127.0.0.1:3000"])
@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE"])
def test_cors_preflight_allows_frontend_writes(client, origin, method):
    response = client.options(
        "/api/learners",
        headers={"Origin": origin, "Access-Control-Request-Method": method},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert method in response.headers["access-control-allow-methods"]


def test_cors_rejects_unknown_origin(client):
    response = client.options(
        "/api/learners",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
    )

    assert "access-control-allow-origin" not in response.headers
