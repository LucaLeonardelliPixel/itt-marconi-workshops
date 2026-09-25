"""RegistrationRepository contract tests for every backend."""

from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

import pytest

from app.repositories.registration_repository import InsertOutcome


def registration(user_id=None, event_id=None, **overrides):
    item = {
        "id": str(uuid4()),
        "user_id": user_id or str(uuid4()),
        "event_id": event_id or str(uuid4()),
        "amount": 149.0,
        "status": "confirmed",
        "created_at": "2026-09-01T10:00:00.000000Z",
        "updated_at": "2026-09-01T10:00:00.000000Z",
    }
    item.update(overrides)
    return item


@pytest.mark.req("REQ-REG-B04")
def test_insert_find_and_defensive_copy(registration_repository):
    item = registration()
    original = deepcopy(item)
    assert (
        registration_repository.insert_confirmed(item, 10)
        is InsertOutcome.CREATED
    )
    item["amount"] = 0
    found = registration_repository.find_by_id(original["id"])
    assert found == original
    found["amount"] = 1
    assert registration_repository.find_by_id(original["id"]) == original
    assert registration_repository.find_by_id("missing") is None


@pytest.mark.req("REQ-REG-B04")
def test_duplicate_precedes_full(registration_repository):
    user_id = str(uuid4())
    event_id = str(uuid4())
    first = registration(user_id, event_id)
    duplicate = registration(user_id, event_id)
    another_user = registration(str(uuid4()), event_id)

    assert registration_repository.insert_confirmed(first, 1) is InsertOutcome.CREATED
    assert (
        registration_repository.insert_confirmed(duplicate, 1)
        is InsertOutcome.ALREADY_REGISTERED
    )
    assert (
        registration_repository.insert_confirmed(another_user, 1)
        is InsertOutcome.EVENT_FULL
    )


@pytest.mark.req("REQ-REG-B07")
def test_cancellation_frees_capacity(registration_repository):
    event_id = str(uuid4())
    first = registration(event_id=event_id)
    second = registration(event_id=event_id)
    registration_repository.insert_confirmed(first, 1)

    updated = registration_repository.update_status(
        first["id"], "cancelled", "2026-09-02T10:00:00.000000Z"
    )
    assert updated["status"] == "cancelled"
    assert registration_repository.count_confirmed(event_id) == 0
    assert registration_repository.insert_confirmed(second, 1) is InsertOutcome.CREATED
    assert registration_repository.count_confirmed(event_id) == 1
    assert registration_repository.update_status("missing", "cancelled", "now") is None


@pytest.mark.req("REQ-REG-E02")
def test_filters_and_delete(registration_repository):
    user_id = str(uuid4())
    event_id = str(uuid4())
    first = registration(user_id, event_id)
    second = registration(str(uuid4()), event_id)
    third = registration(user_id, str(uuid4()))
    for item in (first, second, third):
        registration_repository.insert_confirmed(item, 10)

    result = registration_repository.find_all(
        {"user_id": user_id, "event_id": event_id, "status": "confirmed"}
    )
    assert [item["id"] for item in result] == [first["id"]]
    assert len(registration_repository.find_all()) == 3
    assert registration_repository.delete(first["id"]) is True
    assert registration_repository.delete(first["id"]) is False
