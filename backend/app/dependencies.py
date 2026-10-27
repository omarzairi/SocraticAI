import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Path, Request

from app.config import Settings
from app.database import connect
from app.llm import LLMClient
from app.schemas import SQLITE_MAX_INTEGER


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


def get_llm_client(request: Request) -> LLMClient:
    """The client built at startup. Tests override this dependency with a fake."""
    return request.app.state.llm_client


DbConn = Annotated[sqlite3.Connection, Depends(get_connection)]
Llm = Annotated[LLMClient, Depends(get_llm_client)]

Id = Annotated[int, Path(ge=1, le=SQLITE_MAX_INTEGER)]
