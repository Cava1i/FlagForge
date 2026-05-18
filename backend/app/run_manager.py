"""Run lifecycle manager for the web API."""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
import threading
import time
from pathlib import Path
from typing import Any

from backend.app.agent_session import AgentSession
from backend.app.challenge_service import NotFoundError, ValidationError
from backend.app.run_logs import (
    RunLogStore,
    format_solver_trace_line,
    runner_log_paths,
    sse_event,
    utc_now,
)
from backend.app.skill_catalog import DEFAULT_SKILL_ROOTS, list_available_skill_names
from backend.app.swarm_runner import RunnerFactory, SwarmRunner
from backend.config import Settings
from backend.models import DEFAULT_MODELS
from backend.solver_base import FLAG_FOUND
from backend.storage.challenge_repo import ChallengeRepo
from backend.storage.run_repo import RunRepo

TERMINAL_STATUSES = {"succeeded", "failed", "cancelled", "interrupted"}


class RunManager:
    def __init__(
        self,
        run_repo: RunRepo,
        challenge_repo: ChallengeRepo,
        *,
        runner_factory: RunnerFactory | None = None,
        log_dir: str | Path = "logs/runs",
        solver_log_poll_interval: float = 0.5,
        skill_roots: list[str | Path] | tuple[str | Path, ...] | None = None,
        env_path: str | Path | None = None,
    ) -> None:
        self.run_repo = run_repo
        self.challenge_repo = challenge_repo
        self.runner_factory = runner_factory or self._create_swarm_runner
        self.logs = RunLogStore(log_dir)
        self.log_dir = self.logs.directory
        self.solver_log_poll_interval = solver_log_poll_interval
        self.skill_roots = tuple(Path(root) for root in (skill_roots or DEFAULT_SKILL_ROOTS))
        self.env_path = Path(env_path) if env_path else None
        self.active_runs: dict[int, dict[str, Any]] = {}
        self.agent_sessions: dict[int, AgentSession] = {}
        self._active_lock = threading.Lock()

    def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValidationError("Request body must be a JSON object")

        challenge_id = payload.get("challenge_id")
        if isinstance(challenge_id, bool) or not isinstance(challenge_id, int):
            raise ValidationError("challenge_id is required")

        challenge = self.challenge_repo.get(challenge_id)
        if challenge is None:
            raise NotFoundError("Challenge not found")

        model_specs = self._validate_model_specs(payload.get("model_specs"))
        agent_skills = self._validate_agent_skills(payload.get("agent_skills"))
        no_submit = self._validate_no_submit(payload.get("no_submit", False))
        generate_writeup = self._validate_generate_writeup(payload.get("generate_writeup", True))
        run = self.run_repo.create(
            {
                "challenge_id": challenge_id,
                "status": "queued",
                "executor": "swarm",
                "model_specs": model_specs,
                "no_submit": no_submit,
                "generate_writeup": generate_writeup,
                "agent_skills": agent_skills,
                "summary": "Queued for execution",
            }
        )
        log_path = self._log_path(run["id"])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.touch(exist_ok=True)
        run = self.run_repo.update(run["id"], {"log_path": str(log_path)}) or run
        self._append_log(run["id"], "queued")

        cancel_event = threading.Event()
        thread = threading.Thread(
            target=self._run_in_thread,
            args=(run["id"], challenge, cancel_event),
            name=f"ctf-run-{run['id']}",
            daemon=True,
        )
        with self._active_lock:
            self.active_runs[run["id"]] = {
                "cancel_event": cancel_event,
                "runner": None,
                "thread": thread,
            }
        thread.start()
        return self._with_runtime_state(run)

    def list_runs(
        self,
        *,
        challenge_id: int | None = None,
        status: str | None = None,
        active: bool | None = None,
    ) -> list[dict[str, Any]]:
        runs = [
            self._with_runtime_state(run)
            for run in self.run_repo.list(challenge_id=challenge_id, status=status)
        ]
        if active is not None:
            runs = [run for run in runs if run["active"] is active]
        return runs

    def get_run(self, run_id: int) -> dict[str, Any]:
        run = self.run_repo.get(run_id)
        if run is None:
            raise NotFoundError("Run not found")
        return self._with_runtime_state(run)

    def cancel_run(self, run_id: int) -> dict[str, Any]:
        run = self.get_run(run_id)
        if run["status"] in TERMINAL_STATUSES:
            return run

        active = self.active_runs.get(run_id)
        if active is not None:
            active["cancel_event"].set()
            runner = active.get("runner")
            if runner is not None and hasattr(runner, "cancel"):
                runner.cancel()

        self._append_log(run_id, "cancel requested")
        cancelled = self.run_repo.update(
            run_id,
            {
                "status": "cancelled",
                "summary": "Run cancelled",
                "finished_at": self._now(),
            },
        )
        return self._with_runtime_state(cancelled) if cancelled else self.get_run(run_id)

    def get_run_log(self, run_id: int, *, tail_lines: int | None = None) -> dict[str, Any]:
        run = self.get_run(run_id)
        log_path = Path(run["log_path"] or self._log_path(run_id))
        content = self._read_log_content(log_path, tail_lines=tail_lines)
        return {"run_id": run_id, "path": str(log_path), "content": content}

    def clear_run_log(self, run_id: int) -> dict[str, Any]:
        run = self.get_run(run_id)
        log_path = Path(run["log_path"] or self._log_path(run_id))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("", encoding="utf-8")
        self._append_log(run_id, "log cleared")
        return self.get_run_log(run_id)

    def delete_run(self, run_id: int) -> dict[str, Any]:
        run = self.get_run(run_id)
        if run["active"]:
            raise ValidationError("Stop the run before deleting it")

        self._close_agent_session(run_id)
        self._delete_run_artifacts(run)
        if not self.run_repo.delete(run_id):
            raise NotFoundError("Run not found")
        return run

    def delete_runs_for_challenge(self, challenge_id: int) -> int:
        runs = self.list_runs(challenge_id=challenge_id)
        active = [run for run in runs if run["active"]]
        if active:
            raise ValidationError("Stop active runs before deleting the challenge")

        for run in runs:
            self._close_agent_session(run["id"])
            self._delete_run_artifacts(run)
        return self.run_repo.delete_by_challenge(challenge_id)

    def get_writeup(self, run_id: int) -> dict[str, Any]:
        run = self.get_run(run_id)
        path_value = run.get("writeup_path")
        content = ""
        if path_value:
            path = Path(path_value)
            content = path.read_text(encoding="utf-8") if path.exists() else ""
        return {
            "run_id": run_id,
            "path": path_value,
            "content": content,
            "available": bool(content),
        }

    def get_agent_messages(self, run_id: int) -> dict[str, Any]:
        run = self.get_run(run_id)
        session = self.agent_sessions.get(run_id)
        return {
            "run_id": run_id,
            "available": bool(session and not session.closed),
            "model": session.model_spec if session else run.get("winning_agent"),
            "messages": list(session.messages) if session else [],
        }

    def ask_agent(self, run_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValidationError("Request body must be a JSON object")
        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            raise ValidationError("message must be a non-empty string")

        session = self.agent_sessions.get(run_id)
        if session is None or session.closed:
            raise ValidationError("Agent session is not available for this run")

        answer = session.ask(message.strip())
        self.run_repo.update(run_id, {"agent_session_available": True})
        return {
            "run_id": run_id,
            "model": session.model_spec,
            "message": {"role": "agent", "content": answer},
            "messages": list(session.messages),
        }

    def stream_log_events(
        self,
        run_id: int,
        *,
        testing: bool = False,
        tail_lines: int | None = 800,
    ):
        run = self.get_run(run_id)
        log_path = Path(run["log_path"] or self._log_path(run_id))
        position = 0

        if log_path.exists():
            position = self._initial_stream_position(log_path, tail_lines)
            with log_path.open(encoding="utf-8") as handle:
                handle.seek(position)
                while line := handle.readline():
                    position = handle.tell()
                    yield self._sse("log", line.rstrip("\n"))

        yield self._sse("status", json.dumps(self.get_run(run_id)))
        yield self._sse("heartbeat", self._now())
        if testing:
            return

        while True:
            run = self.get_run(run_id)
            if log_path.exists():
                with log_path.open(encoding="utf-8") as handle:
                    handle.seek(position)
                    while line := handle.readline():
                        position = handle.tell()
                        yield self._sse("log", line.rstrip("\n"))
            yield self._sse("status", json.dumps(run))
            if run["status"] in TERMINAL_STATUSES:
                return
            yield self._sse("heartbeat", self._now())
            time.sleep(1)

    def _run_in_thread(
        self,
        run_id: int,
        challenge: dict[str, Any],
        cancel_event: threading.Event,
    ) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._execute_run(run_id, challenge, cancel_event))
        except NotFoundError:
            return
        finally:
            with self._active_lock:
                self.active_runs.pop(run_id, None)
            session = self.agent_sessions.get(run_id)
            if session is not None and session.loop is loop and not session.closed:
                loop.run_forever()
            loop.close()

    async def _execute_run(
        self,
        run_id: int,
        challenge: dict[str, Any],
        cancel_event: threading.Event,
    ) -> None:
        current = self.get_run(run_id)
        runner = self.runner_factory(current, challenge, cancel_event)
        with self._active_lock:
            if run_id in self.active_runs:
                self.active_runs[run_id]["runner"] = runner

        if cancel_event.is_set() or current["status"] == "cancelled":
            self._finish_cancelled(run_id)
            return

        self.run_repo.update(run_id, {"status": "running", "started_at": self._now()})
        self._append_log(run_id, "running")
        mirror_task = asyncio.create_task(self._mirror_solver_logs(run_id, runner))
        try:
            result = await runner.run()
        except Exception as error:
            await self._stop_mirror_task(mirror_task)
            if cancel_event.is_set():
                self._finish_cancelled(run_id)
            else:
                self._append_log(run_id, f"failed: {error}")
                self.run_repo.update(
                    run_id,
                    {
                        "status": "failed",
                        "summary": "Run failed",
                        "error_summary": str(error),
                        "finished_at": self._now(),
                    },
                )
            return

        if cancel_event.is_set() or getattr(result, "status", None) == "cancelled":
            await self._stop_mirror_task(mirror_task)
            self._finish_cancelled(run_id)
            return

        status = "succeeded" if getattr(result, "status", None) == FLAG_FOUND else "failed"
        writeup_path = None
        winning_agent = getattr(result, "winning_model_spec", None)
        agent_session_available = self._register_agent_session(run_id, result)
        if status == "succeeded" and current.get("generate_writeup", True):
            writeup_path = await self._generate_writeup(run_id, challenge, result)
        elif status == "succeeded":
            self._append_log(run_id, "writeup generation skipped")
        await self._stop_mirror_task(mirror_task)
        self._append_log(run_id, status)
        self.run_repo.update(
            run_id,
            {
                "status": status,
                "result_flag": getattr(result, "flag", None),
                "summary": getattr(result, "findings_summary", None),
                "cost_usd": getattr(result, "cost_usd", None),
                "writeup_path": str(writeup_path) if writeup_path else None,
                "winning_agent": winning_agent,
                "agent_session_available": agent_session_available,
                "finished_at": self._now(),
            },
        )

    def _finish_cancelled(self, run_id: int) -> None:
        self._append_log(run_id, "cancelled")
        self.run_repo.update(
            run_id,
            {
                "status": "cancelled",
                "summary": "Run cancelled",
                "finished_at": self._now(),
            },
        )

    def _with_runtime_state(self, run: dict[str, Any]) -> dict[str, Any]:
        terminal = run["status"] in TERMINAL_STATUSES
        with self._active_lock:
            active = not terminal and run["id"] in self.active_runs
        return {
            **run,
            "active": active,
            "can_cancel": not terminal,
            "agent_session_available": run["id"] in self.agent_sessions,
        }

    def _register_agent_session(self, run_id: int, result: Any) -> bool:
        solver = getattr(result, "agent_session", None)
        ask = getattr(solver, "ask_followup", None)
        if solver is None or not callable(ask):
            return False
        model_spec = getattr(result, "winning_model_spec", None) or getattr(solver, "model_spec", "agent")
        self.agent_sessions[run_id] = AgentSession(
            run_id=run_id,
            model_spec=model_spec,
            solver=solver,
            loop=asyncio.get_running_loop(),
        )
        return True

    def _close_agent_session(self, run_id: int) -> None:
        session = self.agent_sessions.pop(run_id, None)
        if session is not None:
            session.close()

    def _delete_run_artifacts(self, run: dict[str, Any]) -> None:
        for key in ("log_path", "writeup_path"):
            path_value = run.get(key)
            if path_value:
                Path(path_value).unlink(missing_ok=True)

    async def _generate_writeup(
        self,
        run_id: int,
        challenge: dict[str, Any],
        result: Any,
    ) -> Path:
        writeup_path = self._writeup_path(run_id)
        writeup_path.parent.mkdir(parents=True, exist_ok=True)
        flag = getattr(result, "flag", None) or "未记录"
        summary = getattr(result, "findings_summary", None) or "暂无摘要"
        agent = getattr(result, "winning_model_spec", None) or "unknown-agent"

        content = (
            f"# {challenge.get('name', f'Run {run_id}')} Writeup\n\n"
            f"- 题目：{challenge.get('name', '-')}\n"
            f"- 分类：{challenge.get('category') or '-'}\n"
            f"- 解题 Agent：{agent}\n"
            f"- Flag：`{flag}`\n\n"
            "## 解题摘要\n\n"
            f"{summary}\n\n"
            "## 复盘说明\n\n"
            "当前 agent 会话没有返回额外 writeup，以上内容来自最终结果摘要。\n"
        )

        agent_session = getattr(result, "agent_session", None)
        ask = getattr(agent_session, "ask_followup", None)
        if callable(ask):
            prompt = self._settings().flagforge_writeup_prompt
            try:
                generated = await asyncio.wait_for(ask(prompt), timeout=300)
                if isinstance(generated, str) and generated.strip():
                    content = generated.strip() + "\n"
            except Exception as error:
                self._append_log(run_id, f"writeup generation failed: {error}")

        writeup_path.write_text(content, encoding="utf-8")
        self._append_log(run_id, f"writeup generated: {writeup_path}")
        return writeup_path

    def _create_swarm_runner(
        self,
        run: dict[str, Any],
        challenge: dict[str, Any],
        cancel_event: threading.Event,
    ) -> SwarmRunner:
        return SwarmRunner(run, challenge, cancel_event)

    async def _stop_mirror_task(self, task: asyncio.Task) -> None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def _mirror_solver_logs(self, run_id: int, runner: Any) -> None:
        positions: dict[Path, int] = {}
        try:
            while True:
                self._flush_solver_logs(run_id, runner, positions)
                await asyncio.sleep(self.solver_log_poll_interval)
        except asyncio.CancelledError:
            self._flush_solver_logs(run_id, runner, positions)
            raise

    def _flush_solver_logs(self, run_id: int, runner: Any, positions: dict[Path, int]) -> None:
        for path in runner_log_paths(runner):
            if not path.exists() or not path.is_file():
                continue

            position = positions.get(path, 0)
            with path.open(encoding="utf-8") as handle:
                handle.seek(position)
                while line := handle.readline():
                    formatted = format_solver_trace_line(path, line)
                    if formatted:
                        self._append_log(run_id, formatted)
                    position = handle.tell()
            positions[path] = position

    def _validate_model_specs(self, value: Any) -> list[str]:
        if value is None:
            return self._configured_model_specs()
        if isinstance(value, str):
            if not value.strip():
                raise ValidationError("model_specs must not be empty")
            return [self._normalize_model_spec(value)]
        if isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value):
            return [self._normalize_model_spec(item) for item in value]
        raise ValidationError("model_specs must be a string or list of strings")

    def _configured_model_specs(self) -> list[str]:
        settings = self._settings()
        models = [
            self._normalize_model_spec(model)
            for model in (self._parse_list(settings.flagforge_agent_models) or list(DEFAULT_MODELS))
        ]
        count = settings.flagforge_agent_count
        if count < 1:
            raise ValidationError("FLAGFORGE_AGENT_COUNT must be at least 1")
        if count > 12:
            raise ValidationError("FLAGFORGE_AGENT_COUNT must be at most 12")
        return [models[index % len(models)] for index in range(count)]

    def _normalize_model_spec(self, value: str) -> str:
        model = value.strip()
        return model if "/" in model else f"openai/{model}"

    def _validate_agent_skills(self, value: Any) -> list[str]:
        if value is None:
            configured = self._parse_list(self._settings().flagforge_agent_skills)
            return configured or list_available_skill_names(self.skill_roots)
        if isinstance(value, str):
            return self._parse_list(value)
        if isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value):
            return self._dedupe_list(value)
        raise ValidationError("agent_skills must be a string or list of strings")

    def _validate_no_submit(self, value: Any) -> bool:
        if not isinstance(value, bool):
            raise ValidationError("no_submit must be a boolean")
        return value

    def _validate_generate_writeup(self, value: Any) -> bool:
        if not isinstance(value, bool):
            raise ValidationError("generate_writeup must be a boolean")
        return value

    def _settings(self) -> Settings:
        settings = Settings(_env_file=self.env_path) if self.env_path else Settings()
        if self.env_path and self.env_path.exists():
            from backend.app.config_service import ConfigService

            for key, value in ConfigService(self.env_path).read_values().items():
                attr = key.lower()
                if attr not in Settings.model_fields:
                    continue
                current = getattr(settings, attr)
                if isinstance(current, bool):
                    parsed: object = value.lower() in {"1", "true", "yes", "on"}
                elif isinstance(current, int) and not isinstance(current, bool):
                    try:
                        parsed = int(value)
                    except ValueError:
                        continue
                else:
                    parsed = value
                setattr(settings, attr, parsed)
        return settings

    def _append_log(self, run_id: int, message: str) -> None:
        self.logs.append(run_id, message)

    def _log_path(self, run_id: int) -> Path:
        return self.logs.path_for(run_id)

    def _read_log_content(self, path: Path, *, tail_lines: int | None = None) -> str:
        return self.logs.read_content(path, tail_lines=tail_lines)

    def _initial_stream_position(self, path: Path, tail_lines: int | None) -> int:
        return self.logs.initial_stream_position(path, tail_lines)

    def _writeup_path(self, run_id: int) -> Path:
        return self.log_dir.parent / "writeups" / f"{run_id}.md"

    def _sse(self, event: str, data: str) -> str:
        return sse_event(event, data)

    def _now(self) -> str:
        return utc_now()

    def _parse_list(self, value: str | None) -> list[str]:
        if not value:
            return []
        return self._dedupe_list(re.split(r"[\n,]", value))

    def _dedupe_list(self, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            text = str(value).strip()
            if text and text not in result:
                result.append(text)
        return result
