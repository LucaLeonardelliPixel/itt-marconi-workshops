"""Shared fixtures for registration-service tests."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import pytest

from app import Settings, create_app
from app.clients.event_client import EventClient
from app.clients.user_client import UserClient
from app.repositories.json_repo import JsonRegistrationRepository
from app.repositories.memory import MemoryRegistrationRepository
from app.repositories.sqlite_repo import SqliteRegistrationRepository
from app.services.exceptions import DependencyUnavailableError, UpstreamNotFoundError

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT / "contracts"))
from validator import assert_matches_contract  # noqa: E402


class FakeUserClient(UserClient):
    def __init__(self) -> None:
        self.missing: set[str] = set()
        self.unavailable = False
        self.calls: list[str] = []

    def get_user(self, user_id: str) -> dict[str, Any]:
        self.calls.append(user_id)
        if self.unavailable:
            raise DependencyUnavailableError("user-service")
        if user_id in self.missing:
            raise UpstreamNotFoundError("user-service", user_id)
        return {"id": user_id, "role": "attendee"}


class FakeEventClient(EventClient):
    def __init__(self) -> None:
        self.events: dict[str, dict[str, Any]] = {}
        self.missing: set[str] = set()
        self.unavailable = False
        self.calls: list[str] = []

    def add(
        self,
        event_id: str,
        *,
        status: str = "published",
        capacity: int = 10,
        price: float = 149.0,
    ) -> None:
        self.events[event_id] = {
            "id": event_id,
            "status": status,
            "capacity": capacity,
            "price": price,
        }

    def get_event(self, event_id: str) -> dict[str, Any]:
        self.calls.append(event_id)
        if self.unavailable:
            raise DependencyUnavailableError("event-service")
        if event_id in self.missing or event_id not in self.events:
            raise UpstreamNotFoundError("event-service", event_id)
        return dict(self.events[event_id])


def contract_response(response) -> dict[str, Any]:
    return {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "json": response.get_json(silent=True) if response.data else None,
    }


@pytest.fixture(params=["memory", "json", "sqlite"])
def registration_repository(request, tmp_path):
    if request.param == "memory":
        return MemoryRegistrationRepository()
    if request.param == "json":
        return JsonRegistrationRepository(tmp_path / "registrations.json")
    return SqliteRegistrationRepository(tmp_path / "registrations.db")


@pytest.fixture
def fake_users() -> FakeUserClient:
    return FakeUserClient()


@pytest.fixture
def fake_events() -> FakeEventClient:
    return FakeEventClient()


@pytest.fixture
def user_id() -> str:
    return str(uuid4())


@pytest.fixture
def event_id(fake_events: FakeEventClient) -> str:
    value = str(uuid4())
    fake_events.add(value)
    return value


@dataclass
class AppContext:
    client: Any
    repository: Any
    users: FakeUserClient
    events: FakeEventClient


@pytest.fixture
def app_context(registration_repository, fake_users, fake_events, tmp_path) -> AppContext:
    app = create_app(
        repository=registration_repository,
        user_client=fake_users,
        event_client=fake_events,
        settings=Settings(data_dir=tmp_path),
    )
    app.config.update(TESTING=True)
    return AppContext(
        app.test_client(), registration_repository, fake_users, fake_events
    )


@pytest.fixture
def assert_contract() -> Callable[[str, str, Any], None]:
    def _assert(method: str, path: str, response: Any) -> None:
        assert_matches_contract(
            "registration-service", method, path, contract_response(response)
        )

    return _assert
