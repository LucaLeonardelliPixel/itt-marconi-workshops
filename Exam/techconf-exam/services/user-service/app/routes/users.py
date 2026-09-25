"""User resource routes — stub (implemented in Task 12).

All route functions delegate to the injected UserService instance.
Business logic, validation, and storage access live in the service /
repository layers — never here.
"""

from __future__ import annotations

from flask import Blueprint


def make_blueprint(svc) -> Blueprint:
    """Return the users Blueprint with the service instance bound via closure."""
    bp = Blueprint("users", __name__, url_prefix="/api/v1/users")

    # Route implementations added in Task 12.

    return bp
