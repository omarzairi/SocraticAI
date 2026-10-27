from fastapi import APIRouter

from app.dependencies import DbConn, Id
from app.schemas import Learner, LearnerCreate
from app.services import learner_service

router = APIRouter(prefix="/api/learners", tags=["learners"])


@router.post("", status_code=201)
def create_learner(body: LearnerCreate, conn: DbConn) -> Learner:
    return learner_service.create_learner(conn, body.name)


@router.get("")
def list_learners(conn: DbConn) -> list[Learner]:
    return learner_service.list_learners(conn)


@router.get("/{learner_id}")
def get_learner(learner_id: Id, conn: DbConn) -> Learner:
    return learner_service.get_learner(conn, learner_id)
