import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import connect
from app.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # _env_file=None: tests must never read the developer's backend/.env.
    return Settings(_env_file=None, database_path=tmp_path / "test.db")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    # Using TestClient as a context manager runs the lifespan, which creates the database.
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def db(client: TestClient, settings: Settings) -> Iterator[sqlite3.Connection]:
    """Direct database access for test setup and assertions."""
    conn = connect(settings.database_path)
    yield conn
    conn.close()


@pytest.fixture
def make_learner(client: TestClient) -> Callable[..., dict]:
    def make(name: str = "Alex") -> dict:
        response = client.post("/api/learners", json={"name": name})
        assert response.status_code == 201, response.text
        return response.json()

    return make


@pytest.fixture
def start_session(client: TestClient) -> Callable[..., dict]:
    def start(learner_id: int, topic: str = "Fractions") -> dict:
        response = client.post(f"/api/learners/{learner_id}/sessions", json={"topic": topic})
        assert response.status_code == 201, response.text
        return response.json()

    return start
