"""UserService — business logic for user-service.

This module implements the UserService class which contains all business
rules: validation, normalisation, uniqueness enforcement, and delegation
to the repository layer.  It has zero I/O concerns — all storage access
goes through the UserRepository interface.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from app.repositories.base import UserRepository
from app.services.exceptions import (
    EmailConflictError,
    NotFoundError,
    ValidationError,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_ROLES = {"attendee", "speaker", "organizer"}

_USERCREATE_ALLOWED_KEYS = {"first_name", "last_name", "email", "company", "role"}

# Simple but robust email regex: local@domain.tld
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# Internal helpers (module-level pure functions)
# ---------------------------------------------------------------------------

def _normalise_email(email: str) -> str:
    """Return *email* stripped of whitespace and lowercased."""
    return email.strip().lower()


def _validate_create(data: dict) -> None:
    """Validate a ``UserCreate`` payload.

    Raises ``ValidationError`` with a descriptive message on the first
    violation found.  Checks (in order):

    1. ``data`` must be a dict.
    2. No keys outside the allowed set (``additionalProperties: false``).
    3. Required fields present and non-empty: ``first_name``, ``last_name``, ``email``.
    4. Field-length constraints.
    5. Email format.
    6. Role value (when supplied).
    """
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object.")

    # additionalProperties: false
    extra_keys = set(data.keys()) - _USERCREATE_ALLOWED_KEYS
    if extra_keys:
        raise ValidationError(
            f"Unknown field(s): {', '.join(sorted(extra_keys))}."
        )

    # Required fields
    for field in ("first_name", "last_name", "email"):
        value = data.get(field)
        if value is None:
            raise ValidationError(f"'{field}' is required.")
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(f"'{field}' must be a non-empty string.")

    # first_name length
    first_name = data["first_name"]
    if not isinstance(first_name, str) or not (1 <= len(first_name) <= 50):
        raise ValidationError("'first_name' must be between 1 and 50 characters.")

    # last_name length
    last_name = data["last_name"]
    if not isinstance(last_name, str) or not (1 <= len(last_name) <= 50):
        raise ValidationError("'last_name' must be between 1 and 50 characters.")

    # email format
    email = data["email"]
    if not isinstance(email, str) or not _EMAIL_RE.match(email.strip()):
        raise ValidationError("'email' must be a valid email address.")

    # company (optional) — max 100 chars when present and not None
    company = data.get("company")
    if company is not None:
        if not isinstance(company, str):
            raise ValidationError("'company' must be a string or null.")
        if len(company) > 100:
            raise ValidationError("'company' must be at most 100 characters.")

    # role (optional) — must be a known value when present
    role = data.get("role")
    if role is not None:
        if not isinstance(role, str) or role not in _VALID_ROLES:
            raise ValidationError(
                f"'role' must be one of: {', '.join(sorted(_VALID_ROLES))}."
            )


def _utc_now() -> str:
    """Return current UTC time formatted as ISO 8601 (``YYYY-MM-DDTHH:MM:SSZ``)."""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# UserService
# ---------------------------------------------------------------------------


class UserService:
    """Orchestrates all user-service business logic.

    Depends only on the UserRepository interface — never on a concrete
    adapter.  HTTP concerns (request parsing, response serialisation) live
    exclusively in the routes layer.
    """

    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self, data: dict) -> dict:
        """Validate *data*, create a new user, and return the stored record.

        Steps
        -----
        1. Validate ``UserCreate`` fields (types, lengths, format, no extra keys).
        2. Normalise email to lowercase + stripped.
        3. Enforce email uniqueness; raise ``EmailConflictError`` on collision.
        4. Generate a UUID v4 ``id`` and set ``created_at`` / ``updated_at``.
        5. Default ``role`` to ``"attendee"`` if omitted.
        6. Delegate to ``repo.insert`` and return the stored dict.

        Parameters
        ----------
        data:
            Raw ``UserCreate`` dict from the HTTP layer.

        Returns
        -------
        dict
            The newly-created ``User`` dict (all eight fields present).

        Raises
        ------
        ValidationError
            Any field violation or unknown key.
        EmailConflictError
            Email is already registered to another user.
        """
        _validate_create(data)

        normalised_email = _normalise_email(data["email"])

        if self._repo.email_exists(normalised_email):
            raise EmailConflictError(normalised_email)

        now = _utc_now()

        user: dict = {
            "id": str(uuid.uuid4()),
            "first_name": data["first_name"],
            "last_name": data["last_name"],
            "email": normalised_email,
            "company": data.get("company"),
            "role": data.get("role", "attendee"),
            "created_at": now,
            "updated_at": now,
        }

        return self._repo.insert(user)

    # Methods implemented in Tasks 7–11:
    #   list(filters, page, page_size) -> dict
    #   get(id)                        -> dict
    #   replace(id, data)              -> dict
    #   update(id, data)               -> dict
    #   delete(id)                     -> None
