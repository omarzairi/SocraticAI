import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Path, Request

from app.config import Settings
from app.database import connect

SQLITE_MAX_INTEGER = 2**63 - 1


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_connection(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Iterator[sqlite3.Connection]:
    """Open one connection per request and always close it.

    Never commit here: FastAPI runs the code after `yield` once the response has been sent,
    so a failed commit would be invisible to the client. Services commit explicitly.
    """
    conn = connect(settings.database_path)
    try:
        yield conn
    finally:
        conn.close()


DbConn = Annotated[sqlite3.Connection, Depends(get_connection)]

# Path ids must fit in a SQLite INTEGER; a larger value would make sqlite3 raise a 500.
Id = Annotated[int, Path(ge=1, le=SQLITE_MAX_INTEGER)]
