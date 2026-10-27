"""Turn the extractor LLM's JSON reply into validated memory operations."""

import json
import logging
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from app.llm import LLMError
from app.schemas import MemoryContent, MemoryKind

logger = logging.getLogger(__name__)

MAX_OPERATIONS = 8
INVALID_REPLY = (
    "The tutor couldn't summarize this session. Your session is still open; try ending it again."
)


class CreateOperation(BaseModel):
    action: Literal["create"]
    kind: MemoryKind
    content: MemoryContent


class UpdateOperation(BaseModel):
    action: Literal["update"]
    memory_id: int
    content: MemoryContent


class ArchiveOperation(BaseModel):
    action: Literal["archive"]
    memory_id: int


MemoryOperation = Annotated[
    CreateOperation | UpdateOperation | ArchiveOperation, Field(discriminator="action")
]
_operation_adapter: TypeAdapter[MemoryOperation] = TypeAdapter(MemoryOperation)


def parse_operations(raw: str) -> list[MemoryOperation]:
    """Validate each operation on its own: one bad operation is skipped, the rest still apply.

    A reply that isn't a JSON object with an "operations" list raises LLMError, so the
    session stays open and nothing changes.
    """
    text = raw.strip()
    if text.startswith("```"):  # some models wrap JSON in a Markdown code fence
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("The memory update was not valid JSON: %.300r", raw)
        raise LLMError(INVALID_REPLY) from exc
    if not isinstance(data, dict) or not isinstance(data.get("operations"), list):
        logger.warning("The memory update had no 'operations' list: %.300r", raw)
        raise LLMError(INVALID_REPLY)

    operations: list[MemoryOperation] = []
    for item in data["operations"]:
        try:
            operations.append(_operation_adapter.validate_python(item))
        except ValidationError as exc:
            logger.warning("Skipping an invalid memory operation %.200r: %s", item, exc)
    if len(operations) > MAX_OPERATIONS:
        logger.warning("Keeping the first %d of %d operations", MAX_OPERATIONS, len(operations))
    return operations[:MAX_OPERATIONS]
