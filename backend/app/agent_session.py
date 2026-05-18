"""Follow-up chat session wrapper for completed solver runs."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentSession:
    run_id: int
    model_spec: str
    solver: Any
    loop: asyncio.AbstractEventLoop
    messages: list[dict[str, str]] = field(default_factory=list)
    closed: bool = False

    def ask(self, message: str, timeout: int = 300) -> str:
        if self.closed:
            raise RuntimeError("Agent session is closed")
        future = asyncio.run_coroutine_threadsafe(self.solver.ask_followup(message), self.loop)
        answer = future.result(timeout=timeout)
        self.messages.append({"role": "user", "content": message})
        self.messages.append({"role": "agent", "content": answer})
        return answer

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        future = asyncio.run_coroutine_threadsafe(self.solver.stop(), self.loop)
        with contextlib.suppress(Exception):
            future.result(timeout=15)
        self.loop.call_soon_threadsafe(self.loop.stop)

