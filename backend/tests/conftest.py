import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import connect
from app.dependencies import get_llm_client
from app.main import create_app
from tests.fakes import FakeLLMClient

OPENING_QUESTION = "Hi! What do you already know about this topic?"
TUTOR_REPLY = "Interesting. Why do you think that?"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,  # never read the developer's backend/.env
        database_path=tmp_path / "test.db",
        # Even if a test bypassed the fake LLM, it couldn't reach a real provider with a real key.
        llm_api_key="test-key",
        llm_base_url="http://llm.invalid/v1",
        llm_max_retries=0,
    )


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
def client(settings: Settings, fake_llm: FakeLLMClient) -> Iterator[TestClient]:
    app = create_app(settings)
    app.dependency_overrides[get_llm_client] = lambda: fake_llm
    # Using TestClient as a context manager runs the lifespan, which creates the database.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db(client: TestClient, settings: Settings) -> Iterator[sqlite3.Connection]:
    """A second connection for test setup and checks.

    busy_timeout = 0: if the app ever held a lock while waiting for the LLM, a write from here
    would fail at once with "database is locked" instead of quietly waiting.
    """
    conn = connect(settings.database_path)
    conn.execute("PRAGMA busy_timeout = 0")
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
def start_session(client: TestClient, fake_llm: FakeLLMClient) -> Callable[..., dict]:
    def start(learner_id: int, topic: str = "Fractions", opening: str = OPENING_QUESTION) -> dict:
        fake_llm.chat_replies.append(opening)
        response = client.post(f"/api/learners/{learner_id}/sessions", json={"topic": topic})
        assert response.status_code == 201, response.text
        return response.json()

    return start
