"""Contract tests shared by all three EventRepository adapters."""

from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

import pytest


def sample_event(**overrides):
    event = {
        "id": str(uuid4()),
        "title": "Cloud Native Days",
        "description": None,
        "organizer_id": str(uuid4()),
        "venue": "Main Hall",
        "city": "Milano",
        "start_date": "2026-11-01",
        "end_date": "2026-11-02",
        "capacity": 50,
        "price": 99.0,
        "status": "draft",
        "created_at": "2026-09-01T10:00:00.000000Z",
        "updated_at": "2026-09-01T10:00:00.000000Z",
    }
    event.update(overrides)
    return event


@pytest.mark.req("REQ-EVT-N02")
def test_insert_find_and_defensive_copies(event_repository):
    event = sample_event()
    original = deepcopy(event)
    inserted = event_repository.insert(event)
    event["title"] = "Mutated outside"
    inserted["title"] = "Also mutated outside"

    assert event_repository.find_by_id(original["id"]) == original
    assert event_repository.find_by_id("missing") is None


@pytest.mark.req("REQ-EVT-B06")
def test_find_all_applies_status_and_city_filters(event_repository):
    first = sample_event(city="Roma", status="published")
    second = sample_event(city="Roma", status="draft")
    third = sample_event(city="Milano", status="published")
    for event in (first, second, third):
        event_repository.insert(event)

    assert len(event_repository.find_all()) == 3
    assert [item["id"] for item in event_repository.find_all({"status": "published"})] == [
        first["id"],
        third["id"],
    ]
    assert [
        item["id"]
        for item in event_repository.find_all(
            {"status": "published", "city": "Roma"}
        )
    ] == [first["id"]]


@pytest.mark.req("REQ-EVT-N02")
def test_update_and_delete(event_repository):
    event = sample_event()
    event_repository.insert(event)
    replacement = {**event, "title": "Updated Event"}

    assert event_repository.update(event["id"], replacement)["title"] == "Updated Event"
    assert event_repository.update("missing", replacement) is None
    assert event_repository.delete(event["id"]) is True
    assert event_repository.delete(event["id"]) is False
    assert event_repository.find_by_id(event["id"]) is None
