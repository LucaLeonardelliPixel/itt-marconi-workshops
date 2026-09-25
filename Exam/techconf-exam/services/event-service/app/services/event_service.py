"""Event business logic, independent from Flask and concrete adapters."""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.clients.user_repository import UserRepository
from app.repositories.event_repository import Event, EventRepository
from app.services.exceptions import (
    InvalidOrganizerError,
    InvalidStatusTransitionError,
    NotFoundError,
    ValidationError,
)

_WRITABLE_FIELDS = {
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
}
_REQUIRED_FIELDS = {
    "title",
    "organizer_id",
    "venue",
    "city",
    "start_date",
    "end_date",
    "capacity",
    "price",
}
_STATUSES = {"draft", "published", "cancelled"}
_ALLOWED_TRANSITIONS = {
    "draft": {"draft", "published", "cancelled"},
    "published": {"published", "cancelled"},
    "cancelled": {"cancelled"},
}
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


class EventService:
    def __init__(
        self,
        event_repository: EventRepository,
        user_repository: UserRepository,
    ) -> None:
        self._events = event_repository
        self._users = user_repository

    def create(self, data: dict[str, Any]) -> Event:
        payload = self._prepare_complete_payload(data)
        self._validate_organizer(payload["organizer_id"])
        timestamp = _utc_timestamp()
        event: Event = {
            "id": str(uuid4()),
            **payload,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        return self._events.insert(event)

    def list_events(
        self,
        filters: dict[str, Any] | None = None,
        page: Any = 1,
        page_size: Any = 20,
    ) -> dict[str, Any]:
        page_number = self._pagination_integer("page", page, minimum=1)
        size = self._pagination_integer("page_size", page_size, minimum=1, maximum=100)
        filters = filters or {}
        unknown_filters = set(filters) - {"status", "city"}
        if unknown_filters:
            raise ValidationError(
                "Unsupported event filter.", {"fields": sorted(unknown_filters)}
            )
        repository_filters: dict[str, str] = {}
        if filters.get("status") is not None:
            status = filters["status"]
            if status not in _STATUSES:
                raise ValidationError(
                    "status must be draft, published, or cancelled.",
                    {"field": "status"},
                )
            repository_filters["status"] = status
        if filters.get("city") is not None:
            city = filters["city"]
            if not isinstance(city, str):
                raise ValidationError("city must be a string.", {"field": "city"})
            repository_filters["city"] = city

        matching = self._events.find_all(repository_filters)
        total = len(matching)
        start = (page_number - 1) * size
        return {
            "items": matching[start : start + size],
            "page": page_number,
            "page_size": size,
            "total": total,
        }

    def get(self, event_id: str) -> Event:
        event = self._events.find_by_id(event_id)
        if event is None:
            raise NotFoundError(event_id)
        return event

    def replace(self, event_id: str, data: dict[str, Any]) -> Event:
        current = self.get(event_id)
        payload = self._prepare_complete_payload(data)
        self._validate_transition(current["status"], payload["status"])
        self._validate_organizer(payload["organizer_id"])
        replacement: Event = {
            "id": current["id"],
            **payload,
            "created_at": current["created_at"],
            "updated_at": _utc_timestamp(),
        }
        updated = self._events.update(event_id, replacement)
        if updated is None:
            raise NotFoundError(event_id)
        return updated

    def update(self, event_id: str, data: dict[str, Any]) -> Event:
        current = self.get(event_id)
        self._validate_input_object(data, require_all=False)
        if not data:
            raise ValidationError("PATCH body must contain at least one field.")
        self._validate_field_values(data)

        merged = {**current, **data}
        self._validate_field_values(
            {field: merged[field] for field in _WRITABLE_FIELDS}
        )
        self._validate_date_range(merged["start_date"], merged["end_date"])
        self._validate_transition(current["status"], merged["status"])
        if merged["organizer_id"] != current["organizer_id"]:
            self._validate_organizer(merged["organizer_id"])

        merged["id"] = current["id"]
        merged["created_at"] = current["created_at"]
        merged["updated_at"] = _utc_timestamp()
        updated = self._events.update(event_id, merged)
        if updated is None:
            raise NotFoundError(event_id)
        return updated

    def delete(self, event_id: str) -> None:
        if not self._events.delete(event_id):
            raise NotFoundError(event_id)

    def _prepare_complete_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        self._validate_input_object(data, require_all=True)
        payload = dict(data)
        payload.setdefault("description", None)
        payload.setdefault("status", "draft")
        self._validate_field_values(payload)
        self._validate_date_range(payload["start_date"], payload["end_date"])
        return payload

    @staticmethod
    def _validate_input_object(data: Any, require_all: bool) -> None:
        if not isinstance(data, dict):
            raise ValidationError("Request body must be a JSON object.")
        unknown = set(data) - _WRITABLE_FIELDS
        if unknown:
            raise ValidationError(
                "Request contains unsupported fields.", {"fields": sorted(unknown)}
            )
        if require_all:
            missing = _REQUIRED_FIELDS - set(data)
            if missing:
                raise ValidationError(
                    "Request is missing required fields.",
                    {"fields": sorted(missing)},
                )

    @staticmethod
    def _validate_field_values(data: dict[str, Any]) -> None:
        for field, minimum, maximum in (
            ("title", 3, 120),
            ("venue", 0, 100),
            ("city", 0, 60),
        ):
            if field in data:
                value = data[field]
                if not isinstance(value, str) or not minimum <= len(value) <= maximum:
                    raise ValidationError(
                        f"{field} length must be between {minimum} and {maximum}.",
                        {"field": field},
                    )

        if "description" in data:
            description = data["description"]
            if description is not None and (
                not isinstance(description, str) or len(description) > 2000
            ):
                raise ValidationError(
                    "description must be null or at most 2000 characters.",
                    {"field": "description"},
                )

        if "organizer_id" in data:
            organizer_id = data["organizer_id"]
            if not isinstance(organizer_id, str):
                raise ValidationError(
                    "organizer_id must be a UUID.", {"field": "organizer_id"}
                )
            try:
                parsed = UUID(organizer_id)
            except (ValueError, AttributeError):
                raise ValidationError(
                    "organizer_id must be a UUID.", {"field": "organizer_id"}
                ) from None
            if str(parsed) != organizer_id.lower():
                raise ValidationError(
                    "organizer_id must be a canonical UUID.",
                    {"field": "organizer_id"},
                )

        for field in ("start_date", "end_date"):
            if field in data:
                value = data[field]
                if not isinstance(value, str) or not _DATE_PATTERN.fullmatch(value):
                    raise ValidationError(
                        f"{field} must use YYYY-MM-DD format.", {"field": field}
                    )
                try:
                    date.fromisoformat(value)
                except ValueError:
                    raise ValidationError(
                        f"{field} must be a real date.", {"field": field}
                    ) from None

        if "capacity" in data:
            capacity = data["capacity"]
            if isinstance(capacity, bool) or not isinstance(capacity, int) or not 1 <= capacity <= 10000:
                raise ValidationError(
                    "capacity must be an integer from 1 through 10000.",
                    {"field": "capacity"},
                )

        if "price" in data:
            price = data["price"]
            if (
                isinstance(price, bool)
                or not isinstance(price, (int, float))
                or not math.isfinite(price)
                or price < 0
            ):
                raise ValidationError(
                    "price must be a non-negative finite number.",
                    {"field": "price"},
                )

        if "status" in data and data["status"] not in _STATUSES:
            raise ValidationError(
                "status must be draft, published, or cancelled.",
                {"field": "status"},
            )

    @staticmethod
    def _validate_date_range(start_date: str, end_date: str) -> None:
        if date.fromisoformat(end_date) < date.fromisoformat(start_date):
            raise ValidationError(
                "end_date must be on or after start_date.",
                {"fields": ["start_date", "end_date"]},
            )

    def _validate_organizer(self, organizer_id: str) -> None:
        user = self._users.get_user(organizer_id)
        if user.get("role") != "organizer":
            raise InvalidOrganizerError(organizer_id)

    @staticmethod
    def _validate_transition(current: str, requested: str) -> None:
        if requested not in _ALLOWED_TRANSITIONS[current]:
            raise InvalidStatusTransitionError(current, requested)

    @staticmethod
    def _pagination_integer(
        field: str,
        value: Any,
        minimum: int,
        maximum: int | None = None,
    ) -> int:
        if isinstance(value, bool):
            raise ValidationError(f"{field} must be an integer.", {"field": field})
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            raise ValidationError(
                f"{field} must be an integer.", {"field": field}
            ) from None
        if str(value).strip() != str(parsed) and not isinstance(value, int):
            raise ValidationError(f"{field} must be an integer.", {"field": field})
        if parsed < minimum or (maximum is not None and parsed > maximum):
            raise ValidationError(
                f"{field} is outside the allowed range.", {"field": field}
            )
        return parsed
