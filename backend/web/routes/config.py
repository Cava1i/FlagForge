"""Configuration API routes."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from backend.app.challenge_service import ValidationError
from backend.app.config_service import ConfigService

bp = Blueprint("config", __name__, url_prefix="/api/config")


def _service() -> ConfigService:
    return current_app.config["config_service"]


@bp.get("")
def get_config():
    return jsonify({"config": _service().get_config()})


@bp.get("/secrets/<key>")
def reveal_secret(key: str):
    return jsonify({"secret": _service().reveal_secret(key)})


@bp.put("")
def update_config():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("values"), dict):
        raise ValidationError("Request body must contain a values object")
    return jsonify({"config": _service().update_config(payload["values"])})
