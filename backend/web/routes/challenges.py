"""Challenge API routes."""

from __future__ import annotations

import json

from flask import Blueprint, current_app, jsonify, request

from backend.app.challenge_service import ChallengeService, ValidationError
from backend.app.run_manager import RunManager

bp = Blueprint("challenges", __name__, url_prefix="/api/challenges")


def _service() -> ChallengeService:
    return current_app.config["challenge_service"]


def _runs() -> RunManager:
    return current_app.config["run_manager"]


@bp.get("")
def list_challenges():
    return jsonify({"challenges": _service().list_challenges()})


@bp.post("")
def import_challenge():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object")
    path = payload.get("path")
    if not isinstance(path, str) or not path.strip():
        raise ValidationError("path must be a non-empty string")
    challenge = _service().import_from_path(path)
    return jsonify({"challenge": challenge}), 201


@bp.post("/manual")
def create_manual_challenge():
    metadata_raw = request.form.get("metadata", "")
    try:
        metadata = json.loads(metadata_raw)
    except json.JSONDecodeError as error:
        raise ValidationError("metadata must be valid JSON") from error
    if not isinstance(metadata, dict):
        raise ValidationError("metadata must be a JSON object")

    uploaded_files = request.files.getlist("files")
    file_names_raw = request.form.get("file_names")
    if file_names_raw:
        try:
            file_names = json.loads(file_names_raw)
        except json.JSONDecodeError as error:
            raise ValidationError("file_names must be valid JSON") from error
        if not isinstance(file_names, list) or not all(isinstance(name, str) for name in file_names):
            raise ValidationError("file_names must be a JSON array of strings")
        if len(file_names) != len(uploaded_files):
            raise ValidationError("file_names length must match uploaded files")
    else:
        file_names = [file.filename for file in uploaded_files]

    files = [(name, file.read()) for name, file in zip(file_names, uploaded_files, strict=True)]
    challenge = _service().create_manual_challenge(
        metadata,
        files=files,
        slug=request.form.get("slug") or None,
    )
    return jsonify({"challenge": challenge}), 201


@bp.get("/<int:challenge_id>")
def get_challenge(challenge_id: int):
    return jsonify({"challenge": _service().get_challenge(challenge_id)})


@bp.put("/<int:challenge_id>")
def update_challenge(challenge_id: int):
    payload = request.get_json(silent=True)
    challenge = _service().update_challenge_metadata(challenge_id, payload)
    return jsonify({"challenge": challenge})


@bp.delete("/<int:challenge_id>")
def delete_challenge(challenge_id: int):
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object")
    delete_files = payload.get("delete_files", False)
    if not isinstance(delete_files, bool):
        raise ValidationError("delete_files must be a boolean")

    _runs().delete_runs_for_challenge(challenge_id)
    challenge = _service().delete_challenge(challenge_id, delete_files=delete_files)
    return jsonify({"challenge": challenge})
