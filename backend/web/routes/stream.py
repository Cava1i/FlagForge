"""Run log streaming routes."""

from __future__ import annotations

from flask import Blueprint, Response, current_app, request

from backend.app.challenge_service import ValidationError
from backend.app.run_manager import RunManager

bp = Blueprint("run_stream", __name__, url_prefix="/api/runs")


def _manager() -> RunManager:
    return current_app.config["run_manager"]


@bp.get("/<int:run_id>/logs/stream")
def stream_run_logs(run_id: int):
    return Response(
        _manager().stream_log_events(
            run_id,
            testing=current_app.testing,
            tail_lines=_optional_tail_lines_arg(default=800),
        ),
        mimetype="text/event-stream",
    )


def _optional_tail_lines_arg(*, default: int | None) -> int | None:
    value = request.args.get("tail_lines")
    if value is None or value == "":
        return default
    if value.lower() == "all":
        return None
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValidationError("tail_lines must be an integer") from error
    if parsed < 1:
        raise ValidationError("tail_lines must be a positive integer")
    return min(parsed, 10000)
