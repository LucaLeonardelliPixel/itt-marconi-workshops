"""Flask routes for registration resources and event statistics."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, Response, jsonify, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from app.services.exceptions import MalformedJsonError, MethodNotAllowedError
from app.services.registration_service import RegistrationService

_REGISTRATION_FIELDS = (
    "id",
    "user_id",
    "event_id",
    "amount",
    "status",
    "created_at",
    "updated_at",
)


def _registration_body(registration: dict[str, Any]) -> dict[str, Any]:
    return {
        field: registration[field]
        for field in _REGISTRATION_FIELDS
        if field in registration
    }


def _json_body() -> Any:
    if not request.is_json:
        raise MalformedJsonError("Request Content-Type must be application/json.")
    try:
        return request.get_json(silent=False)
    except (BadRequest, UnsupportedMediaType) as exc:
        raise MalformedJsonError() from exc


def create_registrations_blueprint(service: RegistrationService) -> Blueprint:
    blueprint = Blueprint(
        "registrations", __name__, url_prefix="/api/v1/registrations"
    )

    @blueprint.post("")
    def create_registration() -> Response:
        registration = service.create(_json_body())
        response = jsonify(_registration_body(registration))
        response.status_code = 201
        response.headers["Location"] = (
            f"/api/v1/registrations/{registration['id']}"
        )
        return response

    @blueprint.get("")
    def list_registrations() -> Response:
        filters = {
            key: request.args.get(key)
            for key in ("user_id", "event_id", "status")
            if key in request.args
        }
        page = service.list_registrations(
            filters=filters,
            page=request.args.get("page", "1"),
            page_size=request.args.get("page_size", "20"),
        )
        page["items"] = [
            _registration_body(item) for item in page["items"]
        ]
        return jsonify(page)

    @blueprint.get("/stats")
    def registration_stats() -> Response:
        return jsonify(service.stats(request.args.get("event_id")))

    @blueprint.get("/<registration_id>")
    def get_registration(registration_id: str) -> Response:
        return jsonify(_registration_body(service.get(registration_id)))

    @blueprint.patch("/<registration_id>")
    def cancel_registration(registration_id: str) -> Response:
        return jsonify(
            _registration_body(service.cancel(registration_id, _json_body()))
        )

    @blueprint.delete("/<registration_id>")
    def delete_registration(registration_id: str) -> tuple[str, int]:
        service.delete(registration_id)
        return "", 204

    @blueprint.put("/<registration_id>")
    def put_registration_not_allowed(registration_id: str) -> Response:
        del registration_id
        raise MethodNotAllowedError()

    return blueprint
