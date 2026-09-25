"""Real-HTTP integration tests for registration dependencies."""

from __future__ import annotations

import socket
import threading
from contextlib import ExitStack, contextmanager
from uuid import uuid4

import pytest
import requests
from flask import Flask, jsonify
from werkzeug.serving import make_server

from app import Settings, create_app
from app.clients.event_client import HttpEventClient
from app.clients.user_client import HttpUserClient
from app.repositories.memory import MemoryRegistrationRepository


@contextmanager
def running_app(app: Flask):
    server = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def closed_url() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return f"http://127.0.0.1:{sock.getsockname()[1]}"


def user_app(existing_user: str | None) -> Flask:
    app = Flask("integration-user")

    @app.get("/api/v1/users/<user_id>")
    def get_user(user_id: str):
        if user_id != existing_user:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "missing"}}), 404
        return jsonify({"id": user_id, "role": "attendee"})

    return app


def event_app(existing_event: str | None, capacity: int = 2) -> Flask:
    app = Flask("integration-event")

    @app.get("/api/v1/events/<event_id>")
    def get_event(event_id: str):
        if event_id != existing_event:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "missing"}}), 404
        return jsonify(
            {
                "id": event_id,
                "status": "published",
                "capacity": capacity,
                "price": 49.0,
            }
        )

    return app


def registration_app(user_url: str, event_url: str) -> Flask:
    return create_app(
        repository=MemoryRegistrationRepository(),
        user_client=HttpUserClient(user_url),
        event_client=HttpEventClient(event_url),
        settings=Settings(user_service_url=user_url, event_service_url=event_url),
    )


@pytest.mark.req("REQ-REG-E01")
def test_real_http_registration_success():
    user_id = str(uuid4())
    event_id = str(uuid4())
    with ExitStack() as stack:
        users_url = stack.enter_context(running_app(user_app(user_id)))
        events_url = stack.enter_context(running_app(event_app(event_id)))
        registrations_url = stack.enter_context(
            running_app(registration_app(users_url, events_url))
        )
        response = requests.post(
            f"{registrations_url}/api/v1/registrations",
            json={"user_id": user_id, "event_id": event_id},
            timeout=5,
        )
    assert response.status_code == 201
    assert response.json()["amount"] == 49.0


@pytest.mark.req("REQ-REG-B01")
@pytest.mark.parametrize("missing", ["user", "event"])
def test_real_http_missing_reference_returns_422(missing):
    user_id = str(uuid4())
    event_id = str(uuid4())
    with ExitStack() as stack:
        users_url = stack.enter_context(
            running_app(user_app(None if missing == "user" else user_id))
        )
        events_url = stack.enter_context(
            running_app(event_app(None if missing == "event" else event_id))
        )
        registrations_url = stack.enter_context(
            running_app(registration_app(users_url, events_url))
        )
        response = requests.post(
            f"{registrations_url}/api/v1/registrations",
            json={"user_id": user_id, "event_id": event_id},
            timeout=5,
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REFERENCE_NOT_FOUND"


@pytest.mark.req("REQ-REG-B09")
def test_real_http_stopped_event_dependency_returns_503():
    user_id = str(uuid4())
    event_id = str(uuid4())
    with ExitStack() as stack:
        users_url = stack.enter_context(running_app(user_app(user_id)))
        registrations_url = stack.enter_context(
            running_app(registration_app(users_url, closed_url()))
        )
        response = requests.post(
            f"{registrations_url}/api/v1/registrations",
            json={"user_id": user_id, "event_id": event_id},
            timeout=5,
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
