"""Custom integration tests using a real HTTP user dependency."""

from __future__ import annotations

import socket
import threading
from contextlib import contextmanager
from uuid import uuid4

import pytest
from flask import Flask, jsonify
from werkzeug.serving import make_server

from app import Settings, create_app
from app.clients.http_user_repository import HttpUserRepository
from app.repositories.memory import MemoryEventRepository


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def running_user_service(existing_id: str | None):
    app = Flask("integration-user-service")

    @app.get("/api/v1/users/<user_id>")
    def get_user(user_id: str):
        if user_id != existing_id:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "missing"}}), 404
        return jsonify({"id": user_id, "role": "organizer"}), 200

    server = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def event_payload(organizer_id: str):
    return {
        "title": "Real HTTP Dependency Conference",
        "organizer_id": organizer_id,
        "venue": "Auditorium",
        "city": "Roma",
        "start_date": "2026-10-15",
        "end_date": "2026-10-16",
        "capacity": 10,
        "price": 49.0,
    }


def dependency_client(base_url: str):
    app = create_app(
        event_repository=MemoryEventRepository(),
        user_repository=HttpUserRepository(base_url),
        settings=Settings(user_service_url=base_url),
    )
    app.config.update(TESTING=True)
    return app.test_client()


@pytest.mark.req("REQ-EVT-B01")
def test_real_http_valid_organizer_returns_201(assert_contract):
    organizer_id = str(uuid4())
    with running_user_service(organizer_id) as base_url:
        response = dependency_client(base_url).post(
            "/api/v1/events", json=event_payload(organizer_id)
        )
    assert response.status_code == 201
    assert_contract("POST", "/api/v1/events", response)


@pytest.mark.req("REQ-EVT-B01")
def test_real_http_missing_organizer_returns_422(assert_contract):
    organizer_id = str(uuid4())
    with running_user_service(None) as base_url:
        response = dependency_client(base_url).post(
            "/api/v1/events", json=event_payload(organizer_id)
        )
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "REFERENCE_NOT_FOUND"
    assert_contract("POST", "/api/v1/events", response)


@pytest.mark.req("REQ-EVT-B05")
def test_stopped_dependency_returns_503(assert_contract):
    closed_port = free_port()
    base_url = f"http://127.0.0.1:{closed_port}"
    response = dependency_client(base_url).post(
        "/api/v1/events", json=event_payload(str(uuid4()))
    )
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
    assert_contract("POST", "/api/v1/events", response)
