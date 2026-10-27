import sqlite3

from app.database import transaction
from app.errors import ConflictError, NotFoundError
from app.repositories import session_repository
from app.schemas import Session, SessionDetail
from app.services import learner_service


def start_session(conn: sqlite3.Connection, learner_id: int, topic: str) -> SessionDetail:
    learner_service.get_learner(conn, learner_id)
    with transaction(conn):
        # Checked inside the transaction so two concurrent starts can't both succeed.
        active = session_repository.get_active_session(conn, learner_id)
        if active is not None:
            raise ConflictError(
                f"You already have an active session on '{active.topic}'. "
                "Continue it or end it before starting a new one."
            )
        session_id = session_repository.insert_session(conn, learner_id, topic)
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
