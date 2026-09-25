"""Unit tests for the requests-based user-service adapter."""

from __future__ import annotations

from uuid import uuid4

import pytest
import requests
import responses

from app.clients.http_user_repository import HttpUserRepository
from app.services.exceptions import DependencyUnavailableError, ReferenceNotFoundError


@pytest.mark.req("REQ-EVT-B01")
@responses.activate
def test_returns_user_from_configured_url():
    user_id = str(uuid4())
    url = f"http://users.local/api/v1/users/{user_id}"
    responses.get(url, json={"id": user_id, "role": "organizer"}, status=200)

    user = HttpUserRepository("http://users.local/").get_user(user_id)

    assert user["role"] == "organizer"
    assert len(responses.calls) == 1


@pytest.mark.req("REQ-EVT-B01")
@responses.activate
def test_maps_404_to_reference_not_found():
    user_id = str(uuid4())
    responses.get(
        f"http://users.local/api/v1/users/{user_id}",
        json={"error": {"code": "NOT_FOUND", "message": "missing"}},
        status=404,
    )
    with pytest.raises(ReferenceNotFoundError):
        HttpUserRepository("http://users.local").get_user(user_id)


@pytest.mark.req("REQ-EVT-B05")
@pytest.mark.parametrize("status", [400, 500, 503])
@responses.activate
def test_maps_unexpected_statuses_to_dependency_unavailable(status):
    user_id = str(uuid4())
    responses.get(f"http://users.local/api/v1/users/{user_id}", status=status)
    with pytest.raises(DependencyUnavailableError):
        HttpUserRepository("http://users.local").get_user(user_id)


@pytest.mark.req("REQ-EVT-B05")
@responses.activate
def test_maps_invalid_and_unusable_json_to_dependency_unavailable():
    first_id = str(uuid4())
    second_id = str(uuid4())
    responses.get(
        f"http://users.local/api/v1/users/{first_id}",
        body="not-json",
        content_type="application/json",
        status=200,
    )
    responses.get(
        f"http://users.local/api/v1/users/{second_id}",
        json={"id": second_id},
        status=200,
    )
    repository = HttpUserRepository("http://users.local")
    with pytest.raises(DependencyUnavailableError):
        repository.get_user(first_id)
    with pytest.raises(DependencyUnavailableError):
        repository.get_user(second_id)


@pytest.mark.req("REQ-EVT-B05")
def test_uses_two_second_timeout_and_maps_request_errors():
    class FailingSession:
        def get(self, url, timeout):
            assert timeout == 2.0
            raise requests.Timeout("offline")

    with pytest.raises(DependencyUnavailableError):
        HttpUserRepository(
            "http://users.local", session=FailingSession()  # type: ignore[arg-type]
        ).get_user(str(uuid4()))
