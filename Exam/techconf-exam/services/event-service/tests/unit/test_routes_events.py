"""Contract-focused Flask route tests across all persistence backends."""

from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

import pytest


@pytest.mark.req("REQ-EVT-E07")
def test_health_contract(app_context, assert_contract):
    response = app_context.client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "service": "event-service"}
    assert_contract("GET", "/health", response)


@pytest.mark.req("REQ-EVT-E01")
def test_create_event_contract_and_location(
    app_context, valid_event_payload, assert_contract
):
    response = app_context.client.post("/api/v1/events", json=valid_event_payload)
    assert response.status_code == 201
    body = response.get_json()
    assert body["status"] == "draft"
    assert response.headers["Location"] == f"/api/v1/events/{body['id']}"
    assert_contract("POST", "/api/v1/events", response)


@pytest.mark.req("REQ-EVT-E01")
def test_create_malformed_and_validation_errors(
    app_context, valid_event_payload, assert_contract
):
    malformed = app_context.client.post(
        "/api/v1/events", data='{"title":', content_type="application/json"
    )
    assert malformed.status_code == 400
    assert malformed.get_json()["error"]["code"] == "MALFORMED_JSON"
    assert_contract("POST", "/api/v1/events", malformed)

    invalid = app_context.client.post(
        "/api/v1/events", json={**valid_event_payload, "capacity": 0}
    )
    assert invalid.status_code == 422
    assert invalid.get_json()["error"]["code"] == "VALIDATION_ERROR"
    assert_contract("POST", "/api/v1/events", invalid)


@pytest.mark.req("REQ-EVT-B01")
def test_create_maps_organizer_errors(app_context, valid_event_payload, assert_contract):
    organizer_id = valid_event_payload["organizer_id"]
    app_context.users.missing.add(organizer_id)
    missing = app_context.client.post("/api/v1/events", json=valid_event_payload)
    assert missing.status_code == 422
    assert missing.get_json()["error"]["code"] == "REFERENCE_NOT_FOUND"
    assert_contract("POST", "/api/v1/events", missing)

    app_context.users.missing.clear()
    app_context.users.roles[organizer_id] = "attendee"
    wrong_role = app_context.client.post("/api/v1/events", json=valid_event_payload)
    assert wrong_role.status_code == 422
    assert wrong_role.get_json()["error"]["code"] == "INVALID_ORGANIZER"
    assert_contract("POST", "/api/v1/events", wrong_role)

    app_context.users.roles.clear()
    app_context.users.unavailable = True
    unavailable = app_context.client.post("/api/v1/events", json=valid_event_payload)
    assert unavailable.status_code == 503
    assert unavailable.get_json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
    assert_contract("POST", "/api/v1/events", unavailable)


@pytest.mark.req("REQ-EVT-E02")
def test_list_events_filters_and_paginates(
    app_context, valid_event_payload, assert_contract
):
    app_context.client.post(
        "/api/v1/events", json={**valid_event_payload, "title": "Draft Roma"}
    )
    app_context.client.post(
        "/api/v1/events",
        json={
            **valid_event_payload,
            "title": "Published Roma",
            "status": "published",
        },
    )
    app_context.client.post(
        "/api/v1/events",
        json={
            **valid_event_payload,
            "title": "Published Milano",
            "city": "Milano",
            "status": "published",
        },
    )

    response = app_context.client.get(
        "/api/v1/events?status=published&city=Roma&page=1&page_size=1"
    )
    assert response.status_code == 200
    assert response.get_json()["total"] == 1
    assert response.get_json()["items"][0]["title"] == "Published Roma"
    assert_contract("GET", "/api/v1/events?status=published", response)

    invalid = app_context.client.get("/api/v1/events?page=0")
    assert invalid.status_code == 422
    assert_contract("GET", "/api/v1/events?page=0", invalid)


@pytest.mark.req("REQ-EVT-E03")
def test_get_event_and_not_found_contract(
    app_context, valid_event_payload, assert_contract
):
    created = app_context.client.post("/api/v1/events", json=valid_event_payload).get_json()
    path = f"/api/v1/events/{created['id']}"
    response = app_context.client.get(path)
    assert response.status_code == 200
    assert response.get_json()["id"] == created["id"]
    assert_contract("GET", path, response)

    missing_path = f"/api/v1/events/{uuid4()}"
    missing = app_context.client.get(missing_path)
    assert missing.status_code == 404
    assert missing.get_json()["error"]["code"] == "NOT_FOUND"
    assert_contract("GET", missing_path, missing)


@pytest.mark.req("REQ-EVT-E04")
def test_replace_event_contract(app_context, valid_event_payload, assert_contract):
    created = app_context.client.post("/api/v1/events", json=valid_event_payload).get_json()
    replacement = {
        **valid_event_payload,
        "title": "Replacement Conference",
        "status": "published",
    }
    path = f"/api/v1/events/{created['id']}"
    response = app_context.client.put(path, json=replacement)
    assert response.status_code == 200
    assert response.get_json()["title"] == "Replacement Conference"
    assert response.get_json()["created_at"] == created["created_at"]
    assert_contract("PUT", path, response)

    missing_path = f"/api/v1/events/{uuid4()}"
    missing = app_context.client.put(missing_path, json=replacement)
    assert missing.status_code == 404
    assert_contract("PUT", missing_path, missing)


@pytest.mark.req("REQ-EVT-E05")
def test_patch_event_and_invalid_transition_contract(
    app_context, valid_event_payload, assert_contract
):
    created = app_context.client.post("/api/v1/events", json=valid_event_payload).get_json()
    path = f"/api/v1/events/{created['id']}"
    response = app_context.client.patch(path, json={"status": "published"})
    assert response.status_code == 200
    assert response.get_json()["status"] == "published"
    assert_contract("PATCH", path, response)

    invalid = app_context.client.patch(path, json={"status": "draft"})
    assert invalid.status_code == 422
    assert invalid.get_json()["error"]["code"] == "INVALID_STATUS_TRANSITION"
    assert_contract("PATCH", path, invalid)


@pytest.mark.req("REQ-EVT-E06")
def test_delete_event_and_not_found_contract(
    app_context, valid_event_payload, assert_contract
):
    created = app_context.client.post("/api/v1/events", json=valid_event_payload).get_json()
    path = f"/api/v1/events/{created['id']}"
    response = app_context.client.delete(path)
    assert response.status_code == 204
    assert response.data == b""
    assert_contract("DELETE", path, response)

    missing = app_context.client.delete(path)
    assert missing.status_code == 404
    assert_contract("DELETE", path, missing)
