"""Flask routes for the event resource."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, Response, jsonify, request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from app.services.event_service import EventService
from app.services.exceptions import MalformedJsonError

_EVENT_FIELDS = (
    "id",
    "title",
    "description",
    "organizer_id",
    "venue",
    "city",
    "start_date",
    "end_date",
    "capacity",
    "price",
    "status",
    "created_at",
    "updated_at",
)


def _event_body(event: dict[str, Any]) -> dict[str, Any]:
    return {field: event[field] for field in _EVENT_FIELDS if field in event}


def _json_body() -> Any:
    if not request.is_json:
        raise MalformedJsonError("Request Content-Type must be application/json.")
    try:
        return request.get_json(silent=False)
    except (BadRequest, UnsupportedMediaType) as exc:
        raise MalformedJsonError() from exc


def create_events_blueprint(service: EventService) -> Blueprint:
    blueprint = Blueprint("events", __name__, url_prefix="/api/v1/events")

    @blueprint.post("")
    def create_event() -> Response:
        event = service.create(_json_body())
        response = jsonify(_event_body(event))
        response.status_code = 201
        response.headers["Location"] = f"/api/v1/events/{event['id']}"
        return response

    @blueprint.get("")
    def list_events() -> Response:
        filters = {
            key: request.args.get(key)
            for key in ("status", "city")
            if key in request.args
        }
        page = service.list_events(
            filters=filters,
            page=request.args.get("page", "1"),
            page_size=request.args.get("page_size", "20"),
        )
        page["items"] = [_event_body(event) for event in page["items"]]
        return jsonify(page)

    @blueprint.get("/<event_id>")
    def get_event(event_id: str) -> Response:
        return jsonify(_event_body(service.get(event_id)))

    @blueprint.put("/<event_id>")
    def replace_event(event_id: str) -> Response:
        return jsonify(_event_body(service.replace(event_id, _json_body())))

    @blueprint.patch("/<event_id>")
    def update_event(event_id: str) -> Response:
        return jsonify(_event_body(service.update(event_id, _json_body())))

    @blueprint.delete("/<event_id>")
    def delete_event(event_id: str) -> tuple[str, int]:
        service.delete(event_id)
        return "", 204

    return blueprint
