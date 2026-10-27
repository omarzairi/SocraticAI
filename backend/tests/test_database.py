import sqlite3

import pytest

from app.database import connect, init_db, transaction

INSERT_LEARNER = "INSERT INTO learners (name, created_at) VALUES ('Alex', '2026-01-01T00:00Z')"


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "nested" / "app.db"
    init_db(path)
    return path


@pytest.fixture
def conn(db_path):
    conn = connect(db_path)
    yield conn
    conn.close()


def count_learners(db_path) -> int:
    """Count through a second connection, so we only see committed data."""
    other = connect(db_path)
    try:
        return other.execute("SELECT count(*) FROM learners").fetchone()[0]
    finally:
        other.close()


def test_init_db_creates_the_folder_and_can_run_twice(db_path):
    init_db(db_path)

    assert db_path.exists()


def test_transaction_commits_on_success(conn, db_path):
    with transaction(conn):
        conn.execute(INSERT_LEARNER)

    assert count_learners(db_path) == 1


def test_transaction_rolls_back_on_error(conn, db_path):
    with pytest.raises(RuntimeError):
        with transaction(conn):
            conn.execute(INSERT_LEARNER)
            raise RuntimeError("boom")

    assert count_learners(db_path) == 0
    assert not conn.in_transaction


def test_transaction_keeps_the_original_error_when_sqlite_already_rolled_back(conn, db_path):
    with pytest.raises(sqlite3.IntegrityError):
        with transaction(conn):
            conn.execute(INSERT_LEARNER)
            # OR ROLLBACK makes SQLite end the transaction itself before raising.
            conn.execute("INSERT OR ROLLBACK INTO learners (name, created_at) VALUES (NULL, 'x')")

    assert count_learners(db_path) == 0
    assert not conn.in_transaction


def test_nested_transaction_fails_loudly(conn):
    with transaction(conn):
        with pytest.raises(sqlite3.OperationalError, match="within a transaction"):
            with transaction(conn):
                pass


def test_plain_reads_do_not_open_a_transaction(conn):
    conn.execute("SELECT * FROM learners").fetchall()

    assert not conn.in_transaction


def test_foreign_keys_are_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO sessions (learner_id, topic, created_at) VALUES (999, 'Fractions', 'now')"
        )
