"""Shared fixtures for user-service unit tests.

The ``backend_repo`` fixture is parameterised over all three storage adapters
so every storage-touching test runs three times — once per backend.
"""

from __future__ import annotations

import pytest

from app.repositories.memory import MemoryRepository
from app.repositories.json_repo import JsonRepository
from app.repositories.sqlite_repo import Sqlite3Repository


@pytest.fixture(params=["memory", "json", "sqlite"])
def backend_repo(request, tmp_path):
    """Yield a fresh repository instance for each storage backend."""
    if request.param == "memory":
        return MemoryRepository()
    if request.param == "json":
        return JsonRepository(tmp_path / "users.json")
    if request.param == "sqlite":
        return Sqlite3Repository(tmp_path / "users.db")
