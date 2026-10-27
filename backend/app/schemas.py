from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

# Rejects text spanning several lines (checked after surrounding whitespace is stripped).
SINGLE_LINE = r"^[^\r\n]+$"
# Ids must fit in a SQLite INTEGER; a larger value would make sqlite3 raise (a 500).
SQLITE_MAX_INTEGER = 2**63 - 1

LearnerName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60, pattern=SINGLE_LINE)
]
Topic = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120, pattern=SINGLE_LINE)
]
# Learner messages may span several lines (working through steps, for example).
MessageContent = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]

SessionStatus = Literal["active", "ended"]
MessageRole = Literal["learner", "tutor"]

# Memory kinds are defined here once; the prompts list them from MEMORY_KIND_DESCRIPTIONS.
# Adding a kind: add it to both, plus a label in the frontend's lib/types.ts.
MemoryKind = Literal["progress", "knowledge_gap", "misconception", "preference"]
MEMORY_KIND_DESCRIPTIONS: dict[MemoryKind, str] = {
    "progress": "something the learner showed they understand or can do",
    "knowledge_gap": "something the learner doesn't know yet or struggled with",
    "misconception": "a specific incorrect belief the learner expressed",
    "preference": "how the learner likes to learn (examples, pace, style)",
}
MemoryStatus = Literal["active", "archived"]
MemoryContent = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300, pattern=SINGLE_LINE)
]


class RequestBody(BaseModel):
    """Base class for request bodies: unknown fields are rejected, not silently ignored."""

    model_config = ConfigDict(extra="forbid")


class LearnerCreate(RequestBody):
    name: LearnerName


class SessionCreate(RequestBody):
    topic: Topic


class MessageCreate(RequestBody):
    content: MessageContent


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


class ChatTurn(BaseModel):
    learner_message: Message
    tutor_message: Message


class Memory(BaseModel):
    id: int
    learner_id: int
    kind: MemoryKind
    content: str
    status: MemoryStatus
    user_edited: bool
    source_session_id: int | None
    created_at: datetime
    updated_at: datetime


class MemoryUpdate(BaseModel):
    """What ending a session changed in the learner's memory."""

    created: list[Memory] = []
    updated: list[Memory] = []
    archived: list[Memory] = []


class EndSessionResponse(BaseModel):
    session: Session
    memory_update: MemoryUpdate
