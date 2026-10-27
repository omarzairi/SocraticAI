import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def connect(database_path: Path) -> sqlite3.Connection:
    """Open a connection configured the way the whole app expects."""
    # check_same_thread=False: FastAPI may run a sync dependency and the sync route on different
    # threadpool threads. Each connection still serves only one request.
    # autocommit=True: sqlite3 never opens transactions on its own, so plain reads hold no lock.
    # Writes are grouped explicitly with transaction().
    conn = sqlite3.connect(database_path, check_same_thread=False, autocommit=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(database_path: Path) -> None:
    """Create the database folder and tables if they don't exist yet."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(database_path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[None]:
    """Run the statements in the `with` block atomically: commit on success, roll back on error.

    BEGIN IMMEDIATE takes the write lock up front, so checks made inside the block can't be
    invalidated by another request before we commit. Nesting raises an error instead of
    silently committing early.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        conn.execute("COMMIT")
    except BaseException:
        # SQLite may already have rolled back by itself (e.g. disk full, INSERT OR ROLLBACK);
        # a second ROLLBACK would then fail and hide the original error.
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def utc_now() -> str:
    return datetime.now(UTC).isoformat()
