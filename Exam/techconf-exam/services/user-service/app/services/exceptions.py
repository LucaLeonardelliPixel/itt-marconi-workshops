"""Domain exceptions for user-service.

Each exception carries:
  - ``code``    UPPER_SNAKE_CASE string matching the OpenAPI Error.code field.
  - ``message`` Human-readable description (used as the HTTP response message).
  - ``details`` Optional dict for extra context (defaults to empty dict).

These exceptions are raised exclusively by the service layer and caught by
Flask error-handlers in app/__init__.py, which map them to the correct HTTP
status codes and the contract Error envelope.
"""

from __future__ import annotations


class _BaseError(Exception):
    """Shared base for all user-service domain exceptions."""

    code: str  # overridden by each subclass

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class MalformedJsonError(_BaseError):
    """Raised when the request body cannot be parsed as JSON.

    HTTP 400 — MALFORMED_JSON
    """

    code = "MALFORMED_JSON"

    def __init__(self, message: str = "Request body is not valid JSON.", details: dict | None = None) -> None:
        super().__init__(message, details)


class ValidationError(_BaseError):
    """Raised when a field is missing, has the wrong type/length, or an
    unknown key is present in the request body (additionalProperties: false).

    HTTP 422 — VALIDATION_ERROR
    """

    code = "VALIDATION_ERROR"


class EmailConflictError(_BaseError):
    """Raised when the requested email address is already registered to a
    different user (case-insensitive comparison).

    HTTP 409 — EMAIL_ALREADY_EXISTS
    """

    code = "EMAIL_ALREADY_EXISTS"

    def __init__(self, email: str) -> None:
        super().__init__(
            f"The email address '{email}' is already registered.",
            {"email": email},
        )


class NotFoundError(_BaseError):
    """Raised when the requested resource does not exist.

    HTTP 404 — NOT_FOUND
    """

    code = "NOT_FOUND"

    def __init__(self, resource_id: str | None = None) -> None:
        msg = "Resource not found."
        if resource_id:
            msg = f"User '{resource_id}' not found."
        super().__init__(msg, {"id": resource_id} if resource_id else {})
