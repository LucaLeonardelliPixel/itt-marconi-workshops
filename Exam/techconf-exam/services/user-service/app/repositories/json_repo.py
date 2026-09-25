"""JsonRepository — JSON-file-backed adapter for user-service."""

from __future__ import annotations

import copy
import json
import threading
from pathlib import Path

from app.repositories.base import UserRepository


class JsonRepository(UserRepository):
    """Persists user records to a single JSON file at the path given at construction.

    Every read operation loads the full file from disk; every write
    operation serialises the full store and overwrites the file.  A
    ``threading.Lock`` serialises concurrent writes so that parallel
    requests never corrupt the file.

    The path (and therefore ``DATA_DIR``) is injected by the caller —
    this class never reads environment variables directly.
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, dict]:
        """Read the JSON file and return the store dict.

        Returns an empty dict if the file does not exist yet.
        """
        if not self._path.exists():
            return {}
        with self._path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        # Expect a JSON object mapping id -> user dict
        return data if isinstance(data, dict) else {}

    def _save(self, store: dict[str, dict]) -> None:
        """Serialise *store* and overwrite the JSON file.

        Must be called while the write lock is held.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as fh:
            json.dump(store, fh, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Interface implementation
    # ------------------------------------------------------------------

    def insert(self, user: dict) -> dict:
        """Persist *user* and return a copy of the stored record."""
        with self._lock:
            store = self._load()
            store[user["id"]] = copy.deepcopy(user)
            self._save(store)
        return copy.deepcopy(user)

    def find_by_id(self, id: str) -> dict | None:
        """Return a copy of the user record for *id*, or ``None``."""
        store = self._load()
        record = store.get(id)
        return copy.deepcopy(record) if record is not None else None

    def find_all(self, filters: dict | None = None) -> list[dict]:
        """Return all records, optionally filtered by ``role`` and/or ``email``.

        Both filters are equality checks applied with logical AND.
        """
        store = self._load()
        results: list[dict] = list(store.values())

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
        with self._lock:
            store = self._load()
            if id not in store:
                return None
            store[id] = copy.deepcopy(data)
            self._save(store)
            return copy.deepcopy(store[id])

    def delete(self, id: str) -> bool:
        """Remove the record for *id*.

        Returns ``True`` if the record existed and was deleted, ``False``
        if it was not found.
        """
        with self._lock:
            store = self._load()
            if id not in store:
                return False
            del store[id]
            self._save(store)
        return True

    def email_exists(self, email: str, exclude_id: str | None = None) -> bool:
        """Return ``True`` if *email* is already owned by another user.

        When *exclude_id* is provided (e.g. during an update), the record
        with that ``id`` is skipped so a user's own email is never flagged
        as a conflict.
        """
        store = self._load()
        for user in store.values():
            if user.get("email") == email:
                if exclude_id is not None and user.get("id") == exclude_id:
                    continue
                return True
        return False
