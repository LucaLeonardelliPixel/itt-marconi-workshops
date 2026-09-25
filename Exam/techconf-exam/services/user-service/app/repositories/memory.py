"""MemoryRepository stub — implemented in Task 3."""

from __future__ import annotations

from app.repositories.base import UserRepository


class MemoryRepository(UserRepository):
    """In-process dict-backed repository (stub — implemented in Task 3)."""
