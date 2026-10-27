from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Settings read from environment variables and backend/.env (env vars win)."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_path: Path = BACKEND_DIR / "data" / "app.db"

    @field_validator("database_path")
    @classmethod
    def resolve_relative_to_backend(cls, path: Path) -> Path:
        # A relative DATABASE_PATH means "inside backend/", wherever the server is started from.
        return path if path.is_absolute() else BACKEND_DIR / path
