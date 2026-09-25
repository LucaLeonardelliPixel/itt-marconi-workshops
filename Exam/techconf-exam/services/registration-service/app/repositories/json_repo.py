"""Atomic JSON-file registration repository."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from threading import RLock

from app.repositories.registration_repository import (
    InsertOutcome,
    Registration,
    RegistrationFilters,
    RegistrationRepository,
)


class JsonRegistrationRepository(RegistrationRepository):
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        if not self._path.exists():
            self._write_unlocked({})

    def _read_unlocked(self) -> dict[str, Registration]:
        try:
            with self._path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_unlocked(self, registrations: dict[str, Registration]) -> None:
        temporary = self._path.with_suffix(self._path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(registrations, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self._path)

    def insert_confirmed(
        self, registration: Registration, capacity: int
    ) -> InsertOutcome:
        with self._lock:
            registrations = self._read_unlocked()
            if any(
                item["user_id"] == registration["user_id"]
                and item["event_id"] == registration["event_id"]
                and item["status"] == "confirmed"
                for item in registrations.values()
            ):
                return InsertOutcome.ALREADY_REGISTERED
            confirmed = sum(
                item["event_id"] == registration["event_id"]
                and item["status"] == "confirmed"
                for item in registrations.values()
            )
            if confirmed >= capacity:
                return InsertOutcome.EVENT_FULL
            registrations[registration["id"]] = deepcopy(registration)
            self._write_unlocked(registrations)
            return InsertOutcome.CREATED

    def find_by_id(self, registration_id: str) -> Registration | None:
        with self._lock:
            item = self._read_unlocked().get(registration_id)
            return deepcopy(item) if item is not None else None

    def find_all(
        self, filters: RegistrationFilters | None = None
    ) -> list[Registration]:
        filters = filters or {}
        with self._lock:
            return [
                deepcopy(item)
                for item in self._read_unlocked().values()
                if all(item.get(key) == value for key, value in filters.items())
            ]

    def update_status(
        self, registration_id: str, status: str, updated_at: str
    ) -> Registration | None:
        with self._lock:
            registrations = self._read_unlocked()
            item = registrations.get(registration_id)
            if item is None:
                return None
            item["status"] = status
            item["updated_at"] = updated_at
            self._write_unlocked(registrations)
            return deepcopy(item)

    def delete(self, registration_id: str) -> bool:
        with self._lock:
            registrations = self._read_unlocked()
            if registration_id not in registrations:
                return False
            del registrations[registration_id]
            self._write_unlocked(registrations)
            return True

    def count_confirmed(self, event_id: str) -> int:
        with self._lock:
            return sum(
                item["event_id"] == event_id and item["status"] == "confirmed"
                for item in self._read_unlocked().values()
            )
