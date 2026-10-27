from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

# Rejects text spanning several lines (checked after surrounding whitespace is stripped).
SINGLE_LINE = r"^[^\r\n]+$"

LearnerName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60, pattern=SINGLE_LINE)
]
Topic = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120, pattern=SINGLE_LINE)
]

SessionStatus = Literal["active", "ended"]
MessageRole = Literal["learner", "tutor"]


class RequestBody(BaseModel):
    """Base class for request bodies: unknown fields are rejected, not silently ignored."""

    model_config = ConfigDict(extra="forbid")


class LearnerCreate(RequestBody):
    name: LearnerName


class SessionCreate(RequestBody):
    topic: Topic


class Learner(BaseModel):
    id: int
    name: str
    created_at: datetime


class Session(BaseModel):
    id: int
    learner_id: int
    topic: str
    status: SessionStatus
    created_at: datetime
    ended_at: datetime | None


class Message(BaseModel):
    id: int
    session_id: int
    role: MessageRole
    content: str
    created_at: datetime


class SessionDetail(Session):
    messages: list[Message]
