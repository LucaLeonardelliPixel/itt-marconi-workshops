"""Typed domain, application, and dependency errors."""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
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

    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(
            f"{resource.capitalize()} '{resource_id}' was not found.",
            {"resource": resource, "id": resource_id},
        )


class MethodNotAllowedError(DomainError):
    code = "METHOD_NOT_ALLOWED"
    status_code = 405

    def __init__(self) -> None:
        super().__init__("PUT is not supported for registrations.")


class AlreadyRegisteredError(DomainError):
    code = "ALREADY_REGISTERED"
    status_code = 409

    def __init__(self, user_id: str, event_id: str) -> None:
        super().__init__(
            "The user already has a confirmed registration for this event.",
            {"user_id": user_id, "event_id": event_id},
        )


class EventFullError(DomainError):
    code = "EVENT_FULL"
    status_code = 409

    def __init__(self, event_id: str) -> None:
        super().__init__("The event has no available seats.", {"event_id": event_id})


class ValidationError(DomainError):
    code = "VALIDATION_ERROR"
    status_code = 422


class ReferenceNotFoundError(DomainError):
    code = "REFERENCE_NOT_FOUND"
    status_code = 422

    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(
            f"Referenced {resource} '{resource_id}' does not exist.",
            {"resource": resource, "id": resource_id},
        )


class EventNotOpenError(DomainError):
    code = "EVENT_NOT_OPEN"
    status_code = 422

    def __init__(self, event_id: str, status: str) -> None:
        super().__init__(
            "Registrations are accepted only for published events.",
            {"event_id": event_id, "event_status": status},
        )


class InvalidStatusTransitionError(DomainError):
    code = "INVALID_STATUS_TRANSITION"
    status_code = 422

    def __init__(self, current: str, requested: str) -> None:
        super().__init__(
            f"Registration status cannot transition from '{current}' to '{requested}'.",
            {"current_status": current, "requested_status": requested},
        )


class DependencyUnavailableError(DomainError):
    code = "DEPENDENCY_UNAVAILABLE"
    status_code = 503

    def __init__(self, dependency: str, message: str | None = None) -> None:
        super().__init__(
            message or f"{dependency} is unavailable.",
            {"dependency": dependency},
        )


class UpstreamNotFoundError(Exception):
    """Neutral client-layer signal mapped according to operation context."""

    def __init__(self, dependency: str, resource_id: str) -> None:
        super().__init__(f"{dependency} did not contain {resource_id}")
        self.dependency = dependency
        self.resource_id = resource_id
