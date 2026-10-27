import sqlite3

from app.database import utc_now
from app.schemas import Memory, MemoryKind

MEMORY_COLUMNS = (
    "id, learner_id, kind, content, status, user_edited, source_session_id, created_at, updated_at"
)


def get_memory(conn: sqlite3.Connection, learner_id: int, memory_id: int) -> Memory | None:
    row = conn.execute(
        f"SELECT {MEMORY_COLUMNS} FROM memories WHERE id = ? AND learner_id = ?",
        (memory_id, learner_id),
    ).fetchone()
    return Memory(**row) if row else None


def list_memories(conn: sqlite3.Connection, learner_id: int) -> list[Memory]:
    rows = conn.execute(
        f"SELECT {MEMORY_COLUMNS} FROM memories WHERE learner_id = ? ORDER BY id", (learner_id,)
    ).fetchall()
    return [Memory(**row) for row in rows]


def list_active_memories(conn: sqlite3.Connection, learner_id: int) -> list[Memory]:
    """Active memories, most recently updated first (ties broken by id)."""
    rows = conn.execute(
        f"SELECT {MEMORY_COLUMNS} FROM memories WHERE learner_id = ? AND status = 'active' "
        "ORDER BY updated_at DESC, id DESC",
        (learner_id,),
    ).fetchall()
    return [Memory(**row) for row in rows]


def insert_memory(
    conn: sqlite3.Connection, learner_id: int, session_id: int, kind: MemoryKind, content: str
) -> int:
    now = utc_now()
    cursor = conn.execute(
        "INSERT INTO memories (learner_id, kind, content, source_session_id, created_at, "
        "updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (learner_id, kind, content, session_id, now, now),
    )
    return cursor.lastrowid


def update_memory_by_learner(
    conn: sqlite3.Connection, learner_id: int, memory_id: int, content: str
) -> bool:
    """The learner's correction. Sets user_edited, which locks the memory against the extractor."""
    cursor = conn.execute(
        "UPDATE memories SET content = ?, user_edited = 1, updated_at = ? "
        "WHERE id = ? AND learner_id = ?",
        (content, utc_now(), memory_id, learner_id),
    )
    return cursor.rowcount == 1


def delete_memory(conn: sqlite3.Connection, learner_id: int, memory_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM memories WHERE id = ? AND learner_id = ?", (memory_id, learner_id)
    )
    return cursor.rowcount == 1


# The two functions below are the only ways the extractor changes an existing memory.
# Their WHERE clause enforces the rule "the extractor never touches a memory the learner
# edited", even if the learner edits it while the extraction is running.


def update_extracted_memory(
    conn: sqlite3.Connection, learner_id: int, memory_id: int, session_id: int, content: str
) -> bool:
    """False when the memory is missing, archived, another learner's, or edited by the learner."""
    cursor = conn.execute(
        "UPDATE memories SET content = ?, source_session_id = ?, updated_at = ? "
        "WHERE id = ? AND learner_id = ? AND status = 'active' AND user_edited = 0",
        (content, session_id, utc_now(), memory_id, learner_id),
    )
    return cursor.rowcount == 1


def archive_extracted_memory(
    conn: sqlite3.Connection, learner_id: int, memory_id: int, session_id: int
) -> bool:
    """False when the memory is missing, archived, another learner's, or edited by the learner."""
    cursor = conn.execute(
        "UPDATE memories SET status = 'archived', source_session_id = ?, updated_at = ? "
        "WHERE id = ? AND learner_id = ? AND status = 'active' AND user_edited = 0",
        (session_id, utc_now(), memory_id, learner_id),
    )
    return cursor.rowcount == 1
