"""Registration business rules independent of Flask and concrete adapters."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.clients.event_client import EventClient
from app.clients.user_client import UserClient
from app.repositories.registration_repository import (
    InsertOutcome,
    Registration,
    RegistrationRepository,
)
from app.services.exceptions import (
    AlreadyRegisteredError,
    EventFullError,
    EventNotOpenError,
    InvalidStatusTransitionError,
    NotFoundError,
    ReferenceNotFoundError,
    UpstreamNotFoundError,
    ValidationError,
)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


class RegistrationService:
    def __init__(
        self,
        repository: RegistrationRepository,
        user_client: UserClient,
        event_client: EventClient,
    ) -> None:
        self._registrations = repository
        self._users = user_client
        self._events = event_client

    def create(self, data: dict[str, Any]) -> Registration:
        self._validate_create(data)
        user_id = data["user_id"]
        event_id = data["event_id"]

        try:
            self._users.get_user(user_id)
        except UpstreamNotFoundError as exc:
            raise ReferenceNotFoundError("user", user_id) from exc
        try:
            event = self._events.get_event(event_id)
        except UpstreamNotFoundError as exc:
            raise ReferenceNotFoundError("event", event_id) from exc

        if event["status"] != "published":
            raise EventNotOpenError(event_id, event["status"])

        timestamp = _utc_timestamp()
        registration: Registration = {
            "id": str(uuid4()),
            "user_id": user_id,
            "event_id": event_id,
            "amount": event["price"],
            "status": "confirmed",
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        outcome = self._registrations.insert_confirmed(
            registration, event["capacity"]
        )
        if outcome is InsertOutcome.ALREADY_REGISTERED:
            raise AlreadyRegisteredError(user_id, event_id)
        if outcome is InsertOutcome.EVENT_FULL:
            raise EventFullError(event_id)
        return registration

    def list_registrations(
        self,
        filters: dict[str, Any] | None = None,
        page: Any = 1,
        page_size: Any = 20,
    ) -> dict[str, Any]:
        page_number = self._pagination_integer("page", page, 1)
        size = self._pagination_integer("page_size", page_size, 1, 100)
        filters = filters or {}
        unknown = set(filters) - {"user_id", "event_id", "status"}
        if unknown:
            raise ValidationError(
                "Unsupported registration filter.", {"fields": sorted(unknown)}
            )
        repository_filters: dict[str, str] = {}
        for field in ("user_id", "event_id"):
            value = filters.get(field)
            if value is not None:
                self._validate_uuid(field, value)
                repository_filters[field] = value
        status = filters.get("status")
        if status is not None:
            if status not in {"confirmed", "cancelled"}:
                raise ValidationError(
                    "status must be confirmed or cancelled.", {"field": "status"}
                )
            repository_filters["status"] = status

        matching = self._registrations.find_all(repository_filters)
        total = len(matching)
        start = (page_number - 1) * size
        return {
            "items": matching[start : start + size],
            "page": page_number,
            "page_size": size,
            "total": total,
        }

    def get(self, registration_id: str) -> Registration:
        registration = self._registrations.find_by_id(registration_id)
        if registration is None:
            raise NotFoundError("registration", registration_id)
        return registration

    def cancel(self, registration_id: str, data: dict[str, Any]) -> Registration:
        current = self.get(registration_id)
        if not isinstance(data, dict):
            raise ValidationError("Request body must be a JSON object.")
        if set(data) != {"status"}:
            raise ValidationError(
                "PATCH body must contain only the required status field.",
                {"fields": sorted(data)},
            )
        requested = data["status"]
        if current["status"] != "confirmed" or requested != "cancelled":
            raise InvalidStatusTransitionError(current["status"], str(requested))
        updated = self._registrations.update_status(
            registration_id, "cancelled", _utc_timestamp()
        )
        if updated is None:
            raise NotFoundError("registration", registration_id)
        return updated

    def delete(self, registration_id: str) -> None:
        if not self._registrations.delete(registration_id):
            raise NotFoundError("registration", registration_id)

    def stats(self, event_id: Any) -> dict[str, Any]:
        self._validate_uuid("event_id", event_id)
        try:
            event = self._events.get_event(event_id)
        except UpstreamNotFoundError as exc:
            raise NotFoundError("event", event_id) from exc
        confirmed = self._registrations.count_confirmed(event_id)
        capacity = event["capacity"]
        return {
            "event_id": event_id,
            "capacity": capacity,
            "confirmed": confirmed,
            "available": max(capacity - confirmed, 0),
        }

    @classmethod
    def _validate_create(cls, data: Any) -> None:
        if not isinstance(data, dict):
            raise ValidationError("Request body must be a JSON object.")
        if set(data) != {"user_id", "event_id"}:
            raise ValidationError(
                "POST body must contain exactly user_id and event_id.",
                {"fields": sorted(data)},
            )
        cls._validate_uuid("user_id", data["user_id"])
        cls._validate_uuid("event_id", data["event_id"])

    @staticmethod
    def _validate_uuid(field: str, value: Any) -> None:
        if not isinstance(value, str):
            raise ValidationError(f"{field} must be a UUID.", {"field": field})
        try:
            parsed = UUID(value)
        except (ValueError, AttributeError):
            raise ValidationError(f"{field} must be a UUID.", {"field": field}) from None
        if str(parsed) != value.lower():
            raise ValidationError(
                f"{field} must be a canonical UUID.", {"field": field}
            )

    @staticmethod
    def _pagination_integer(
        field: str, value: Any, minimum: int, maximum: int | None = None
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
