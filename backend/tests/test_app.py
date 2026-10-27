import pytest

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


@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE"])
def test_cors_preflight_allows_frontend_writes(client, method):
    response = client.options(
        "/api/learners",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": method},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert method in response.headers["access-control-allow-methods"]


def test_cors_rejects_unknown_origin(client):
    response = client.options(
        "/api/learners",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
    )

    assert "access-control-allow-origin" not in response.headers
