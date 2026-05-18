import time

import yaml

from backend.web.app import create_app


class BlockingRunner:
    async def run(self):
        while True:
            import asyncio

            await asyncio.sleep(1)

    def cancel(self):
        pass


def write_challenge(path):
    path.mkdir()
    (path / "metadata.yml").write_text(
        yaml.safe_dump(
            {
                "name": "Stream Run",
                "category": "misc",
                "value": 50,
                "connection_info": "",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def make_client(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "CTF_AGENT_DB_PATH": tmp_path / "web.sqlite3",
            "CTF_AGENT_RUNNER_FACTORY": lambda run, challenge, cancel_event: BlockingRunner(),
        }
    )
    return app.test_client()


def wait_for_initial_run_log(log_path):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if log_path.exists() and "running" in log_path.read_text(encoding="utf-8"):
            return
        time.sleep(0.01)
    raise AssertionError("run did not write initial running log line")


def test_run_log_stream_sends_existing_log_status_and_heartbeat(tmp_path):
    client = make_client(tmp_path)
    challenge = client.post(
        "/api/challenges", json={"path": str(write_challenge(tmp_path / "stream-run"))}
    ).get_json()["challenge"]
    run = client.post("/api/runs", json={"challenge_id": challenge["id"]}).get_json()["run"]

    log_path = tmp_path / "logs" / "runs" / f"{run['id']}.log"
    wait_for_initial_run_log(log_path)
    log_path.write_text("first line\nsecond line\n", encoding="utf-8")

    response = client.get(f"/api/runs/{run['id']}/logs/stream")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "event: log\ndata: first line\n\n" in body
    assert "event: log\ndata: second line\n\n" in body
    assert "event: status\n" in body
    assert "event: heartbeat\n" in body


def test_run_log_stream_can_start_from_tail(tmp_path):
    client = make_client(tmp_path)
    challenge = client.post(
        "/api/challenges", json={"path": str(write_challenge(tmp_path / "tail-stream-run"))}
    ).get_json()["challenge"]
    run = client.post("/api/runs", json={"challenge_id": challenge["id"]}).get_json()["run"]
    log_path = tmp_path / "logs" / "runs" / f"{run['id']}.log"
    wait_for_initial_run_log(log_path)
    log_path.write_text("one\ntwo\nthree\n", encoding="utf-8")

    response = client.get(f"/api/runs/{run['id']}/logs/stream?tail_lines=2")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "event: log\ndata: one\n\n" not in body
    assert "event: log\ndata: two\n\n" in body
    assert "event: log\ndata: three\n\n" in body
