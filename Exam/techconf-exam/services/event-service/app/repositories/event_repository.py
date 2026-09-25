"""Persistence port owned by the event-service domain."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

Event = dict[str, Any]
EventFilters = dict[str, str]


class EventRepository(ABC):
    """Abstract CRUD interface implemented by every storage backend."""

    @abstractmethod
    def insert(self, event: Event) -> Event:
        raise NotImplementedError

    @abstractmethod
    def find_by_id(self, event_id: str) -> Event | None:
        raise NotImplementedError

    @abstractmethod
    def find_all(self, filters: EventFilters | None = None) -> list[Event]:
        raise NotImplementedError

    @abstractmethod
    def update(self, event_id: str, event: Event) -> Event | None:
        raise NotImplementedError

    @abstractmethod
    def delete(self, event_id: str) -> bool:
        raise NotImplementedError
