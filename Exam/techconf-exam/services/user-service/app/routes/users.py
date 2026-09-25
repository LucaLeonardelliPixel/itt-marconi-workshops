"""User resource routes.

All route functions delegate to the injected UserService instance.
Business logic, validation, and storage access live in the service /
repository layers — never here.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.services.exceptions import MalformedJsonError, ValidationError


def make_blueprint(svc) -> Blueprint:
    """Return the users Blueprint with the service instance bound via closure."""
    bp = Blueprint("users", __name__, url_prefix="/api/v1/users")

    # ------------------------------------------------------------------
    # POST /api/v1/users — create a new user
    # ------------------------------------------------------------------
    @bp.post("")
    def create_user():
        data = request.get_json(force=True, silent=True)
        if data is None:
            raise MalformedJsonError()
        user = svc.create(data)
        resp = jsonify(user)
        resp.status_code = 201
        resp.headers["Location"] = f"/api/v1/users/{user['id']}"
        return resp

    # ------------------------------------------------------------------
    # GET /api/v1/users — list users (with optional filtering + pagination)
    # ------------------------------------------------------------------
    @bp.get("")
    def list_users():
        # Parse pagination params; bad values become ValidationError
        try:
            page = int(request.args.get("page", 1))
        except (ValueError, TypeError):
            raise ValidationError("'page' must be an integer ≥ 1.")

        try:
            page_size = int(request.args.get("page_size", 20))
        except (ValueError, TypeError):
            raise ValidationError("'page_size' must be an integer between 1 and 100.")

        # Build optional filter dict
        filters: dict = {}
        role = request.args.get("role")
        if role is not None:
            filters["role"] = role
        email = request.args.get("email")
        if email is not None:
            filters["email"] = email

        result = svc.list(filters or None, page, page_size)
        return jsonify(result), 200

    # ------------------------------------------------------------------
    # GET /api/v1/users/<id> — retrieve a single user
    # ------------------------------------------------------------------
    @bp.get("/<string:user_id>")
    def get_user(user_id: str):
        user = svc.get(user_id)
        return jsonify(user), 200

    # ------------------------------------------------------------------
    # PUT /api/v1/users/<id> — fully replace a user
    # ------------------------------------------------------------------
    @bp.put("/<string:user_id>")
    def replace_user(user_id: str):
        data = request.get_json(force=True, silent=True)
        if data is None:
            raise MalformedJsonError()
        user = svc.replace(user_id, data)
        return jsonify(user), 200

    # ------------------------------------------------------------------
    # PATCH /api/v1/users/<id> — partially update a user
    # ------------------------------------------------------------------
    @bp.patch("/<string:user_id>")
    def update_user(user_id: str):
        data = request.get_json(force=True, silent=True)
        if data is None:
            raise MalformedJsonError()
        user = svc.update(user_id, data)
        return jsonify(user), 200

    # ------------------------------------------------------------------
    # DELETE /api/v1/users/<id> — remove a user
    # ------------------------------------------------------------------
    @bp.delete("/<string:user_id>")
    def delete_user(user_id: str):
        svc.delete(user_id)
        return "", 204

    return bp
