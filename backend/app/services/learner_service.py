import sqlite3

from app.database import transaction
from app.errors import NotFoundError
from app.repositories import learner_repository
from app.schemas import Learner


def create_learner(conn: sqlite3.Connection, name: str) -> Learner:
    with transaction(conn):
        learner_id = learner_repository.insert_learner(conn, name)
    return get_learner(conn, learner_id)


def list_learners(conn: sqlite3.Connection) -> list[Learner]:
    return learner_repository.list_learners(conn)


def get_learner(conn: sqlite3.Connection, learner_id: int) -> Learner:
    learner = learner_repository.get_learner(conn, learner_id)
    if learner is None:
        raise NotFoundError(f"Learner {learner_id} not found.")
    return learner
