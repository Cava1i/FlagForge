import asyncio
import json
import threading
import time

import pytest

from backend.app.challenge_service import ValidationError
from backend.app.run_manager import RunManager
from backend.storage.challenge_repo import ChallengeRepo
from backend.storage.db import bootstrap
from backend.storage.run_repo import RunRepo


class FakeResult:
    def __init__(
        self,
        *,
        flag=None,
        status="flag_found",
        findings_summary="done",
        cost_usd=1.25,
        log_path="solver.log",
        agent_session=None,
        winning_model_spec=None,
    ):
        self.flag = flag
        self.status = status
        self.findings_summary = findings_summary
        self.cost_usd = cost_usd
        self.log_path = log_path
        self.agent_session = agent_session
        self.winning_model_spec = winning_model_spec


class FakeAgentSession:
    def __init__(self):
        self.prompts = []
        self.stopped = False

    async def ask_followup(self, prompt):
        self.prompts.append(prompt)
        if "writeup" in prompt.lower():
            return "# Writeup\n\n清晰复盘。"
        return f"回答：{prompt}"

    async def stop(self):
        self.stopped = True


class FakeRunner:
    def __init__(self, result=None, error=None):
        self.result = result or FakeResult(flag="ctf{ok}")
        self.error = error
        self.started = threading.Event()
        self.release = threading.Event()
        self.cancelled = threading.Event()

    async def run(self):
        self.started.set()
        while not self.release.is_set() and not self.cancelled.is_set():
            await asyncio.sleep(0.01)
        if self.cancelled.is_set():
            return FakeResult(status="cancelled", findings_summary="cancelled")
        if self.error:
            raise self.error
        return self.result

    def cancel(self):
        self.cancelled.set()
        self.release.set()


class TraceWritingRunner(FakeRunner):
    def __init__(self, trace_path):
        super().__init__()
        self.trace_path = trace_path

    def get_log_paths(self):
        return [self.trace_path]

    async def run(self):
        self.started.set()
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "ts": time.time(),
                        "type": "tool_call",
                        "tool": "bash",
                        "args": "{\"command\":\"file ./chall\"}",
                        "step": 1,
                    }
                )
                + "\n"
            )
            handle.flush()
            await asyncio.sleep(0.05)
            handle.write(
                json.dumps(
                    {
                        "ts": time.time(),
                        "type": "tool_result",
                        "tool": "bash",
                        "result": "ELF 64-bit",
                        "step": 1,
                    }
                )
                + "\n"
            )
            handle.flush()
        while not self.release.is_set():
            await asyncio.sleep(0.01)
        return self.result


