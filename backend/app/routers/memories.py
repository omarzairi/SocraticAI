from fastapi import APIRouter

from app.dependencies import DbConn, Id
from app.schemas import Memory, MemoryEdit
from app.services import memory_service

router = APIRouter(prefix="/api/learners/{learner_id}/memories", tags=["memories"])


@router.get("")
def list_memories(learner_id: Id, conn: DbConn) -> list[Memory]:
    return memory_service.list_memories(conn, learner_id)


@router.patch("/{memory_id}")
def edit_memory(learner_id: Id, memory_id: Id, body: MemoryEdit, conn: DbConn) -> Memory:
    return memory_service.edit_memory(conn, learner_id, memory_id, body.content)


@router.delete("/{memory_id}", status_code=204)
def delete_memory(learner_id: Id, memory_id: Id, conn: DbConn) -> None:
    memory_service.delete_memory(conn, learner_id, memory_id)
