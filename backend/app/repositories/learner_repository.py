import sqlite3

from app.database import utc_now
from app.schemas import Learner

LEARNER_COLUMNS = "id, name, created_at"


def insert_learner(conn: sqlite3.Connection, name: str) -> int:
    cursor = conn.execute(
        "INSERT INTO learners (name, created_at) VALUES (?, ?)", (name, utc_now())
    )
    return cursor.lastrowid


def get_learner(conn: sqlite3.Connection, learner_id: int) -> Learner | None:
    row = conn.execute(
        f"SELECT {LEARNER_COLUMNS} FROM learners WHERE id = ?", (learner_id,)
    ).fetchone()
    return Learner(**row) if row else None


def list_learners(conn: sqlite3.Connection) -> list[Learner]:
    rows = conn.execute(f"SELECT {LEARNER_COLUMNS} FROM learners ORDER BY id").fetchall()
    return [Learner(**row) for row in rows]