def wait_for(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        threading.Event().wait(0.01)
    raise AssertionError("condition was not reached before timeout")


def make_manager(tmp_path, runner=None, **manager_kwargs):
    db_path = tmp_path / "web.sqlite3"
    bootstrap(db_path)
    challenge_repo = ChallengeRepo(db_path)
    challenge_path = tmp_path / "run-me"
    challenge_path.mkdir()
    (challenge_path / "metadata.yml").write_text("name: Run Me\ncategory: pwn\nvalue: 100\n", encoding="utf-8")
    challenge = challenge_repo.upsert(
        {
            "name": "Run Me",
            "slug": "run-me",
            "path": str(challenge_path),
            "category": "pwn",
            "value": 100,
            "connection_info": "nc host 1234",
        }
    )
    runner_factory = (lambda run, challenge, cancel_event: runner) if runner else None
    return (
        RunManager(
            RunRepo(db_path),
            challenge_repo,
            runner_factory=runner_factory,
            log_dir=tmp_path / "logs" / "runs",
            env_path=tmp_path / ".env",
            **manager_kwargs,
        ),
        challenge,
    )


def test_create_run_record(tmp_path):
    runner = FakeRunner()
    manager, challenge = make_manager(tmp_path, runner)

    run = manager.create_run(
        {"challenge_id": challenge["id"], "model_specs": ["codex/gpt-5.4"], "no_submit": True}
    )

    assert run["challenge_id"] == challenge["id"]
    assert run["status"] == "queued"
    assert run["executor"] == "swarm"
    assert run["model_specs"] == ["codex/gpt-5.4"]
    assert run["no_submit"] is True
    assert run["generate_writeup"] is True
    assert run["log_path"].endswith(f"logs/runs/{run['id']}.log")


def test_create_run_uses_configured_agent_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("FLAGFORGE_AGENT_COUNT", "2")
    monkeypatch.setenv("FLAGFORGE_AGENT_MODELS", "codex/gpt-5.4,codex/gpt-5.4-mini,claude-sdk/claude-opus-4-6/medium")
    monkeypatch.setenv("FLAGFORGE_AGENT_SKILLS", "ctf-web,ctf-misc")
    runner = FakeRunner()
    manager, challenge = make_manager(tmp_path, runner)

    run = manager.create_run({"challenge_id": challenge["id"]})

    assert run["model_specs"] == ["codex/gpt-5.4", "codex/gpt-5.4-mini"]
    assert run["agent_skills"] == ["ctf-web", "ctf-misc"]


def test_create_run_accepts_per_run_agent_skills(tmp_path):
    runner = FakeRunner()
    manager, challenge = make_manager(tmp_path, runner)

    run = manager.create_run({"challenge_id": challenge["id"], "agent_skills": ["ctf-crypto"]})

    assert run["agent_skills"] == ["ctf-crypto"]


def test_create_run_defaults_to_all_available_skills(tmp_path, monkeypatch):
    monkeypatch.delenv("FLAGFORGE_AGENT_SKILLS", raising=False)
    skill_root = tmp_path / "skills"
    for name in ("ctf-web", "ctf-misc"):
        skill_dir = skill_root / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\n---\n# {name}\n", encoding="utf-8")
    runner = FakeRunner()
    manager, challenge = make_manager(tmp_path, runner, skill_roots=[skill_root])

    run = manager.create_run({"challenge_id": challenge["id"]})

    assert run["agent_skills"] == ["ctf-misc", "ctf-web"]


def test_create_run_can_disable_writeup_generation(tmp_path):
    runner = FakeRunner()
    manager, challenge = make_manager(tmp_path, runner)

    run = manager.create_run({"challenge_id": challenge["id"], "generate_writeup": False})

    assert run["generate_writeup"] is False


def test_list_and_get_runs(tmp_path):
    runner = FakeRunner()
    manager, challenge = make_manager(tmp_path, runner)
    run = manager.create_run({"challenge_id": challenge["id"]})

    assert manager.list_runs()[0]["id"] == run["id"]
    assert manager.get_run(run["id"])["challenge_id"] == challenge["id"]


def test_create_run_rejects_bool_challenge_id(tmp_path):
    manager, _challenge = make_manager(tmp_path, FakeRunner())

    with pytest.raises(ValidationError):
        manager.create_run({"challenge_id": True})


@pytest.mark.parametrize(
    "payload",
    [
        {"challenge_id": 1, "model_specs": [object()]},
        {"challenge_id": 1, "model_specs": {"bad": "shape"}},
        {"challenge_id": 1, "no_submit": "false"},
    ],
)
def test_create_run_validates_model_specs_and_no_submit(tmp_path, payload):
    manager, challenge = make_manager(tmp_path, FakeRunner())
    payload["challenge_id"] = challenge["id"]

    with pytest.raises(ValidationError):
        manager.create_run(payload)


def test_run_transitions_queued_running_succeeded(tmp_path):
    runner = FakeRunner(FakeResult(flag="ctf{winner}", cost_usd=2.5))
    manager, challenge = make_manager(tmp_path, runner)

    run = manager.create_run({"challenge_id": challenge["id"]})
    assert run["status"] == "queued"

    assert runner.started.wait(2)
    wait_for(lambda: manager.get_run(run["id"])["status"] == "running")

    runner.release.set()
    wait_for(lambda: manager.get_run(run["id"])["status"] == "succeeded")
    finished = manager.get_run(run["id"])
    assert finished["result_flag"] == "ctf{winner}"
    assert finished["cost_usd"] == 2.5
    assert finished["finished_at"] is not None


def test_run_log_includes_solver_trace_events_while_running(tmp_path):
    trace_path = tmp_path / "traces" / "trace-stream-run-gpt-5.4-mini-20260513-221912.jsonl"
    runner = TraceWritingRunner(trace_path)
    manager, challenge = make_manager(tmp_path, runner, solver_log_poll_interval=0.01)

    run = manager.create_run({"challenge_id": challenge["id"]})
    assert runner.started.wait(2)

    log_path = tmp_path / "logs" / "runs" / f"{run['id']}.log"
    wait_for(lambda: "call bash" in log_path.read_text(encoding="utf-8"))
    wait_for(lambda: "ELF 64-bit" in log_path.read_text(encoding="utf-8"))

    runner.release.set()
    wait_for(lambda: manager.get_run(run["id"])["status"] == "succeeded")


def test_successful_run_generates_writeup_and_keeps_agent_chat(tmp_path, monkeypatch):
    monkeypatch.delenv("FLAGFORGE_WRITEUP_PROMPT", raising=False)
    agent = FakeAgentSession()
    result = FakeResult(
        flag="ctf{winner}",
        agent_session=agent,
        winning_model_spec="codex/gpt-5.4",
    )
    runner = FakeRunner(result)
    manager, challenge = make_manager(tmp_path, runner)

    run = manager.create_run({"challenge_id": challenge["id"]})
    assert runner.started.wait(2)
    runner.release.set()
    wait_for(lambda: manager.get_run(run["id"])["status"] == "succeeded")

    finished = manager.get_run(run["id"])
    assert finished["agent_session_available"] is True
    assert finished["winning_agent"] == "codex/gpt-5.4"
    writeup = manager.get_writeup(run["id"])
    assert writeup["available"] is True
    assert "Writeup" in writeup["content"]

    chat = manager.ask_agent(run["id"], {"message": "为什么这样做？"})
    assert chat["message"]["content"] == "回答：为什么这样做？"

    manager.delete_run(run["id"])
    wait_for(lambda: agent.stopped)


def test_successful_run_uses_configured_writeup_prompt(tmp_path):
    agent = FakeAgentSession()
    result = FakeResult(
        flag="ctf{winner}",
        agent_session=agent,
        winning_model_spec="codex/gpt-5.4",
    )
    runner = FakeRunner(result)
    env_path = tmp_path / ".env"
    env_path.write_text("FLAGFORGE_WRITEUP_PROMPT=请输出一份中文教学复盘。\n", encoding="utf-8")
    manager, challenge = make_manager(tmp_path, runner)

    run = manager.create_run({"challenge_id": challenge["id"]})
    assert runner.started.wait(2)
    runner.release.set()
    wait_for(lambda: manager.get_run(run["id"])["status"] == "succeeded")

    assert agent.prompts[0] == "请输出一份中文教学复盘。"


def test_successful_run_skips_writeup_when_disabled(tmp_path):
    agent = FakeAgentSession()
    result = FakeResult(
        flag="ctf{winner}",
        agent_session=agent,
        winning_model_spec="codex/gpt-5.4",
    )
    runner = FakeRunner(result)
    manager, challenge = make_manager(tmp_path, runner)

    run = manager.create_run({"challenge_id": challenge["id"], "generate_writeup": False})
    assert runner.started.wait(2)
    runner.release.set()
    wait_for(lambda: manager.get_run(run["id"])["status"] == "succeeded")

    writeup = manager.get_writeup(run["id"])
    assert writeup["available"] is False
    assert agent.prompts == []


def test_run_with_non_flag_status_fails_even_when_flag_present(tmp_path):
    runner = FakeRunner(FakeResult(flag="ctf{unconfirmed}", status="gave_up"))
    manager, challenge = make_manager(tmp_path, runner)

    run = manager.create_run({"challenge_id": challenge["id"]})
    assert runner.started.wait(2)

    runner.release.set()
    wait_for(lambda: manager.get_run(run["id"])["status"] == "failed")


def test_run_transitions_queued_running_failed(tmp_path):
    runner = FakeRunner(error=RuntimeError("solver exploded"))
    manager, challenge = make_manager(tmp_path, runner)

    run = manager.create_run({"challenge_id": challenge["id"]})
    assert runner.started.wait(2)
    wait_for(lambda: manager.get_run(run["id"])["status"] == "running")

    runner.release.set()
    wait_for(lambda: manager.get_run(run["id"])["status"] == "failed")
    failed = manager.get_run(run["id"])
    assert "solver exploded" in failed["error_summary"]
    assert failed["finished_at"] is not None


def test_cancel_run_marks_cancelled(tmp_path):
    runner = FakeRunner()
    manager, challenge = make_manager(tmp_path, runner)

    run = manager.create_run({"challenge_id": challenge["id"]})
    assert runner.started.wait(2)

    cancelled = manager.cancel_run(run["id"])

    assert cancelled["status"] == "cancelled"
    assert runner.cancelled.is_set()
    wait_for(lambda: manager.get_run(run["id"])["status"] == "cancelled")
