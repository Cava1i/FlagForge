"""SQLite repository for run records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.storage.db import connect


class RunRepo:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def create(self, run: dict[str, Any]) -> dict[str, Any]:
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO runs
                    (
                        challenge_id, status, executor, model_specs, no_submit,
                        generate_writeup, result_flag, summary, error_summary, cost_usd, log_path,
                        writeup_path, winning_agent, agent_session_available,
                        agent_skills,
                        started_at, finished_at
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run["challenge_id"],
                    run["status"],
                    run["executor"],
                    json.dumps(run.get("model_specs", [])),
                    int(run.get("no_submit", False)),
                    int(run.get("generate_writeup", True)),
                    run.get("result_flag"),
                    run.get("summary"),
                    run.get("error_summary"),
                    run.get("cost_usd"),
                    run.get("log_path"),
                    run.get("writeup_path"),
                    run.get("winning_agent"),
                    int(run.get("agent_session_available", False)),
                    json.dumps(run.get("agent_skills", [])),
                    run.get("started_at"),
                    run.get("finished_at"),
                ),
            )
            run_id = cursor.lastrowid
        result = self.get(run_id)
        if result is None:
            raise RuntimeError("run create failed")
        return result

    def list(
        self,
        *,
        challenge_id: int | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        values: list[Any] = []
        if challenge_id is not None:
            where.append("r.challenge_id = ?")
            values.append(challenge_id)
        if status is not None:
            where.append("r.status = ?")
            values.append(status)
        where_clause = f"WHERE {' AND '.join(where)}" if where else ""

        with connect(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT r.id, r.challenge_id, c.name AS challenge_name,
                       r.status, r.executor, r.model_specs, r.no_submit,
                       r.generate_writeup,
                       r.result_flag, r.summary, r.error_summary, r.cost_usd, r.log_path,
                       r.writeup_path, r.winning_agent, r.agent_session_available,
                       r.agent_skills,
                       r.started_at, r.finished_at, r.created_at, r.updated_at
                FROM runs AS r
                LEFT JOIN challenges AS c ON c.id = r.challenge_id
                {where_clause}
                ORDER BY r.id ASC
                """,
                values,
            ).fetchall()
        return [self._row_to_run(row) for row in rows]

    def get(self, run_id: int) -> dict[str, Any] | None:
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT r.id, r.challenge_id, c.name AS challenge_name,
                       r.status, r.executor, r.model_specs, r.no_submit,
                       r.generate_writeup,
                       r.result_flag, r.summary, r.error_summary, r.cost_usd, r.log_path,
                       r.writeup_path, r.winning_agent, r.agent_session_available,
                       r.agent_skills,
                       r.started_at, r.finished_at, r.created_at, r.updated_at
                FROM runs AS r
                LEFT JOIN challenges AS c ON c.id = r.challenge_id
                WHERE r.id = ?
                """,
                (run_id,),
            ).fetchone()
        return self._row_to_run(row) if row else None

    def update(self, run_id: int, fields: dict[str, Any]) -> dict[str, Any] | None:
        allowed = {
            "status",
            "result_flag",
            "summary",
            "error_summary",
            "cost_usd",
            "log_path",
            "writeup_path",
            "winning_agent",
            "agent_session_available",
            "agent_skills",
            "generate_writeup",
            "started_at",
            "finished_at",
        }
        updates = {key: value for key, value in fields.items() if key in allowed}
        if "agent_session_available" in updates:
            updates["agent_session_available"] = int(bool(updates["agent_session_available"]))
        if "generate_writeup" in updates:
            updates["generate_writeup"] = int(bool(updates["generate_writeup"]))
        if "agent_skills" in updates:
            updates["agent_skills"] = json.dumps(updates["agent_skills"])
        if not updates:
            return self.get(run_id)

        assignments = ", ".join(f"{key} = ?" for key in updates)
        values = list(updates.values())
        values.append(run_id)
        terminal_guard = ""
        if updates.get("status") in {"queued", "running"}:
            terminal_guard = "AND status NOT IN ('succeeded', 'failed', 'cancelled', 'interrupted')"
        with connect(self.db_path) as connection:
            connection.execute(
                f"""
                UPDATE runs
                SET {assignments}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                {terminal_guard}
                """,
                values,
            )
        return self.get(run_id)

    def mark_active_runs_interrupted(self) -> int:
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE runs
                SET status = 'interrupted',
                    summary = COALESCE(summary, 'Run interrupted by backend restart'),
                    error_summary = COALESCE(error_summary, 'Backend restarted before this run finished'),
                    finished_at = COALESCE(finished_at, CURRENT_TIMESTAMP),
                    updated_at = CURRENT_TIMESTAMP
                WHERE status IN ('queued', 'running')
                """
            )
            return cursor.rowcount

    def delete(self, run_id: int) -> bool:
        with connect(self.db_path) as connection:
            cursor = connection.execute("DELETE FROM runs WHERE id = ?", (run_id,))
            return cursor.rowcount > 0

    def delete_by_challenge(self, challenge_id: int) -> int:
        with connect(self.db_path) as connection:
            cursor = connection.execute("DELETE FROM runs WHERE challenge_id = ?", (challenge_id,))
            return cursor.rowcount

    def _row_to_run(self, row: Any) -> dict[str, Any]:
        run = dict(row)
        run["model_specs"] = json.loads(run["model_specs"] or "[]")
        run["agent_skills"] = json.loads(run.get("agent_skills") or "[]")
        run["no_submit"] = bool(run["no_submit"])
        run["generate_writeup"] = bool(run.get("generate_writeup", True))
        run["agent_session_available"] = bool(run.get("agent_session_available"))
        return run
