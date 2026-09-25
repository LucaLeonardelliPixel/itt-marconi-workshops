"""Typed domain and application errors for event-service."""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base error translated by the Flask boundary."""

    code = "INTERNAL_ERROR"
    status_code = 500

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class MalformedJsonError(DomainError):
    code = "MALFORMED_JSON"
    status_code = 400

    def __init__(self, message: str = "Request body is not valid JSON.") -> None:
        super().__init__(message)


class NotFoundError(DomainError):
    code = "NOT_FOUND"
    status_code = 404

    def __init__(self, event_id: str) -> None:
        super().__init__(f"Event '{event_id}' was not found.", {"id": event_id})


class ValidationError(DomainError):
    code = "VALIDATION_ERROR"
    status_code = 422


class ReferenceNotFoundError(DomainError):
    code = "REFERENCE_NOT_FOUND"
    status_code = 422

    def __init__(self, organizer_id: str) -> None:
        super().__init__(
            f"Organizer '{organizer_id}' does not exist.",
            {"resource": "user", "id": organizer_id},
        )


class InvalidOrganizerError(DomainError):
    code = "INVALID_ORGANIZER"
    status_code = 422

    def __init__(self, organizer_id: str) -> None:
        super().__init__(
            f"User '{organizer_id}' does not have the organizer role.",
            {"organizer_id": organizer_id},
        )


class InvalidStatusTransitionError(DomainError):
    code = "INVALID_STATUS_TRANSITION"
    status_code = 422

    def __init__(self, current: str, requested: str) -> None:
        super().__init__(
            f"Event status cannot transition from '{current}' to '{requested}'.",
            {"current_status": current, "requested_status": requested},
        )


class DependencyUnavailableError(DomainError):
    code = "DEPENDENCY_UNAVAILABLE"
    status_code = 503

    def __init__(self, message: str = "user-service is unavailable.") -> None:
        super().__init__(message, {"dependency": "user-service"})
