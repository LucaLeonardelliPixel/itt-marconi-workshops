"""SQLite registration repository with atomic seat reservation."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from app.repositories.registration_repository import (
    InsertOutcome,
    Registration,
    RegistrationFilters,
    RegistrationRepository,
)

_COLUMNS = (
    "id",
    "user_id",
    "event_id",
    "amount",
    "status",
    "created_at",
    "updated_at",
)


class SqliteRegistrationRepository(RegistrationRepository):
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS registrations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_confirmed_registration
                ON registrations(user_id, event_id)
                WHERE status = 'confirmed'
                """
            )
            connection.commit()

    def insert_confirmed(
        self, registration: Registration, capacity: int
    ) -> InsertOutcome:
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                duplicate = connection.execute(
                    """
                    SELECT 1 FROM registrations
                    WHERE user_id = ? AND event_id = ? AND status = 'confirmed'
                    """,
                    (registration["user_id"], registration["event_id"]),
                ).fetchone()
                if duplicate is not None:
                    connection.rollback()
                    return InsertOutcome.ALREADY_REGISTERED
                confirmed = connection.execute(
                    """
                    SELECT COUNT(*) FROM registrations
                    WHERE event_id = ? AND status = 'confirmed'
                    """,
                    (registration["event_id"],),
                ).fetchone()[0]
                if confirmed >= capacity:
                    connection.rollback()
                    return InsertOutcome.EVENT_FULL
                placeholders = ", ".join("?" for _ in _COLUMNS)
                connection.execute(
                    f"INSERT INTO registrations ({', '.join(_COLUMNS)}) VALUES ({placeholders})",
                    tuple(registration[column] for column in _COLUMNS),
                )
                connection.commit()
                return InsertOutcome.CREATED
            except sqlite3.IntegrityError:
                connection.rollback()
                return InsertOutcome.ALREADY_REGISTERED

    def find_by_id(self, registration_id: str) -> Registration | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM registrations WHERE id = ?", (registration_id,)
            ).fetchone()
        return dict(row) if row is not None else None

    def find_all(
        self, filters: RegistrationFilters | None = None
    ) -> list[Registration]:
        filters = filters or {}
        clauses: list[str] = []
        values: list[str] = []
        for key in ("user_id", "event_id", "status"):
            if key in filters:
                clauses.append(f"{key} = ?")
                values.append(filters[key])
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"SELECT * FROM registrations{where} ORDER BY rowid", tuple(values)
            ).fetchall()
        return [dict(row) for row in rows]

    def update_status(
        self, registration_id: str, status: str, updated_at: str
    ) -> Registration | None:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "UPDATE registrations SET status = ?, updated_at = ? WHERE id = ?",
                (status, updated_at, registration_id),
            )
            connection.commit()
            if cursor.rowcount == 0:
                return None
        return self.find_by_id(registration_id)

    def delete(self, registration_id: str) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM registrations WHERE id = ?", (registration_id,)
            )
            connection.commit()
            return cursor.rowcount > 0

    def count_confirmed(self, event_id: str) -> int:
        with closing(self._connect()) as connection:
            return int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM registrations
                    WHERE event_id = ? AND status = 'confirmed'
                    """,
                    (event_id,),
                ).fetchone()[0]
            )
