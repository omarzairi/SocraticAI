from fastapi import APIRouter

from app.dependencies import DbConn, Id, Llm
from app.schemas import (
    ChatTurn,
    EndSessionResponse,
    MessageCreate,
    Session,
    SessionCreate,
    SessionDetail,
)
from app.services import session_service

router = APIRouter(prefix="/api/learners/{learner_id}/sessions", tags=["sessions"])


@router.post("", status_code=201)
def start_session(learner_id: Id, body: SessionCreate, conn: DbConn, llm: Llm) -> SessionDetail:
    return session_service.start_session(conn, llm, learner_id, body.topic)


@router.get("")
def list_sessions(learner_id: Id, conn: DbConn) -> list[Session]:
    return session_service.list_sessions(conn, learner_id)


@router.get("/{session_id}")
def get_session(learner_id: Id, session_id: Id, conn: DbConn) -> SessionDetail:
    return session_service.get_session_detail(conn, learner_id, session_id)


@router.post("/{session_id}/messages", status_code=201)
def send_message(
    learner_id: Id, session_id: Id, body: MessageCreate, conn: DbConn, llm: Llm
) -> ChatTurn:
    return session_service.send_message(conn, llm, learner_id, session_id, body.content)


@router.post("/{session_id}/end")
def end_session(learner_id: Id, session_id: Id, conn: DbConn, llm: Llm) -> EndSessionResponse:
    return session_service.end_session(conn, llm, learner_id, session_id)
