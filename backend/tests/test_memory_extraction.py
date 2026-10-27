import json
from typing import get_args

import pytest

from app.llm import LLMError
from app.schemas import MEMORY_KIND_DESCRIPTIONS, MemoryKind
from app.services.memory_extraction import (
    MAX_OPERATIONS,
    ArchiveOperation,
    CreateOperation,
    UpdateOperation,
    parse_operations,
)

CREATE = {"action": "create", "kind": "misconception", "content": "Adds the denominators."}
UPDATE = {"action": "update", "memory_id": 3, "content": "Can add unlike fractions."}
ARCHIVE = {"action": "archive", "memory_id": 5}


def reply(*operations) -> str:
    return json.dumps({"operations": list(operations)})


def test_every_memory_kind_has_a_description():
    assert set(get_args(MemoryKind)) == set(MEMORY_KIND_DESCRIPTIONS)


def test_valid_operations_are_parsed():
    operations = parse_operations(reply(CREATE, UPDATE, ARCHIVE))

    assert operations == [
        CreateOperation(**CREATE),
        UpdateOperation(**UPDATE),
        ArchiveOperation(**ARCHIVE),
    ]


def test_json_wrapped_in_a_code_fence_is_accepted():
    assert parse_operations(f"```json\n{reply(CREATE)}\n```") == [CreateOperation(**CREATE)]


def test_no_operations_is_a_valid_answer():
    assert parse_operations(reply()) == []


@pytest.mark.parametrize(
    "raw",
    ["Sure! Here are the memories:", '{"operations": [', "[]", '{"ops": []}', '{"operations": 3}'],
    ids=["prose", "truncated-json", "array", "wrong-key", "not-a-list"],
)
def test_malformed_replies_raise_llm_error(raw):
    with pytest.raises(LLMError, match="couldn't summarize"):
        parse_operations(raw)


@pytest.mark.parametrize(
    "bad_operation",
    [
        {"action": "create", "kind": "mood", "content": "Seems tired."},
        {"action": "create", "kind": "progress", "content": ""},
        {"action": "create", "kind": "progress", "content": "Line one\nLine two"},
        {"action": "create", "kind": "progress", "content": "x" * 301},
        {"action": "delete", "memory_id": 3},
        {"action": "update", "memory_id": "three", "content": "Can add fractions."},
        {"action": "archive"},
        "not an object",
    ],
)
def test_an_invalid_operation_is_skipped_and_the_others_survive(bad_operation):
    operations = parse_operations(reply(CREATE, bad_operation, ARCHIVE))

    assert operations == [CreateOperation(**CREATE), ArchiveOperation(**ARCHIVE)]


def test_at_most_eight_operations_are_kept():
    many = [{**CREATE, "content": f"Memory number {index}."} for index in range(12)]

    operations = parse_operations(reply(*many))

    assert len(operations) == MAX_OPERATIONS
    assert operations[0].content == "Memory number 0."
