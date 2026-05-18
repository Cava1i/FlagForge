"""Run API routes."""

from __future__ import annotations

from flask import Blueprint, Response, current_app, jsonify, request

from backend.app.challenge_service import ValidationError
from backend.app.run_manager import RunManager

bp = Blueprint("runs", __name__, url_prefix="/api/runs")


def _manager() -> RunManager:
    return current_app.config["run_manager"]


@bp.get("")
def list_runs():
    return jsonify(
        {
            "runs": _manager().list_runs(
                challenge_id=_optional_int_arg("challenge_id"),
                status=_optional_status_arg(),
                active=_optional_bool_arg("active"),
            )
        }
    )


@bp.post("")
def create_run():
    payload = request.get_json(silent=True) or {}
    run = _manager().create_run(payload)
    return jsonify({"run": run}), 201


@bp.get("/<int:run_id>")
def get_run(run_id: int):
    return jsonify({"run": _manager().get_run(run_id)})


@bp.delete("/<int:run_id>")
def delete_run(run_id: int):
    return jsonify({"run": _manager().delete_run(run_id)})


@bp.post("/<int:run_id>/cancel")
def cancel_run(run_id: int):
    return jsonify({"run": _manager().cancel_run(run_id)})


@bp.get("/<int:run_id>/logs")
def get_run_log(run_id: int):
    return jsonify({"log": _manager().get_run_log(run_id, tail_lines=_optional_tail_lines_arg())})


@bp.delete("/<int:run_id>/logs")
def clear_run_log(run_id: int):
    return jsonify({"log": _manager().clear_run_log(run_id)})


@bp.get("/<int:run_id>/writeup")
def get_writeup(run_id: int):
    return jsonify({"writeup": _manager().get_writeup(run_id)})


@bp.get("/<int:run_id>/writeup/download")
def download_writeup(run_id: int):
    writeup = _manager().get_writeup(run_id)
    if not writeup["available"]:
        return jsonify({"error": {"code": "not_found", "message": "Writeup not found"}}), 404
    return Response(
        writeup["content"],
        mimetype="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="run-{run_id}-writeup.md"'},
    )


@bp.get("/<int:run_id>/agent/messages")
def get_agent_messages(run_id: int):
    return jsonify({"chat": _manager().get_agent_messages(run_id)})


@bp.post("/<int:run_id>/agent/messages")
def ask_agent(run_id: int):
    return jsonify({"chat": _manager().ask_agent(run_id, request.get_json(silent=True) or {})})


def _optional_int_arg(name: str) -> int | None:
    value = request.args.get(name)
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValidationError(f"{name} must be an integer") from error
    if parsed < 1:
        raise ValidationError(f"{name} must be a positive integer")
    return parsed


def _optional_status_arg() -> str | None:
    value = request.args.get("status")
    if value is None or value == "":
        return None
    allowed = {"queued", "running", "succeeded", "failed", "cancelled", "interrupted"}
    if value not in allowed:
        raise ValidationError("status is not supported")
    return value


def _optional_bool_arg(name: str) -> bool | None:
    value = request.args.get(name)
    if value is None or value == "":
        return None
    normalized = value.lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise ValidationError(f"{name} must be true or false")


def _optional_tail_lines_arg() -> int | None:
    value = request.args.get("tail_lines")
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValidationError("tail_lines must be an integer") from error
    if parsed < 1:
        raise ValidationError("tail_lines must be a positive integer")
    return min(parsed, 10000)
