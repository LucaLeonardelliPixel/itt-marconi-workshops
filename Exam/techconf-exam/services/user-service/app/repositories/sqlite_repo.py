"""Sqlite3Repository — SQLite-backed adapter for user-service."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.repositories.base import UserRepository

# Column names that mirror the User schema, in insertion order.
_COLUMNS = (
    "id",
    "first_name",
    "last_name",
    "email",
    "company",
    "role",
    "created_at",
    "updated_at",
)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id         TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name  TEXT NOT NULL,
    email      TEXT NOT NULL,
    company    TEXT,
    role       TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a ``sqlite3.Row`` to a plain ``dict`` matching the User shape."""
    d = dict(row)
    # SQLite stores NULL as None; preserve that for the nullable 'company' field.
    return d


class Sqlite3Repository(UserRepository):
    """Persists user records to a SQLite database at the path given at construction.

    The ``users`` table is created with ``CREATE TABLE IF NOT EXISTS`` on the
    first connection so that the file is initialised automatically.  All
    read/write operations use parameterised queries to prevent SQL injection.

    The path (and therefore ``DATA_DIR``) is injected by the caller —
    this class never reads environment variables directly.
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        # Ensure parent directory exists before SQLite tries to open the file.
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open a connection with ``row_factory`` set for dict-like access."""
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create the ``users`` table if it does not already exist."""
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE_SQL)
            conn.commit()

    # ------------------------------------------------------------------
    # Interface implementation
    # ------------------------------------------------------------------

    def insert(self, user: dict) -> dict:
        """Persist *user* and return a copy of the stored record."""
        placeholders = ", ".join("?" for _ in _COLUMNS)
        columns_sql = ", ".join(_COLUMNS)
        sql = f"INSERT INTO users ({columns_sql}) VALUES ({placeholders})"
        values = tuple(user.get(col) for col in _COLUMNS)

        with self._connect() as conn:
            conn.execute(sql, values)
            conn.commit()

        return dict(user)

    def find_by_id(self, id: str) -> dict | None:
        """Return the user dict for *id*, or ``None`` if not found."""
        with self._connect() as conn:
            cursor = conn.execute("SELECT * FROM users WHERE id = ?", (id,))
            row = cursor.fetchone()

        return _row_to_dict(row) if row is not None else None

    def find_all(self, filters: dict | None = None) -> list[dict]:
        """Return all records, optionally filtered by ``role`` and/or ``email``.

        Both filters are equality checks applied with logical AND.
        """
        sql = "SELECT * FROM users"
        params: list[Any] = []

        conditions: list[str] = []
        if filters:
            role = filters.get("role")
            email = filters.get("email")
            if role is not None:
                conditions.append("role = ?")
                params.append(role)
            if email is not None:
                conditions.append("email = ?")
                params.append(email)

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        with self._connect() as conn:
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()

        return [_row_to_dict(row) for row in rows]

    def update(self, id: str, data: dict) -> dict | None:
        """Overwrite the stored record for *id* with *data*.

        Returns the updated user dict, or ``None`` if *id* was not found.
        """
        # Build SET clause for every column except the primary key.
        mutable_cols = [col for col in _COLUMNS if col != "id"]
        set_clause = ", ".join(f"{col} = ?" for col in mutable_cols)
        sql = f"UPDATE users SET {set_clause} WHERE id = ?"
        values = tuple(data.get(col) for col in mutable_cols) + (id,)

        with self._connect() as conn:
            cursor = conn.execute(sql, values)
            conn.commit()
            if cursor.rowcount == 0:
                return None

        return self.find_by_id(id)

    def delete(self, id: str) -> bool:
        """Remove the record for *id*.

        Returns ``True`` if the record existed and was deleted, ``False``
        if it was not found.
        """
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM users WHERE id = ?", (id,))
            conn.commit()

        return cursor.rowcount > 0

    def email_exists(self, email: str, exclude_id: str | None = None) -> bool:
        """Return ``True`` if *email* is already owned by another user.

        When *exclude_id* is provided (e.g. during an update), the record
        with that ``id`` is skipped so a user's own email is never flagged
        as a conflict.
        """
        if exclude_id is not None:
            sql = "SELECT 1 FROM users WHERE email = ? AND id != ? LIMIT 1"
            params: tuple = (email, exclude_id)
        else:
            sql = "SELECT 1 FROM users WHERE email = ? LIMIT 1"
            params = (email,)

        with self._connect() as conn:
            cursor = conn.execute(sql, params)
            row = cursor.fetchone()

        return row is not None
