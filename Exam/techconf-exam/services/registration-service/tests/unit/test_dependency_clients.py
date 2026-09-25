"""Unit tests for user-service and event-service HTTP clients."""

from __future__ import annotations

from uuid import uuid4

import pytest
import requests
import responses

from app.clients.event_client import HttpEventClient
from app.clients.user_client import HttpUserClient
from app.services.exceptions import DependencyUnavailableError, UpstreamNotFoundError


@pytest.mark.req("REQ-REG-B01")
@responses.activate
def test_user_client_success_and_trailing_slash():
    user_id = str(uuid4())
    url = f"http://users.local/api/v1/users/{user_id}"
    responses.get(url, json={"id": user_id, "role": "attendee"}, status=200)
    assert HttpUserClient("http://users.local/").get_user(user_id)["id"] == user_id


@pytest.mark.req("REQ-REG-B02")
@responses.activate
def test_event_client_success():
    event_id = str(uuid4())
    url = f"http://events.local/api/v1/events/{event_id}"
    responses.get(
        url,
        json={
            "id": event_id,
            "status": "published",
            "capacity": 5,
            "price": 25.0,
        },
        status=200,
    )
    assert HttpEventClient("http://events.local").get_event(event_id)["price"] == 25.0


@pytest.mark.req("REQ-REG-B01")
@pytest.mark.parametrize("kind", ["user", "event"])
@responses.activate
def test_clients_map_404_to_neutral_not_found(kind):
    resource_id = str(uuid4())
    if kind == "user":
        url = f"http://dependency.local/api/v1/users/{resource_id}"
        client = HttpUserClient("http://dependency.local")
        call = client.get_user
    else:
        url = f"http://dependency.local/api/v1/events/{resource_id}"
        client = HttpEventClient("http://dependency.local")
        call = client.get_event
    responses.get(url, status=404)
    with pytest.raises(UpstreamNotFoundError):
        call(resource_id)


@pytest.mark.req("REQ-REG-B09")
@pytest.mark.parametrize("kind", ["user", "event"])
@pytest.mark.parametrize("status", [400, 500, 503])
@responses.activate
def test_clients_map_unexpected_statuses(kind, status):
    resource_id = str(uuid4())
    resource = "users" if kind == "user" else "events"
    responses.get(
        f"http://dependency.local/api/v1/{resource}/{resource_id}", status=status
    )
    client = (
        HttpUserClient("http://dependency.local")
        if kind == "user"
        else HttpEventClient("http://dependency.local")
    )
    with pytest.raises(DependencyUnavailableError):
        (client.get_user if kind == "user" else client.get_event)(resource_id)


@pytest.mark.req("REQ-REG-B09")
@responses.activate
def test_clients_reject_invalid_json_and_unusable_objects():
    user_id = str(uuid4())
    event_id = str(uuid4())
    responses.get(
        f"http://dependency.local/api/v1/users/{user_id}",
        body="invalid",
        content_type="application/json",
        status=200,
    )
    responses.get(
        f"http://dependency.local/api/v1/events/{event_id}",
        json={"id": event_id, "status": "published", "capacity": True, "price": 2},
        status=200,
    )
    with pytest.raises(DependencyUnavailableError):
        HttpUserClient("http://dependency.local").get_user(user_id)
    with pytest.raises(DependencyUnavailableError):
        HttpEventClient("http://dependency.local").get_event(event_id)


@pytest.mark.req("REQ-REG-B09")
@pytest.mark.parametrize("kind", ["user", "event"])
def test_clients_use_two_second_timeout_and_map_request_errors(kind):
    class FailingSession:
        def get(self, url, timeout):
            assert timeout == 2.0
            raise requests.Timeout("offline")

    client = (
        HttpUserClient("http://dependency.local", session=FailingSession())
        if kind == "user"
        else HttpEventClient("http://dependency.local", session=FailingSession())
    )
    with pytest.raises(DependencyUnavailableError):
        (client.get_user if kind == "user" else client.get_event)(str(uuid4()))
