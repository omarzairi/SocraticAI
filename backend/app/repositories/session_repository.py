import sqlite3

from app.database import utc_now
from app.schemas import Message, MessageRole, Session

SESSION_COLUMNS = "id, learner_id, topic, status, created_at, ended_at"
MESSAGE_COLUMNS = "id, session_id, role, content, created_at"


def insert_session(conn: sqlite3.Connection, learner_id: int, topic: str) -> int:
    cursor = conn.execute(
        "INSERT INTO sessions (learner_id, topic, created_at) VALUES (?, ?, ?)",
        (learner_id, topic, utc_now()),
    )
    return cursor.lastrowid


def get_session(conn: sqlite3.Connection, learner_id: int, session_id: int) -> Session | None:
    row = conn.execute(
        f"SELECT {SESSION_COLUMNS} FROM sessions WHERE id = ? AND learner_id = ?",
        (session_id, learner_id),
    ).fetchone()
    return Session(**row) if row else None


def get_active_session(conn: sqlite3.Connection, learner_id: int) -> Session | None:
    row = conn.execute(
        f"SELECT {SESSION_COLUMNS} FROM sessions WHERE learner_id = ? AND status = 'active'",
        (learner_id,),
    ).fetchone()
    return Session(**row) if row else None


def list_sessions(conn: sqlite3.Connection, learner_id: int) -> list[Session]:
    rows = conn.execute(
        f"SELECT {SESSION_COLUMNS} FROM sessions WHERE learner_id = ? ORDER BY id DESC",
        (learner_id,),
    ).fetchall()
    return [Session(**row) for row in rows]


def mark_ended(conn: sqlite3.Connection, session_id: int) -> None:
    conn.execute(
        "UPDATE sessions SET status = 'ended', ended_at = ? WHERE id = ?", (utc_now(), session_id)
    )


def insert_message(
    conn: sqlite3.Connection, session_id: int, role: MessageRole, content: str
) -> int:
    cursor = conn.execute(
        "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (session_id, role, content, utc_now()),
    )
    return cursor.lastrowid


def count_messages(conn: sqlite3.Connection, session_id: int) -> int:
    return conn.execute(
        "SELECT count(*) FROM messages WHERE session_id = ?", (session_id,)
    ).fetchone()[0]


def get_message(conn: sqlite3.Connection, message_id: int) -> Message:
    """A message that is known to exist (used right after inserting it)."""
    row = conn.execute(
        f"SELECT {MESSAGE_COLUMNS} FROM messages WHERE id = ?", (message_id,)
    ).fetchone()
    return Message(**row)


def list_messages(conn: sqlite3.Connection, session_id: int) -> list[Message]:
    """Messages of one session, oldest first.

    Callers first load the session with get_session(conn, learner_id, session_id),
    which checks that the session belongs to the learner.
    """
    rows = conn.execute(
        f"SELECT {MESSAGE_COLUMNS} FROM messages WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()
    return [Message(**row) for row in rows]
