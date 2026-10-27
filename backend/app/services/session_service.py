import sqlite3

from app.database import transaction
from app.errors import ConflictError, NotFoundError
from app.llm import LLMClient
from app.repositories import session_repository
from app.schemas import Session, SessionDetail
from app.services import learner_service, prompt_builder

# Some variety keeps the tutor's questions from sounding scripted.
TUTOR_TEMPERATURE = 0.7


def start_session(
    conn: sqlite3.Connection, llm: LLMClient, learner_id: int, topic: str
) -> SessionDetail:
    """Create a session with the tutor's opening question. Nothing is saved if the LLM fails."""
    learner = learner_service.get_learner(conn, learner_id)
    _ensure_no_active_session(conn, learner_id)  # fail fast, before calling the LLM
    opening = llm.complete(
        prompt_builder.build_tutor_messages(learner, topic, history=[]),
        temperature=TUTOR_TEMPERATURE,
    )
    with transaction(conn):
        # Checked again: another start may have finished while the LLM was answering.
        _ensure_no_active_session(conn, learner_id)
        session_id = session_repository.insert_session(conn, learner_id, topic)
        session_repository.insert_message(conn, session_id, "tutor", opening)
    return get_session_detail(conn, learner_id, session_id)


def list_sessions(conn: sqlite3.Connection, learner_id: int) -> list[Session]:
    learner_service.get_learner(conn, learner_id)
    return session_repository.list_sessions(conn, learner_id)


def get_session(conn: sqlite3.Connection, learner_id: int, session_id: int) -> Session:
    learner_service.get_learner(conn, learner_id)  # a missing learner is reported as such
    session = session_repository.get_session(conn, learner_id, session_id)
    if session is None:
        raise NotFoundError(f"Session {session_id} not found.")
    return session


def get_session_detail(conn: sqlite3.Connection, learner_id: int, session_id: int) -> SessionDetail:
    session = get_session(conn, learner_id, session_id)
    messages = session_repository.list_messages(conn, session_id)
    return SessionDetail(**session.model_dump(), messages=messages)


def _ensure_no_active_session(conn: sqlite3.Connection, learner_id: int) -> None:
    active = session_repository.get_active_session(conn, learner_id)
    if active is not None:
        raise ConflictError(
            f"You already have an active session on '{active.topic}'. "
            "Continue it or end it before starting a new one."
        )
