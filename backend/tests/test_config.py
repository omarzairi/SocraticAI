import pytest
from pydantic import ValidationError

from app.config import BACKEND_DIR, Settings


def test_relative_database_path_resolves_inside_backend(monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", "data/other.db")

    assert Settings(_env_file=None).database_path == BACKEND_DIR / "data" / "other.db"


def test_home_directory_in_database_path_is_expanded(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # what expanduser() uses on Windows

    settings = Settings(_env_file=None, database_path="~/tutor.db")

    assert settings.database_path == tmp_path / "tutor.db"


def test_database_path_pointing_to_a_folder_is_rejected(tmp_path):
    with pytest.raises(ValidationError, match="must be a file"):
        Settings(_env_file=None, database_path=tmp_path)


def test_misspelled_setting_in_env_file_is_rejected(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("DATABSE_PATH=typo.db\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        Settings(_env_file=env_file)


def test_api_key_is_stripped_and_hidden_from_reprs():
    settings = Settings(_env_file=None, llm_api_key="  sk-abc123  ")

    assert settings.llm_api_key.get_secret_value() == "sk-abc123"
    assert "sk-abc123" not in repr(settings)


@pytest.mark.parametrize("bad_key", ["sk-abc”123", "sk-abc 123", "sk-​abc"])
def test_api_key_with_pasted_junk_is_rejected_without_echoing_it(bad_key):
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, llm_api_key=bad_key)

    assert "LLM_API_KEY" in str(error.value)
    assert bad_key not in str(error.value)


def test_misspelled_setting_argument_is_rejected(tmp_path):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, databse_path=tmp_path / "typo.db")
