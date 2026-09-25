"""Registration-service Flask application factory."""

from __future__ import annotations

from flask import Flask, jsonify

from app.clients.event_client import EventClient, HttpEventClient
from app.clients.user_client import HttpUserClient, UserClient
from app.config import Settings, load_settings
from app.repositories.json_repo import JsonRegistrationRepository
from app.repositories.memory import MemoryRegistrationRepository
from app.repositories.registration_repository import RegistrationRepository
from app.repositories.sqlite_repo import SqliteRegistrationRepository
from app.routes.health import health_blueprint
from app.routes.registrations import create_registrations_blueprint
from app.services.exceptions import DomainError
from app.services.registration_service import RegistrationService


def build_registration_repository(settings: Settings) -> RegistrationRepository:
    if settings.storage_backend == "memory":
        return MemoryRegistrationRepository()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    if settings.storage_backend == "json":
        return JsonRegistrationRepository(settings.data_dir / "registrations.json")
    if settings.storage_backend == "sqlite":
        return SqliteRegistrationRepository(settings.data_dir / "registrations.db")
    raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")


def create_app(
    repository: RegistrationRepository | None = None,
    user_client: UserClient | None = None,
    event_client: EventClient | None = None,
    settings: Settings | None = None,
) -> Flask:
    settings = settings or load_settings()
    repository = repository or build_registration_repository(settings)
    user_client = user_client or HttpUserClient(
        settings.user_service_url, timeout=settings.dependency_timeout
    )
    event_client = event_client or HttpEventClient(
        settings.event_service_url, timeout=settings.dependency_timeout
    )
    service = RegistrationService(repository, user_client, event_client)

    application = Flask(__name__)
    application.config["SETTINGS"] = settings
    application.register_blueprint(create_registrations_blueprint(service))
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


__all__ = ["Settings", "build_registration_repository", "create_app"]
