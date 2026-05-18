"""Run log storage and solver trace formatting helpers."""

from __future__ import annotations

import json
import re
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.challenge_service import ValidationError


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def sse_event(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


class RunLogStore:
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self._lock = threading.Lock()

    def append(self, run_id: int, message: str) -> None:
        timestamp = utc_now()
        path = self.path_for(run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, path.open("a", encoding="utf-8") as handle:
            handle.write(f"{timestamp} {message}\n")

    def path_for(self, run_id: int) -> Path:
        return self.directory / f"{run_id}.log"

    def read_content(self, path: Path, *, tail_lines: int | None = None) -> str:
        if not path.exists():
            return ""
        if tail_lines is None:
            return path.read_text(encoding="utf-8")
        if tail_lines < 1:
            raise ValidationError("tail_lines must be a positive integer")
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        return "".join(lines[-tail_lines:])

    def initial_stream_position(self, path: Path, tail_lines: int | None) -> int:
        if tail_lines is None:
            return 0
        if tail_lines < 1:
            raise ValidationError("tail_lines must be a positive integer")
        with path.open("rb") as handle:
            handle.seek(0, 2)
            end = handle.tell()
            if end == 0:
                return 0
            handle.seek(end - 1)
            threshold = tail_lines if handle.read(1) == b"\n" else tail_lines - 1
            count = 0
            position = end
            while position > 0:
                read_size = min(4096, position)
                position -= read_size
                handle.seek(position)
                chunk = handle.read(read_size)
                for index in range(len(chunk) - 1, -1, -1):
                    if chunk[index : index + 1] == b"\n":
                        count += 1
                        if count > threshold:
                            return position + index + 1
            return 0


def runner_log_paths(runner: Any) -> list[Path]:
    getter = getattr(runner, "get_log_paths", None)
    if callable(getter):
        return [Path(path) for path in getter()]

    swarm = getattr(runner, "swarm", None)
    solvers = getattr(swarm, "solvers", {}) if swarm is not None else {}
    paths: list[Path] = []
    for solver in solvers.values():
        tracer = getattr(solver, "tracer", None)
        path = getattr(tracer, "path", None)
        if path:
            paths.append(Path(path))
    return paths


def format_solver_trace_line(path: Path, line: str) -> str:
    raw = line.strip()
    if not raw:
        return ""

    label = trace_label(path)
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        return f"[{label}] {compact_text(raw, 800)}"

    if not isinstance(event, dict):
        return f"[{label}] {compact_text(raw, 800)}"

    event_type = str(event.get("type") or "event")
    prefix = f"[{event.get('model') or label}]"

    if event_type == "start":
        return f"{prefix} solver started"
    if event_type == "tool_call":
        return (
            f"{prefix} step {event.get('step', '?')} call {event.get('tool', '?')}: "
            f"{compact_text(str(event.get('args', '')), 800)}"
        )
    if event_type == "tool_result":
        return (
            f"{prefix} step {event.get('step', '?')} result {event.get('tool', '?')}: "
            f"{compact_text(str(event.get('result', '')), 1000)}"
        )
    if event_type == "usage":
        cost = event.get("cost_usd", 0)
        return (
            f"{prefix} usage input={event.get('input_tokens', 0)} "
            f"output={event.get('output_tokens', 0)} "
            f"cache={event.get('cache_read_tokens', 0)} cost=${cost}"
        )
    if event_type == "model_response":
        return (
            f"{prefix} step {event.get('step', '?')} model: "
            f"{compact_text(str(event.get('text', '')), 1000)}"
        )
    if event_type == "turn_complete":
        return (
            f"{prefix} turn complete duration={event.get('duration', '?')}s "
            f"steps={event.get('steps', '?')}"
        )
    if event_type == "finish":
        details = f"status={event.get('status', '?')}"
        if event.get("flag"):
            details += f" flag={event['flag']}"
        return f"{prefix} finished {details}"
    if event_type == "stop":
        return f"{prefix} solver stopped step_count={event.get('step_count', '?')}"
    if event_type in {"error", "turn_failed"}:
        return f"{prefix} {event_type}: {compact_text(str(event.get('error', '')), 1000)}"

    payload = {key: value for key, value in event.items() if key not in {"ts", "type"}}
    return f"{prefix} {event_type}: {compact_text(json.dumps(payload, ensure_ascii=False), 1000)}"


def trace_label(path: Path) -> str:
    stem = path.stem
    if stem.startswith("trace-"):
        stem = stem[len("trace-") :]
    match = re.match(r"(.+)-\d{8}-\d{6}$", stem)
    if match:
        return match.group(1)
    return stem


def compact_text(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."

