"""Flask endpoint and OpenAPI contract tests across all three backends."""

from __future__ import annotations

from uuid import uuid4

import pytest


def create_registration(client, user_id, event_id):
    return client.post(
        "/api/v1/registrations",
        json={"user_id": user_id, "event_id": event_id},
    )


@pytest.mark.req("REQ-REG-E08")
def test_health_contract(app_context, assert_contract):
    response = app_context.client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "service": "registration-service",
    }
    assert_contract("GET", "/health", response)


@pytest.mark.req("REQ-REG-E01")
def test_create_contract_location_and_amount(
    app_context, fake_events, user_id, assert_contract
):
    event_id = str(uuid4())
    fake_events.add(event_id, price=79.5)
    response = create_registration(app_context.client, user_id, event_id)
    assert response.status_code == 201
    body = response.get_json()
    assert body["status"] == "confirmed"
    assert body["amount"] == 79.5
    assert response.headers["Location"] == f"/api/v1/registrations/{body['id']}"
    assert_contract("POST", "/api/v1/registrations", response)


@pytest.mark.req("REQ-REG-E01")
def test_create_error_contracts(app_context, fake_events, user_id, assert_contract):
    malformed = app_context.client.post(
        "/api/v1/registrations", data='{"user_id":', content_type="application/json"
    )
    assert malformed.status_code == 400
    assert_contract("POST", "/api/v1/registrations", malformed)

    invalid = app_context.client.post(
        "/api/v1/registrations", json={"user_id": user_id}
    )
    assert invalid.status_code == 422
    assert invalid.get_json()["error"]["code"] == "VALIDATION_ERROR"
    assert_contract("POST", "/api/v1/registrations", invalid)

    event_id = str(uuid4())
    fake_events.add(event_id, status="draft")
    closed = create_registration(app_context.client, user_id, event_id)
    assert closed.status_code == 422
    assert closed.get_json()["error"]["code"] == "EVENT_NOT_OPEN"
    assert_contract("POST", "/api/v1/registrations", closed)


@pytest.mark.req("REQ-REG-B04")
def test_duplicate_and_capacity_contracts(
    app_context, fake_events, user_id, assert_contract
):
    event_id = str(uuid4())
    fake_events.add(event_id, capacity=1)
    assert create_registration(app_context.client, user_id, event_id).status_code == 201

    duplicate = create_registration(app_context.client, user_id, event_id)
    assert duplicate.status_code == 409
    assert duplicate.get_json()["error"]["code"] == "ALREADY_REGISTERED"
    assert_contract("POST", "/api/v1/registrations", duplicate)

    full = create_registration(app_context.client, str(uuid4()), event_id)
    assert full.status_code == 409
    assert full.get_json()["error"]["code"] == "EVENT_FULL"
    assert_contract("POST", "/api/v1/registrations", full)


@pytest.mark.req("REQ-REG-B01")
def test_reference_and_dependency_contracts(
    app_context, fake_users, fake_events, user_id, assert_contract
):
    event_id = str(uuid4())
    fake_events.add(event_id)
    fake_users.missing.add(user_id)
    missing = create_registration(app_context.client, user_id, event_id)
    assert missing.status_code == 422
    assert missing.get_json()["error"]["code"] == "REFERENCE_NOT_FOUND"
    assert_contract("POST", "/api/v1/registrations", missing)

    fake_users.missing.clear()
    fake_events.unavailable = True
    unavailable = create_registration(app_context.client, user_id, event_id)
    assert unavailable.status_code == 503
    assert unavailable.get_json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
    assert_contract("POST", "/api/v1/registrations", unavailable)


