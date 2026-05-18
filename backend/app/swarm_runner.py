"""Runner adapter that connects web run records to the solver swarm."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

RunnerFactory = Callable[[dict[str, Any], dict[str, Any], threading.Event], Any]


class SwarmRunner:
    def __init__(self, run: dict[str, Any], challenge: dict[str, Any], cancel_event: threading.Event) -> None:
        self.run_record = run
        self.challenge = challenge
        self.cancel_event = cancel_event
        self.swarm: Any | None = None

    async def run(self) -> Any:
        from backend.agents.swarm import ChallengeSwarm
        from backend.config import Settings
        from backend.cost_tracker import CostTracker
        from backend.ctfd import CTFdClient
        from backend.prompts import ChallengeMeta
        from backend.sandbox import cleanup_orphan_containers, configure_semaphore

        settings = Settings()
        model_specs = self.run_record["model_specs"]
        agent_skills = self.run_record.get("agent_skills", [])
        configure_semaphore(len(model_specs))
        await cleanup_orphan_containers()

        challenge_path = Path(self.challenge["path"])
        meta = ChallengeMeta.from_yaml(challenge_path / "metadata.yml")
        ctfd = CTFdClient(
            base_url=settings.ctfd_url,
            token=settings.ctfd_token,
            username=settings.ctfd_user,
            password=settings.ctfd_pass,
        )
        cost_tracker = CostTracker()
        self.swarm = ChallengeSwarm(
            challenge_dir=str(challenge_path),
            meta=meta,
            ctfd=ctfd,
            cost_tracker=cost_tracker,
            settings=settings,
            model_specs=model_specs,
            agent_skills=agent_skills,
            no_submit=self.run_record["no_submit"],
        )

        try:
            result = await self.swarm.run()
            if result is not None and getattr(result, "cost_usd", None) is None:
                result.cost_usd = cost_tracker.total_cost_usd
            return result
        finally:
            await ctfd.close()

    def cancel(self) -> None:
        self.cancel_event.set()
        if self.swarm is not None:
            self.swarm.kill()

    def get_log_paths(self) -> list[Path]:
        if self.swarm is None:
            return []

        paths: list[Path] = []
        for solver in self.swarm.solvers.values():
            tracer = getattr(solver, "tracer", None)
            path = getattr(tracer, "path", None)
            if path:
                paths.append(Path(path))
        return paths

