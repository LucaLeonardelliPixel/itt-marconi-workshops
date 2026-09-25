"""Thread-safe in-memory registration repository."""

from __future__ import annotations

from copy import deepcopy
from threading import RLock

from app.repositories.registration_repository import (
    InsertOutcome,
    Registration,
    RegistrationFilters,
    RegistrationRepository,
)


class MemoryRegistrationRepository(RegistrationRepository):
    def __init__(self) -> None:
        self._registrations: dict[str, Registration] = {}
        self._lock = RLock()

    def insert_confirmed(
        self, registration: Registration, capacity: int
    ) -> InsertOutcome:
        with self._lock:
            if any(
                item["user_id"] == registration["user_id"]
                and item["event_id"] == registration["event_id"]
                and item["status"] == "confirmed"
                for item in self._registrations.values()
            ):
                return InsertOutcome.ALREADY_REGISTERED
            confirmed = sum(
                item["event_id"] == registration["event_id"]
                and item["status"] == "confirmed"
                for item in self._registrations.values()
            )
            if confirmed >= capacity:
                return InsertOutcome.EVENT_FULL
            self._registrations[registration["id"]] = deepcopy(registration)
            return InsertOutcome.CREATED

    def find_by_id(self, registration_id: str) -> Registration | None:
        with self._lock:
            item = self._registrations.get(registration_id)
            return deepcopy(item) if item is not None else None

    def find_all(
        self, filters: RegistrationFilters | None = None
    ) -> list[Registration]:
        filters = filters or {}
        with self._lock:
            return [
                deepcopy(item)
                for item in self._registrations.values()
                if all(item.get(key) == value for key, value in filters.items())
            ]

    def update_status(
        self, registration_id: str, status: str, updated_at: str
    ) -> Registration | None:
        with self._lock:
            item = self._registrations.get(registration_id)
            if item is None:
                return None
            item["status"] = status
            item["updated_at"] = updated_at
            return deepcopy(item)

    def delete(self, registration_id: str) -> bool:
        with self._lock:
            return self._registrations.pop(registration_id, None) is not None

    def count_confirmed(self, event_id: str) -> int:
        with self._lock:
            return sum(
                item["event_id"] == event_id and item["status"] == "confirmed"
                for item in self._registrations.values()
            )
