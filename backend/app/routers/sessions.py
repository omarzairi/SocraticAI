from fastapi import APIRouter

from app.dependencies import DbConn, Id
from app.schemas import Session, SessionCreate, SessionDetail
from app.services import session_service

router = APIRouter(prefix="/api/learners/{learner_id}/sessions", tags=["sessions"])


@router.post("", status_code=201)
def start_session(learner_id: Id, body: SessionCreate, conn: DbConn) -> SessionDetail:
    return session_service.start_session(conn, learner_id, body.topic)


@router.get("")
def list_sessions(learner_id: Id, conn: DbConn) -> list[Session]:
    return session_service.list_sessions(conn, learner_id)


@router.get("/{session_id}")
def get_session(learner_id: Id, session_id: Id, conn: DbConn) -> SessionDetail:
    return session_service.get_session_detail(conn, learner_id, session_id)
