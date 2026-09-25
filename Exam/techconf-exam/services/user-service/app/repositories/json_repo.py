"""JsonRepository stub — implemented in Task 4."""

from __future__ import annotations

from pathlib import Path

from app.repositories.base import UserRepository


class JsonRepository(UserRepository):
    """JSON-file-backed repository (stub — implemented in Task 4)."""

    def __init__(self, path: Path) -> None:
        self._path = path
