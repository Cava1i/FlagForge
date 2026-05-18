import json
from pathlib import Path

import pytest

from backend.app.challenge_service import ValidationError
from backend.app.run_logs import RunLogStore, format_solver_trace_line, runner_log_paths


def test_run_log_store_reads_tail_and_tracks_initial_stream_position(tmp_path):
    store = RunLogStore(tmp_path / "runs")
    path = store.path_for(7)
    path.parent.mkdir(parents=True)
    path.write_text("one\ntwo\nthree\n", encoding="utf-8")

    assert store.read_content(path, tail_lines=2) == "two\nthree\n"

    with path.open(encoding="utf-8") as handle:
        handle.seek(store.initial_stream_position(path, 2))
        assert handle.read() == "two\nthree\n"

    with pytest.raises(ValidationError):
        store.read_content(path, tail_lines=0)


def test_format_solver_trace_line_handles_structured_and_plain_trace_lines():
    path = Path("trace-mobile2-gpt5.5-20260517-184018.jsonl")
    line = json.dumps(
        {
            "type": "tool_call",
            "tool": "read_file",
            "args": '{"path": "AndroidManifest.xml"}',
            "step": 12,
        }
    )

    assert (
        format_solver_trace_line(path, line)
        == '[mobile2-gpt5.5] step 12 call read_file: {"path": "AndroidManifest.xml"}'
    )
    assert format_solver_trace_line(path, "plain trace") == "[mobile2-gpt5.5] plain trace"
    assert format_solver_trace_line(path, "") == ""


def test_runner_log_paths_prefers_explicit_runner_method(tmp_path):
    explicit = tmp_path / "explicit.jsonl"

    class Runner:
        def get_log_paths(self):
            return [explicit]

    assert runner_log_paths(Runner()) == [explicit]

