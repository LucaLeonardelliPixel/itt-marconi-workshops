"""Local process health endpoint."""

from flask import Blueprint, jsonify

health_blueprint = Blueprint("health", __name__)


@health_blueprint.get("/health")
def health():
    return jsonify({"status": "ok", "service": "event-service"}), 200
