from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

# Rejects text spanning several lines (checked after surrounding whitespace is stripped).
SINGLE_LINE = r"^[^\r\n]+$"

LearnerName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60, pattern=SINGLE_LINE)
]


class RequestBody(BaseModel):
    """Base class for request bodies: unknown fields are rejected, not silently ignored."""

    model_config = ConfigDict(extra="forbid")


class LearnerCreate(RequestBody):
    name: LearnerName


class Learner(BaseModel):
    id: int
    name: str
    created_at: datetime
