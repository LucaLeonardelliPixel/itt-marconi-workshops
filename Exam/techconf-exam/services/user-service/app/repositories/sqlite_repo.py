"""Sqlite3Repository stub — implemented in Task 5."""

from __future__ import annotations

from pathlib import Path

from app.repositories.base import UserRepository


class Sqlite3Repository(UserRepository):
    """SQLite3-backed repository (stub — implemented in Task 5)."""

    def __init__(self, path: Path) -> None:
        self._path = path
