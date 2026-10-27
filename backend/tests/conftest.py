from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
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
