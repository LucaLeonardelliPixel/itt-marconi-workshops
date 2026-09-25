"""Persistence port for registrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

Registration = dict[str, Any]
RegistrationFilters = dict[str, str]


class InsertOutcome(str, Enum):
    CREATED = "created"
    ALREADY_REGISTERED = "already_registered"
    EVENT_FULL = "event_full"


class RegistrationRepository(ABC):
    @abstractmethod
    def insert_confirmed(
        self, registration: Registration, capacity: int
    ) -> InsertOutcome:
        raise NotImplementedError

    @abstractmethod
    def find_by_id(self, registration_id: str) -> Registration | None:
        raise NotImplementedError

    @abstractmethod
    def find_all(
        self, filters: RegistrationFilters | None = None
    ) -> list[Registration]:
        raise NotImplementedError

    @abstractmethod
    def update_status(
        self, registration_id: str, status: str, updated_at: str
    ) -> Registration | None:
        raise NotImplementedError

    @abstractmethod
    def delete(self, registration_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def count_confirmed(self, event_id: str) -> int:
        raise NotImplementedError
