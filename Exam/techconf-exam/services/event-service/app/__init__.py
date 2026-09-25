"""Flask application factory and dependency composition for event-service."""

from __future__ import annotations

from flask import Flask, jsonify

from app.clients.http_user_repository import HttpUserRepository
from app.clients.user_repository import UserRepository
from app.config import Settings, load_settings
from app.repositories.event_repository import EventRepository
from app.repositories.json_repo import JsonEventRepository
from app.repositories.memory import MemoryEventRepository
from app.repositories.sqlite_repo import SqliteEventRepository
from app.routes.events import create_events_blueprint
from app.routes.health import health_blueprint
from app.services.event_service import EventService
from app.services.exceptions import DomainError


def build_event_repository(settings: Settings) -> EventRepository:
    if settings.storage_backend == "memory":
        return MemoryEventRepository()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    if settings.storage_backend == "json":
        return JsonEventRepository(settings.data_dir / "events.json")
    if settings.storage_backend == "sqlite":
        return SqliteEventRepository(settings.data_dir / "events.db")
    raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")


def create_app(
    event_repository: EventRepository | None = None,
    user_repository: UserRepository | None = None,
    settings: Settings | None = None,
) -> Flask:
    settings = settings or load_settings()
    event_repository = event_repository or build_event_repository(settings)
    user_repository = user_repository or HttpUserRepository(
        settings.user_service_url,
        timeout=settings.dependency_timeout,
    )
    service = EventService(event_repository, user_repository)

    application = Flask(__name__)
    application.config["SETTINGS"] = settings
    application.register_blueprint(create_events_blueprint(service))
    application.register_blueprint(health_blueprint)

    @application.errorhandler(DomainError)
    def handle_domain_error(error: DomainError):
        return (
            jsonify(
                {
                    "error": {
                        "code": error.code,
                        "message": error.message,
                        "details": error.details,
                    }
                }
            ),
            error.status_code,
        )

    return application


__all__ = ["Settings", "build_event_repository", "create_app"]
