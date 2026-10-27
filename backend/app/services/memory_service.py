import logging
import sqlite3

from app.repositories import memory_repository
from app.schemas import MemoryUpdate
from app.services.memory_extraction import (
    ArchiveOperation,
    CreateOperation,
    MemoryOperation,
    UpdateOperation,
)

logger = logging.getLogger(__name__)


def apply_operations(
    conn: sqlite3.Connection, learner_id: int, session_id: int, operations: list[MemoryOperation]
) -> MemoryUpdate:
    """Apply the extractor's operations. Must run inside the caller's transaction.

    The LLM proposes, this code decides: operations on memories the extractor may not touch
    (another learner's, archived, or edited by the learner) are skipped by the SQL itself,
    and a create that repeats an active memory is skipped.
    """
    update = MemoryUpdate()
    known = {
        _normalize(memory.content)
        for memory in memory_repository.list_active_memories(conn, learner_id)
    }
    for operation in operations:
        match operation:
            case CreateOperation(kind=kind, content=content):
                if _normalize(content) in known:
                    logger.info("Skipping a duplicate memory: %r", content)
                    continue
                memory_id = memory_repository.insert_memory(
                    conn, learner_id, session_id, kind, content
                )
                known.add(_normalize(content))
                update.created.append(memory_repository.get_memory(conn, learner_id, memory_id))
            case UpdateOperation(memory_id=memory_id, content=content):
                if memory_repository.update_extracted_memory(
                    conn, learner_id, memory_id, session_id, content
                ):
                    known.add(_normalize(content))
                    update.updated.append(memory_repository.get_memory(conn, learner_id, memory_id))
                else:
                    _log_skipped("update", memory_id)
            case ArchiveOperation(memory_id=memory_id):
                if memory_repository.archive_extracted_memory(
                    conn, learner_id, memory_id, session_id
                ):
                    update.archived.append(
                        memory_repository.get_memory(conn, learner_id, memory_id)
                    )
                else:
                    _log_skipped("archive", memory_id)
    return update


def _normalize(content: str) -> str:
    return " ".join(content.casefold().split())


def _log_skipped(action: str, memory_id: int) -> None:
    logger.warning(
        "Skipped the extractor's %s of memory %s: missing, archived, another learner's, "
        "or edited by the learner",
        action,
        memory_id,
    )
