"""Health-check endpoint.

GET /health -> 200 {"status": "ok", "service": "user-service"}
"""

from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    return jsonify({"status": "ok", "service": "user-service"}), 200
