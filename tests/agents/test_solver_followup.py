import pytest

from backend.agents.solver import Solver
from backend.agents.swarm import ChallengeSwarm
from backend.config import Settings
from backend.cost_tracker import CostTracker
from backend.prompts import ChallengeMeta


def test_openai_api_solver_exposes_followup_for_writeup_sessions(tmp_path):
    swarm = ChallengeSwarm(
        challenge_dir=str(tmp_path),
        meta=ChallengeMeta(name="Followup"),
        ctfd=object(),
        cost_tracker=CostTracker(),
        settings=Settings(openai_api_key="sk-test"),
        model_specs=["openai/gpt5.5"],
    )

    solver = swarm._create_solver("openai/gpt5.5")

    assert callable(getattr(solver, "ask_followup", None))


@pytest.mark.asyncio
async def test_pydantic_solver_followup_uses_free_text_output_and_keeps_history():
    class FakeAgent:
        def __init__(self):
            self.calls = []

        async def run(self, prompt, **kwargs):
            self.calls.append((prompt, kwargs))
            return FakeRunResult()

    class FakeRunResult:
        output = "# Writeup\n\n详细复盘。"

        def usage(self):
            return None

        def all_messages(self):
            return ["next-history"]

        def new_messages(self):
            return []

    solver = Solver.__new__(Solver)
    solver._agent = FakeAgent()
    solver._messages = ["existing-history"]
    solver.deps = object()
    solver.cost_tracker = CostTracker()
    solver.agent_name = "Followup/gpt5.5"
    solver.model_id = "gpt5.5"
    solver.model_spec = "openai/gpt5.5"
    solver._findings = ""

    answer = await solver.ask_followup("写一份 writeup")

    assert answer == "# Writeup\n\n详细复盘。"
    assert solver._messages == ["next-history"]
    assert solver._agent.calls[0][0] == "写一份 writeup"
    assert solver._agent.calls[0][1]["output_type"] is str
    assert solver._agent.calls[0][1]["message_history"] == ["existing-history"]
