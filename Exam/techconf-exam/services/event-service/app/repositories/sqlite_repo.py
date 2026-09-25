"""SQLite event repository using Python's standard sqlite3 module."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.repositories.event_repository import Event, EventFilters, EventRepository

_COLUMNS = (
    "id",
    "title",
    "description",
    "organizer_id",
    "venue",
    "city",
    "start_date",
    "end_date",
    "capacity",
    "price",
    "status",
    "created_at",
    "updated_at",
)


class SqliteEventRepository(EventRepository):
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    organizer_id TEXT NOT NULL,
                    venue TEXT NOT NULL,
                    city TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    capacity INTEGER NOT NULL,
                    price REAL NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _row_to_event(row: sqlite3.Row | None) -> Event | None:
        return dict(row) if row is not None else None

    def insert(self, event: Event) -> Event:
        placeholders = ", ".join("?" for _ in _COLUMNS)
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO events ({', '.join(_COLUMNS)}) VALUES ({placeholders})",
                tuple(event[column] for column in _COLUMNS),
            )
        return dict(event)

    def find_by_id(self, event_id: str) -> Event | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM events WHERE id = ?", (event_id,)
            ).fetchone()
        return self._row_to_event(row)

    def find_all(self, filters: EventFilters | None = None) -> list[Event]:
        filters = filters or {}
        clauses: list[str] = []
        values: list[str] = []
        for key in ("status", "city"):
            if key in filters:
                clauses.append(f"{key} = ?")
                values.append(filters[key])
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM events{where} ORDER BY rowid", tuple(values)
            ).fetchall()
        return [dict(row) for row in rows]

    def update(self, event_id: str, event: Event) -> Event | None:
        mutable_columns = _COLUMNS[1:]
        assignments = ", ".join(f"{column} = ?" for column in mutable_columns)
        values = tuple(event[column] for column in mutable_columns) + (event_id,)
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE events SET {assignments} WHERE id = ?", values
            )
            if cursor.rowcount == 0:
                return None
        return self.find_by_id(event_id)

    def delete(self, event_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM events WHERE id = ?", (event_id,))
            return cursor.rowcount > 0
