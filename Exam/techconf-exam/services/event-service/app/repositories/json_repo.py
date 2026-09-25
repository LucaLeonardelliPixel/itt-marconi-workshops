"""Atomic JSON-file event repository using only the standard library."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from threading import RLock

from app.repositories.event_repository import Event, EventFilters, EventRepository


class JsonEventRepository(EventRepository):
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        if not self._path.exists():
            self._write_unlocked({})

    def _read_unlocked(self) -> dict[str, Event]:
        try:
            with self._path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict):
            return {}
        return data

    def _write_unlocked(self, events: dict[str, Event]) -> None:
        temporary = self._path.with_suffix(self._path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(events, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self._path)

    def insert(self, event: Event) -> Event:
        with self._lock:
            events = self._read_unlocked()
            events[event["id"]] = deepcopy(event)
            self._write_unlocked(events)
            return deepcopy(events[event["id"]])

    def find_by_id(self, event_id: str) -> Event | None:
        with self._lock:
            event = self._read_unlocked().get(event_id)
            return deepcopy(event) if event is not None else None

    def find_all(self, filters: EventFilters | None = None) -> list[Event]:
        filters = filters or {}
        with self._lock:
            events = self._read_unlocked().values()
            return [
                deepcopy(event)
                for event in events
                if all(event.get(key) == value for key, value in filters.items())
            ]

    def update(self, event_id: str, event: Event) -> Event | None:
        with self._lock:
            events = self._read_unlocked()
            if event_id not in events:
                return None
            stored = deepcopy(event)
            stored["id"] = event_id
            events[event_id] = stored
            self._write_unlocked(events)
            return deepcopy(stored)

    def delete(self, event_id: str) -> bool:
        with self._lock:
            events = self._read_unlocked()
            if event_id not in events:
                return False
            del events[event_id]
            self._write_unlocked(events)
            return True
