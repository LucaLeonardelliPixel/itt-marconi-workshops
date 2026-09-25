"""Shared fixtures for all event-service tests."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import pytest

from app import Settings, create_app
from app.clients.user_repository import UserRepository
from app.repositories.json_repo import JsonEventRepository
from app.repositories.memory import MemoryEventRepository
from app.repositories.sqlite_repo import SqliteEventRepository
from app.services.exceptions import (
    DependencyUnavailableError,
    ReferenceNotFoundError,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT / "contracts"))
from validator import assert_matches_contract  # noqa: E402


class FakeUserRepository(UserRepository):
    """Configurable user port used by service and route tests."""

    def __init__(self) -> None:
        self.roles: dict[str, str] = {}
        self.missing: set[str] = set()
        self.unavailable = False
        self.calls: list[str] = []

    def get_user(self, user_id: str) -> dict[str, Any]:
        self.calls.append(user_id)
        if self.unavailable:
            raise DependencyUnavailableError()
        if user_id in self.missing:
            raise ReferenceNotFoundError(user_id)
        return {"id": user_id, "role": self.roles.get(user_id, "organizer")}


def contract_response(response) -> dict[str, Any]:
    """Adapt a Flask test response to contracts.validator's dictionary API."""
    body = response.get_json(silent=True) if response.data else None
    return {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "json": body,
    }


@pytest.fixture(params=["memory", "json", "sqlite"])
def event_repository(request, tmp_path):
    if request.param == "memory":
        return MemoryEventRepository()
    if request.param == "json":
        return JsonEventRepository(tmp_path / "events.json")
    return SqliteEventRepository(tmp_path / "events.db")


@pytest.fixture
def fake_users() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def organizer_id() -> str:
    return str(uuid4())


@pytest.fixture
def valid_event_payload(organizer_id: str) -> dict[str, Any]:
    return {
        "title": "Python Architecture Conference",
        "description": "A conference about robust Python systems.",
        "organizer_id": organizer_id,
        "venue": "Auditorium Roma",
        "city": "Roma",
        "start_date": "2026-10-15",
        "end_date": "2026-10-16",
        "capacity": 100,
        "price": 149.0,
    }


@dataclass
class AppContext:
    client: Any
    repository: Any
    users: FakeUserRepository


@pytest.fixture
def app_context(event_repository, fake_users, tmp_path) -> AppContext:
    settings = Settings(data_dir=tmp_path)
    app = create_app(
        event_repository=event_repository,
        user_repository=fake_users,
        settings=settings,
    )
    app.config.update(TESTING=True)
    return AppContext(app.test_client(), event_repository, fake_users)


@pytest.fixture
def assert_contract() -> Callable[[str, str, Any], None]:
    def _assert(method: str, path: str, response: Any) -> None:
        assert_matches_contract("event-service", method, path, contract_response(response))

    return _assert
