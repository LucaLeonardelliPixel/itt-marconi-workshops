"""RegistrationService business-rule tests."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.repositories.memory import MemoryRegistrationRepository
from app.services.exceptions import (
    AlreadyRegisteredError,
    DependencyUnavailableError,
    EventFullError,
    EventNotOpenError,
    InvalidStatusTransitionError,
    NotFoundError,
    ReferenceNotFoundError,
    ValidationError,
)
from app.services.registration_service import RegistrationService


@pytest.fixture
def service(fake_users, fake_events):
    return RegistrationService(MemoryRegistrationRepository(), fake_users, fake_events)


@pytest.mark.req("REQ-REG-B06")
def test_create_generates_confirmed_registration_and_copies_price(
    service, event_id, user_id
):
    created = service.create({"user_id": user_id, "event_id": event_id})
    assert UUID(created["id"]).version == 4
    assert created["status"] == "confirmed"
    assert created["amount"] == 149.0
    assert created["created_at"] == created["updated_at"]


@pytest.mark.req("REQ-REG-B01")
def test_create_maps_missing_references(
    service, fake_users, fake_events, event_id, user_id
):
    fake_users.missing.add(user_id)
    with pytest.raises(ReferenceNotFoundError):
        service.create({"user_id": user_id, "event_id": event_id})

    fake_users.missing.clear()
    fake_events.missing.add(event_id)
    with pytest.raises(ReferenceNotFoundError):
        service.create({"user_id": user_id, "event_id": event_id})


@pytest.mark.req("REQ-REG-B09")
def test_create_propagates_dependency_unavailable(
    service, fake_users, fake_events, event_id, user_id
):
    fake_users.unavailable = True
    with pytest.raises(DependencyUnavailableError):
        service.create({"user_id": user_id, "event_id": event_id})
    fake_users.unavailable = False
    fake_events.unavailable = True
    with pytest.raises(DependencyUnavailableError):
        service.create({"user_id": user_id, "event_id": event_id})


@pytest.mark.req("REQ-REG-B03")
def test_create_rejects_event_not_open(service, fake_events, event_id, user_id):
    fake_events.events[event_id]["status"] = "draft"
    with pytest.raises(EventNotOpenError):
        service.create({"user_id": user_id, "event_id": event_id})


@pytest.mark.req("REQ-REG-E01")
@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"user_id": "bad", "event_id": "bad"},
        {"user_id": str(uuid4())},
        {
            "user_id": str(uuid4()),
            "event_id": str(uuid4()),
            "amount": 0,
        },
    ],
)
def test_create_rejects_invalid_bodies(service, payload):
    with pytest.raises(ValidationError):
        service.create(payload)  # type: ignore[arg-type]


@pytest.mark.req("REQ-REG-B04")
def test_duplicate_then_cancel_allows_new_registration(
    service, event_id, user_id
):
    first = service.create({"user_id": user_id, "event_id": event_id})
    with pytest.raises(AlreadyRegisteredError):
        service.create({"user_id": user_id, "event_id": event_id})
    service.cancel(first["id"], {"status": "cancelled"})
    second = service.create({"user_id": user_id, "event_id": event_id})
    assert second["id"] != first["id"]


@pytest.mark.req("REQ-REG-B05")
def test_capacity_blocks_next_user(service, fake_events, event_id, user_id):
    fake_events.events[event_id]["capacity"] = 1
    service.create({"user_id": user_id, "event_id": event_id})
    with pytest.raises(EventFullError):
        service.create({"user_id": str(uuid4()), "event_id": event_id})


@pytest.mark.req("REQ-REG-E02")
def test_list_filters_and_paginates(service, fake_events, event_id, user_id):
    other_event = str(uuid4())
    fake_events.add(other_event)
    service.create({"user_id": user_id, "event_id": event_id})
    service.create({"user_id": user_id, "event_id": other_event})

    page = service.list_registrations(
        {"event_id": event_id, "status": "confirmed"}, "1", "1"
    )
    assert page["total"] == 1
    assert page["items"][0]["event_id"] == event_id
    assert service.list_registrations(page=99)["items"] == []


@pytest.mark.req("REQ-REG-E02")
@pytest.mark.parametrize(
    ("filters", "page", "size"),
    [
        ({"other": "x"}, 1, 20),
        ({"user_id": "bad"}, 1, 20),
        ({"event_id": "bad"}, 1, 20),
        ({"status": "pending"}, 1, 20),
        ({}, 0, 20),
        ({}, 1, 101),
        ({}, "one", 20),
        ({}, "1.5", 20),
        ({}, True, 20),
    ],
)
def test_list_rejects_invalid_parameters(service, filters, page, size):
    with pytest.raises(ValidationError):
        service.list_registrations(filters, page, size)


@pytest.mark.req("REQ-REG-B07")
def test_cancel_rejects_invalid_bodies_and_transitions(service, event_id, user_id):
    created = service.create({"user_id": user_id, "event_id": event_id})
    with pytest.raises(ValidationError):
        service.cancel(created["id"], {})
    with pytest.raises(ValidationError):
        service.cancel(created["id"], {"status": "cancelled", "extra": True})
    with pytest.raises(InvalidStatusTransitionError):
        service.cancel(created["id"], {"status": "confirmed"})
    service.cancel(created["id"], {"status": "cancelled"})
    with pytest.raises(InvalidStatusTransitionError):
        service.cancel(created["id"], {"status": "cancelled"})


@pytest.mark.req("REQ-REG-B08")
def test_stats_counts_confirmed_and_maps_missing_event(
    service, fake_events, event_id, user_id
):
    fake_events.events[event_id]["capacity"] = 2
    created = service.create({"user_id": user_id, "event_id": event_id})
    assert service.stats(event_id) == {
        "event_id": event_id,
        "capacity": 2,
        "confirmed": 1,
        "available": 1,
    }
    service.cancel(created["id"], {"status": "cancelled"})
    assert service.stats(event_id)["available"] == 2
    missing = str(uuid4())
    fake_events.missing.add(missing)
    with pytest.raises(NotFoundError):
        service.stats(missing)
    with pytest.raises(ValidationError):
        service.stats("bad")


@pytest.mark.req("REQ-REG-E03")
def test_get_delete_missing_and_local_calls_do_not_use_dependencies(
    service, fake_users, fake_events
):
    unknown = str(uuid4())
    with pytest.raises(NotFoundError):
        service.get(unknown)
    with pytest.raises(NotFoundError):
        service.delete(unknown)
    service.list_registrations()
    assert fake_users.calls == []
    assert fake_events.calls == []
