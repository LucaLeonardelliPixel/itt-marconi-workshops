"""MemoryRepository — in-process dict-backed adapter for user-service."""

from __future__ import annotations

import copy

from app.repositories.base import UserRepository


class MemoryRepository(UserRepository):
    """In-process ``dict[str, dict]`` repository.

    Every user record is stored as a deep copy to prevent callers from
    mutating stored state through references.  This adapter is the default
    and serves as the test baseline for adapter-agnostic tests.
    """

    def __init__(self) -> None:
        self._store: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Interface implementation
    # ------------------------------------------------------------------

    def insert(self, user: dict) -> dict:
        """Store *user* and return a copy of the stored record."""
        self._store[user["id"]] = copy.deepcopy(user)
        return copy.deepcopy(self._store[user["id"]])

    def find_by_id(self, id: str) -> dict | None:
        """Return a copy of the user record for *id*, or ``None``."""
        record = self._store.get(id)
        return copy.deepcopy(record) if record is not None else None

    def find_all(self, filters: dict | None = None) -> list[dict]:
        """Return all records, optionally filtered by ``role`` and/or ``email``.

        Both filters are equality checks applied with logical AND.
        """
        results = list(self._store.values())

        if filters:
            role = filters.get("role")
            email = filters.get("email")
            if role is not None:
                results = [u for u in results if u.get("role") == role]
            if email is not None:
                results = [u for u in results if u.get("email") == email]

        return [copy.deepcopy(u) for u in results]

    def update(self, id: str, data: dict) -> dict | None:
        """Overwrite the stored record for *id* with *data*.

        Returns a copy of the updated record, or ``None`` if *id* was not
        found.
        """
        if id not in self._store:
            return None
        self._store[id] = copy.deepcopy(data)
        return copy.deepcopy(self._store[id])

    def delete(self, id: str) -> bool:
        """Remove the record for *id*.

        Returns ``True`` if the record existed and was deleted, ``False``
        if it was not found.
        """
        if id in self._store:
            del self._store[id]
            return True
        return False

    def patch(self, id: str, data: dict) -> dict | None:
        """Merge *data* onto the existing record for *id*.

        Only the keys present in *data* are updated; all other fields remain
        unchanged.  Returns a copy of the updated record, or ``None`` if *id*
        was not found.
        """
        if id not in self._store:
            return None
        self._store[id] = {**self._store[id], **copy.deepcopy(data)}
        return copy.deepcopy(self._store[id])

    def email_exists(self, email: str, exclude_id: str | None = None) -> bool:
        """Return ``True`` if *email* is already owned by another user.

        When *exclude_id* is provided (e.g. during an update), the record
        with that ``id`` is skipped so a user's own email is never flagged
        as a conflict.
        """
        for user in self._store.values():
            if user.get("email") == email:
                if exclude_id is not None and user.get("id") == exclude_id:
                    continue
                return True
        return False
