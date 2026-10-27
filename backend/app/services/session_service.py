import sqlite3

from app.database import transaction
from app.errors import ConflictError, NotFoundError
from app.llm import LLMClient
from app.repositories import memory_repository, session_repository
from app.schemas import ChatTurn, EndSessionResponse, Message, Session, SessionDetail
from app.services import learner_service, memory_extraction, memory_service, prompt_builder

# Some variety keeps the tutor's questions from sounding scripted.
TUTOR_TEMPERATURE = 0.7
# Memory updates should be consistent rather than creative.
EXTRACTION_TEMPERATURE = 0.2


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


def send_message(
    conn: sqlite3.Connection, llm: LLMClient, learner_id: int, session_id: int, content: str
) -> ChatTurn:
    """Save the learner's message together with the tutor's reply, or nothing if the LLM fails."""
    learner = learner_service.get_learner(conn, learner_id)
    session = get_session(conn, learner_id, session_id)
    _ensure_active(session)
    history = session_repository.list_messages(conn, session_id)
    reply = llm.complete(
        prompt_builder.build_tutor_messages(learner, session.topic, history, new_message=content),
        temperature=TUTOR_TEMPERATURE,
    )
    with transaction(conn):
        _ensure_unchanged(conn, learner_id, session_id, history)
        learner_message_id = session_repository.insert_message(conn, session_id, "learner", content)
        tutor_message_id = session_repository.insert_message(conn, session_id, "tutor", reply)
    return ChatTurn(
        learner_message=session_repository.get_message(conn, learner_message_id),
        tutor_message=session_repository.get_message(conn, tutor_message_id),
    )


def end_session(
    conn: sqlite3.Connection, llm: LLMClient, learner_id: int, session_id: int
) -> EndSessionResponse:
    """End the session and update the learner's memory together: both happen, or neither.

    If the LLM fails or its reply is unusable, nothing changes and the session stays open,
    so "ended" always means "memory was updated".
    """
    session = get_session(conn, learner_id, session_id)
    _ensure_active(session)
    history = session_repository.list_messages(conn, session_id)
    operations = []
    if any(message.role == "learner" for message in history):  # else nothing to learn from
        memories = memory_repository.list_active_memories(conn, learner_id)
        reply = llm.complete(
            prompt_builder.build_extraction_messages(session.topic, memories, history),
            temperature=EXTRACTION_TEMPERATURE,
            json_mode=True,
        )
        operations = memory_extraction.parse_operations(reply)
    with transaction(conn):
        _ensure_unchanged(conn, learner_id, session_id, history)
        session_repository.mark_ended(conn, session_id)
        memory_update = memory_service.apply_operations(conn, learner_id, session_id, operations)
    return EndSessionResponse(
        session=get_session(conn, learner_id, session_id), memory_update=memory_update
    )


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


def _ensure_unchanged(
    conn: sqlite3.Connection, learner_id: int, session_id: int, history: list[Message]
) -> None:
    """Re-check inside the write transaction what we read before calling the LLM.

    While the LLM was answering, the session may have ended or another message may have
    arrived (a second tab), and the LLM's answer was based on `history`.
    """
    _ensure_active(get_session(conn, learner_id, session_id))
    if session_repository.count_messages(conn, session_id) != len(history):
        raise ConflictError(
            "The conversation changed in the meantime. Reload the session and try again."
        )


def _ensure_active(session: Session) -> None:
    if session.status != "active":
        raise ConflictError("This session has ended. Start a new session to keep learning.")


def _ensure_no_active_session(conn: sqlite3.Connection, learner_id: int) -> None:
    active = session_repository.get_active_session(conn, learner_id)
    if active is not None:
        raise ConflictError(
            f"You already have an active session on '{active.topic}'. "
            "Continue it or end it before starting a new one."
        )