@pytest.mark.req("REQ-REG-E02")
def test_list_contract_filters_and_pagination(
    app_context, fake_events, user_id, assert_contract
):
    first_event = str(uuid4())
    second_event = str(uuid4())
    fake_events.add(first_event)
    fake_events.add(second_event)
    create_registration(app_context.client, user_id, first_event)
    create_registration(app_context.client, user_id, second_event)

    response = app_context.client.get(
        f"/api/v1/registrations?user_id={user_id}&event_id={first_event}&status=confirmed&page=1&page_size=1"
    )
    assert response.status_code == 200
    assert response.get_json()["total"] == 1
    assert_contract("GET", "/api/v1/registrations?status=confirmed", response)

    invalid = app_context.client.get("/api/v1/registrations?page=0")
    assert invalid.status_code == 422
    assert_contract("GET", "/api/v1/registrations?page=0", invalid)


@pytest.mark.req("REQ-REG-E03")
def test_get_and_not_found_contract(
    app_context, fake_events, user_id, assert_contract
):
    event_id = str(uuid4())
    fake_events.add(event_id)
    created = create_registration(app_context.client, user_id, event_id).get_json()
    path = f"/api/v1/registrations/{created['id']}"
    response = app_context.client.get(path)
    assert response.status_code == 200
    assert_contract("GET", path, response)

    missing_path = f"/api/v1/registrations/{uuid4()}"
    missing = app_context.client.get(missing_path)
    assert missing.status_code == 404
    assert_contract("GET", missing_path, missing)


@pytest.mark.req("REQ-REG-E04")
def test_patch_cancels_and_releases_seat(
    app_context, fake_events, user_id, assert_contract
):
    event_id = str(uuid4())
    fake_events.add(event_id, capacity=1)
    created = create_registration(app_context.client, user_id, event_id).get_json()
    path = f"/api/v1/registrations/{created['id']}"

    response = app_context.client.patch(path, json={"status": "cancelled"})
    assert response.status_code == 200
    assert response.get_json()["status"] == "cancelled"
    assert_contract("PATCH", path, response)

    invalid = app_context.client.patch(path, json={"status": "confirmed"})
    assert invalid.status_code == 422
    assert invalid.get_json()["error"]["code"] == "INVALID_STATUS_TRANSITION"
    assert_contract("PATCH", path, invalid)

    accepted = create_registration(app_context.client, str(uuid4()), event_id)
    assert accepted.status_code == 201


@pytest.mark.req("REQ-REG-B08")
def test_stats_success_missing_and_validation_contract(
    app_context, fake_events, user_id, assert_contract
):
    event_id = str(uuid4())
    fake_events.add(event_id, capacity=2)
    create_registration(app_context.client, user_id, event_id)

    response = app_context.client.get(
        f"/api/v1/registrations/stats?event_id={event_id}"
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "event_id": event_id,
        "capacity": 2,
        "confirmed": 1,
        "available": 1,
    }
    assert_contract("GET", f"/api/v1/registrations/stats?event_id={event_id}", response)

    missing_id = str(uuid4())
    fake_events.missing.add(missing_id)
    missing = app_context.client.get(
        f"/api/v1/registrations/stats?event_id={missing_id}"
    )
    assert missing.status_code == 404
    assert_contract("GET", "/api/v1/registrations/stats", missing)

    invalid = app_context.client.get("/api/v1/registrations/stats")
    assert invalid.status_code == 422
    assert_contract("GET", "/api/v1/registrations/stats", invalid)


@pytest.mark.req("REQ-REG-E05")
def test_delete_contract(app_context, fake_events, user_id, assert_contract):
    event_id = str(uuid4())
    fake_events.add(event_id)
    created = create_registration(app_context.client, user_id, event_id).get_json()
    path = f"/api/v1/registrations/{created['id']}"
    response = app_context.client.delete(path)
    assert response.status_code == 204
    assert response.data == b""
    assert_contract("DELETE", path, response)

    missing = app_context.client.delete(path)
    assert missing.status_code == 404
    assert_contract("DELETE", path, missing)


@pytest.mark.req("REQ-REG-E07")
def test_put_returns_contract_compliant_405_without_state_access(
    app_context, assert_contract
):
    path = f"/api/v1/registrations/{uuid4()}"
    response = app_context.client.put(path, json={"status": "confirmed"})
    assert response.status_code == 405
    assert response.get_json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert_contract("PUT", path, response)
