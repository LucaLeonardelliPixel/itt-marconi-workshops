"""Unit tests for EventService business rules."""

from __future__ import annotations

from copy import deepcopy
from uuid import UUID, uuid4

import pytest

from app.repositories.memory import MemoryEventRepository
from app.services.event_service import EventService
from app.services.exceptions import (
    DependencyUnavailableError,
    InvalidOrganizerError,
    InvalidStatusTransitionError,
    NotFoundError,
    ReferenceNotFoundError,
    ValidationError,
)


@pytest.fixture
def service(fake_users):
    return EventService(MemoryEventRepository(), fake_users)


@pytest.mark.req("REQ-EVT-E01")
def test_create_generates_metadata_and_defaults(service, valid_event_payload):
    event = service.create(valid_event_payload)

    assert UUID(event["id"]).version == 4
    assert event["status"] == "draft"
    assert event["created_at"].endswith("Z")
    assert event["updated_at"] == event["created_at"]
    assert event["description"] == valid_event_payload["description"]


@pytest.mark.req("REQ-EVT-B01")
def test_create_propagates_missing_and_unavailable_user(
    service, fake_users, valid_event_payload
):
    fake_users.missing.add(valid_event_payload["organizer_id"])
    with pytest.raises(ReferenceNotFoundError):
        service.create(valid_event_payload)

    fake_users.missing.clear()
    fake_users.unavailable = True
    with pytest.raises(DependencyUnavailableError):
        service.create(valid_event_payload)


@pytest.mark.req("REQ-EVT-B02")
def test_create_rejects_non_organizer(service, fake_users, valid_event_payload):
    fake_users.roles[valid_event_payload["organizer_id"]] = "attendee"
    with pytest.raises(InvalidOrganizerError):
        service.create(valid_event_payload)


@pytest.mark.req("REQ-EVT-B03")
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "ab"),
        ("title", "x" * 121),
        ("description", "x" * 2001),
        ("organizer_id", "not-a-uuid"),
        ("venue", "x" * 101),
        ("city", "x" * 61),
        ("start_date", "2026/10/15"),
        ("start_date", "2026-02-30"),
        ("capacity", 0),
        ("capacity", 10001),
        ("capacity", True),
        ("price", -0.01),
        ("price", True),
        ("status", "archived"),
    ],
)
def test_create_rejects_invalid_fields(service, valid_event_payload, field, value):
    payload = {**valid_event_payload, field: value}
    with pytest.raises(ValidationError):
        service.create(payload)


@pytest.mark.req("REQ-EVT-E01")
def test_create_rejects_missing_extra_and_non_object(service, valid_event_payload):
    missing = dict(valid_event_payload)
    del missing["title"]
    with pytest.raises(ValidationError):
        service.create(missing)
    with pytest.raises(ValidationError):
        service.create({**valid_event_payload, "id": str(uuid4())})
    with pytest.raises(ValidationError):
        service.create([])  # type: ignore[arg-type]


@pytest.mark.req("REQ-EVT-B03")
def test_create_rejects_reversed_dates(service, valid_event_payload):
    payload = {
        **valid_event_payload,
        "start_date": "2026-10-17",
        "end_date": "2026-10-16",
    }
    with pytest.raises(ValidationError):
        service.create(payload)


@pytest.mark.req("REQ-EVT-B06")
def test_list_filters_then_paginates(service, valid_event_payload):
    service.create({**valid_event_payload, "title": "Roma Draft", "city": "Roma"})
    service.create(
        {
            **valid_event_payload,
            "title": "Roma Published",
            "city": "Roma",
            "status": "published",
        }
    )
    service.create(
        {
            **valid_event_payload,
            "title": "Milan Published",
            "city": "Milano",
            "status": "published",
        }
    )

    result = service.list_events(
        {"status": "published", "city": "Roma"}, page="1", page_size="1"
    )
    assert result["total"] == 1
    assert result["page"] == 1
    assert result["items"][0]["title"] == "Roma Published"
    assert service.list_events(page=99, page_size=20)["items"] == []


@pytest.mark.req("REQ-EVT-E02")
@pytest.mark.parametrize(
    ("filters", "page", "page_size"),
    [
        ({"status": "unknown"}, 1, 20),
        ({"other": "x"}, 1, 20),
        ({"city": 3}, 1, 20),
        ({}, 0, 20),
        ({}, 1, 0),
        ({}, 1, 101),
        ({}, "one", 20),
        ({}, "1.5", 20),
        ({}, True, 20),
    ],
)
def test_list_rejects_invalid_parameters(service, filters, page, page_size):
    with pytest.raises(ValidationError):
        service.list_events(filters, page, page_size)


@pytest.mark.req("REQ-EVT-B04")
def test_update_supports_allowed_transitions_and_rejects_reverse(
    service, valid_event_payload
):
    created = service.create(valid_event_payload)
    published = service.update(created["id"], {"status": "published"})
    assert published["status"] == "published"
    cancelled = service.update(created["id"], {"status": "cancelled"})
    assert cancelled["status"] == "cancelled"
    with pytest.raises(InvalidStatusTransitionError):
        service.update(created["id"], {"status": "draft"})


@pytest.mark.req("REQ-EVT-E05")
def test_partial_update_preserves_immutable_fields_and_validates_changed_organizer(
    service, fake_users, valid_event_payload
):
    created = service.create(valid_event_payload)
    replacement_organizer = str(uuid4())
    updated = service.update(
        created["id"],
        {"title": "Updated Conference", "organizer_id": replacement_organizer},
    )
    assert updated["id"] == created["id"]
    assert updated["created_at"] == created["created_at"]
    assert updated["title"] == "Updated Conference"
    assert replacement_organizer in fake_users.calls
    with pytest.raises(ValidationError):
        service.update(created["id"], {})


@pytest.mark.req("REQ-EVT-E04")
def test_replace_preserves_identity_and_validates_transition(service, valid_event_payload):
    created = service.create(valid_event_payload)
    replacement = {
        **valid_event_payload,
        "title": "Fully Replaced Conference",
        "status": "published",
    }
    updated = service.replace(created["id"], replacement)
    assert updated["id"] == created["id"]
    assert updated["created_at"] == created["created_at"]
    assert updated["title"] == "Fully Replaced Conference"

    without_status = deepcopy(valid_event_payload)
    with pytest.raises(InvalidStatusTransitionError):
        service.replace(created["id"], without_status)


@pytest.mark.req("REQ-EVT-E03")
def test_get_and_delete_missing_raise_not_found(service):
    unknown = str(uuid4())
    with pytest.raises(NotFoundError):
        service.get(unknown)
    with pytest.raises(NotFoundError):
        service.delete(unknown)
