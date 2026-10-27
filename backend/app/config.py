from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Settings read from environment variables and backend/.env (env vars win).

    Unknown keys are rejected (the BaseSettings default), so a typo fails at startup
    instead of silently falling back to a default value.
    """

    # hide_input_in_errors: a validation error must never echo a value such as the API key.
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", hide_input_in_errors=True
    )

    database_path: Path = BACKEND_DIR / "data" / "app.db"

    # SecretStr keeps the key out of logs and reprs. Empty means "not configured yet".
    llm_api_key: SecretStr = SecretStr("")
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "openai/gpt-oss-120b"
    # gpt-oss thinks before answering; "low" keeps replies fast. Empty for models that don't reason.
    llm_reasoning_effort: str = "low"
    llm_timeout_seconds: float = 30.0
    # One retry rides out a brief hiccup; more would keep the learner waiting for minutes.
    llm_max_retries: int = 1

    @field_validator("llm_api_key", mode="before")
    @classmethod
    def clean_api_key(cls, value: object) -> object:
        # A key pasted with spaces or "smart" characters would break every single request.
        if isinstance(value, str):
            value = value.strip()
            if not value.isascii() or any(char.isspace() for char in value):
                raise ValueError("LLM_API_KEY must be plain text without spaces; paste it again")
        return value

    @field_validator("database_path")
    @classmethod
    def resolve_database_path(cls, path: Path) -> Path:
        # A relative path means "inside backend/", wherever the server is started from.
        path = path.expanduser()
        if not path.is_absolute():
            path = BACKEND_DIR / path
        if path.is_dir():
            raise ValueError(f"DATABASE_PATH must be a file, not a folder: {path}")
        return path
