"""Outbound user lookup port used for organizer validation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class UserRepository(ABC):
    @abstractmethod
    def get_user(self, user_id: str) -> dict[str, Any]:
        """Return one user or raise a typed application exception."""
        raise NotImplementedError
