"""user-service application factory.

Usage::

    from app import create_app
    app = create_app()          # uses STORAGE_BACKEND env var
    app = create_app(repo=...)  # inject a specific repository (tests)
"""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify

from app.services.exceptions import (
    EmailConflictError,
    MalformedJsonError,
    NotFoundError,
    ValidationError,
)


def _build_repo():
    """Select and instantiate the repository adapter from environment variables.

    Reads STORAGE_BACKEND (default: memory) and DATA_DIR (default: ./data).
    This is the ONLY place in the codebase that reads these env vars.
    """
    # Import here to keep top-level imports clean and avoid circular deps
    from app.repositories.memory import MemoryRepository
    from app.repositories.json_repo import JsonRepository
    from app.repositories.sqlite_repo import Sqlite3Repository

    backend = os.environ.get("STORAGE_BACKEND", "memory").lower()
    data_dir = Path(os.environ.get("DATA_DIR", "./data"))

    if backend == "memory":
        return MemoryRepository()
    if backend == "json":
        data_dir.mkdir(parents=True, exist_ok=True)
        return JsonRepository(data_dir / "users.json")
    if backend == "sqlite":
        data_dir.mkdir(parents=True, exist_ok=True)
        return Sqlite3Repository(data_dir / "users.db")
    raise ValueError(f"Unknown STORAGE_BACKEND: {backend!r}. Choose memory, json, or sqlite.")


def create_app(repo=None) -> Flask:
    """Create and configure the Flask application.

    Parameters
    ----------
    repo:
        Optional repository instance to inject (used in tests). When omitted
        the repository is built from environment variables via _build_repo().
    """
    app = Flask(__name__)

    # -- Repository & service -------------------------------------------------
    if repo is None:
        repo = _build_repo()

    # Import here so the service module can be tested independently of Flask
    from app.services.user_service import UserService
    svc = UserService(repo)

    # -- Blueprints -----------------------------------------------------------
    from app.routes.users import make_blueprint
    app.register_blueprint(make_blueprint(svc))

    from app.routes.health import health_bp
    app.register_blueprint(health_bp)

    # -- Error handlers -------------------------------------------------------
    def _error_response(exc: Exception, status: int):
        from app.services.exceptions import _BaseError
        err = exc if isinstance(exc, _BaseError) else _BaseError(str(exc))  # type: ignore[abstract]
        return jsonify({"error": {"code": err.code, "message": err.message, "details": err.details}}), status

    @app.errorhandler(MalformedJsonError)
    def handle_malformed_json(exc):
        return _error_response(exc, 400)

    @app.errorhandler(ValidationError)
    def handle_validation(exc):
        return _error_response(exc, 422)

    @app.errorhandler(EmailConflictError)
    def handle_conflict(exc):
        return _error_response(exc, 409)

    @app.errorhandler(NotFoundError)
    def handle_not_found(exc):
        return _error_response(exc, 404)

    return app
