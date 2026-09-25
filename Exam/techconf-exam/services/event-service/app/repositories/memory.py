"""In-memory event repository."""

from __future__ import annotations

from copy import deepcopy
from threading import RLock

from app.repositories.event_repository import Event, EventFilters, EventRepository


class MemoryEventRepository(EventRepository):
    def __init__(self) -> None:
        self._events: dict[str, Event] = {}
        self._lock = RLock()

    def insert(self, event: Event) -> Event:
        with self._lock:
            stored = deepcopy(event)
            self._events[event["id"]] = stored
            return deepcopy(stored)

    def find_by_id(self, event_id: str) -> Event | None:
        with self._lock:
            event = self._events.get(event_id)
            return deepcopy(event) if event is not None else None

    def find_all(self, filters: EventFilters | None = None) -> list[Event]:
        filters = filters or {}
        with self._lock:
            events = self._events.values()
            result = [
                deepcopy(event)
                for event in events
                if all(event.get(key) == value for key, value in filters.items())
            ]
        return result

    def update(self, event_id: str, event: Event) -> Event | None:
        with self._lock:
            if event_id not in self._events:
                return None
            stored = deepcopy(event)
            stored["id"] = event_id
            self._events[event_id] = stored
            return deepcopy(stored)

    def delete(self, event_id: str) -> bool:
        with self._lock:
            return self._events.pop(event_id, None) is not None
