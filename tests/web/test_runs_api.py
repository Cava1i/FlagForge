import yaml

import backend.web.routes.models as model_routes
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
                "name": "API Run",
                "category": "crypto",
                "value": 125,
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
            "CTF_AGENT_ENV_PATH": tmp_path / ".env",
            "CTF_AGENT_RUNNER_FACTORY": lambda run, challenge, cancel_event: BlockingRunner(),
        }
    )
    return app.test_client()


def test_create_list_and_get_run_api(tmp_path):
    client = make_client(tmp_path)
    challenge = client.post(
        "/api/challenges", json={"path": str(write_challenge(tmp_path / "api-run"))}
    ).get_json()["challenge"]

    create_response = client.post(
        "/api/runs",
        json={
            "challenge_id": challenge["id"],
            "model_specs": "codex/gpt-5.4",
            "no_submit": True,
            "generate_writeup": False,
        },
    )

    assert create_response.status_code == 201
    run = create_response.get_json()["run"]
    assert run["status"] == "queued"
    assert run["challenge_id"] == challenge["id"]
    assert run["model_specs"] == ["codex/gpt-5.4"]
    assert run["no_submit"] is True
    assert run["generate_writeup"] is False
    assert run["active"] is True
    assert run["can_cancel"] is True

    list_response = client.get("/api/runs")
    assert list_response.status_code == 200
    listed = list_response.get_json()["runs"][0]
    assert listed["id"] == run["id"]
    assert listed["challenge_name"] == "API Run"
    assert listed["can_cancel"] is True

    detail_response = client.get(f"/api/runs/{run['id']}")
    assert detail_response.status_code == 200
    detail = detail_response.get_json()["run"]
    assert detail["id"] == run["id"]
    assert detail["challenge_name"] == "API Run"
    assert detail["active"] is True


def test_list_runs_api_filters_by_challenge_status_and_active(tmp_path):
    client = make_client(tmp_path)
    first = client.post(
        "/api/challenges", json={"path": str(write_challenge(tmp_path / "first-run"))}
    ).get_json()["challenge"]
    second = client.post(
        "/api/challenges", json={"path": str(write_challenge(tmp_path / "second-run"))}
    ).get_json()["challenge"]
    first_run = client.post("/api/runs", json={"challenge_id": first["id"]}).get_json()["run"]
    client.post("/api/runs", json={"challenge_id": second["id"]})

    by_challenge = client.get(f"/api/runs?challenge_id={first['id']}")
    assert by_challenge.status_code == 200
    filtered = by_challenge.get_json()["runs"]
    assert [run["id"] for run in filtered] == [first_run["id"]]

    active = client.get(f"/api/runs?challenge_id={first['id']}&active=true")
    assert active.status_code == 200
    active_runs = active.get_json()["runs"]
    assert len(active_runs) == 1
    assert active_runs[0]["can_cancel"] is True

    cancelled = client.post(f"/api/runs/{first_run['id']}/cancel").get_json()["run"]
    assert cancelled["status"] == "cancelled"
    assert cancelled["can_cancel"] is False

    inactive = client.get(f"/api/runs?challenge_id={first['id']}&active=false")
    assert inactive.status_code == 200
    assert inactive.get_json()["runs"][0]["id"] == first_run["id"]


def test_list_runs_api_rejects_invalid_filters(tmp_path):
    client = make_client(tmp_path)

    assert client.get("/api/runs?challenge_id=abc").status_code == 400
    assert client.get("/api/runs?active=maybe").status_code == 400
    assert client.get("/api/runs?status=unknown").status_code == 400


def test_create_app_marks_stale_active_runs_interrupted(tmp_path):
    db_path = tmp_path / "web.sqlite3"
    client = make_client(tmp_path)
    challenge = client.post(
        "/api/challenges", json={"path": str(write_challenge(tmp_path / "stale-run"))}
    ).get_json()["challenge"]
    run = client.post("/api/runs", json={"challenge_id": challenge["id"]}).get_json()["run"]

    fresh_client = create_app(
        {
            "TESTING": True,
            "CTF_AGENT_DB_PATH": db_path,
            "CTF_AGENT_RUNNER_FACTORY": lambda run, challenge, cancel_event: BlockingRunner(),
        }
    ).test_client()

    response = fresh_client.get(f"/api/runs/{run['id']}")
    assert response.status_code == 200
    stale_run = response.get_json()["run"]
    assert stale_run["status"] == "interrupted"
    assert stale_run["finished_at"] is not None


def test_create_run_rejects_missing_challenge(tmp_path):
    client = make_client(tmp_path)

    response = client.post("/api/runs", json={"challenge_id": 404})

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_create_run_rejects_bool_challenge_id(tmp_path):
    client = make_client(tmp_path)

    response = client.post("/api/runs", json={"challenge_id": True})

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "validation_error"


def test_create_run_rejects_invalid_model_specs(tmp_path):
    client = make_client(tmp_path)
    challenge = client.post(
        "/api/challenges", json={"path": str(write_challenge(tmp_path / "invalid-models"))}
    ).get_json()["challenge"]

    response = client.post(
        "/api/runs",
        json={"challenge_id": challenge["id"], "model_specs": [{"model": "codex/gpt-5.4"}]},
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "validation_error"


def test_create_run_rejects_invalid_no_submit(tmp_path):
    client = make_client(tmp_path)
    challenge = client.post(
        "/api/challenges", json={"path": str(write_challenge(tmp_path / "invalid-submit"))}
    ).get_json()["challenge"]

    response = client.post(
        "/api/runs",
        json={"challenge_id": challenge["id"], "no_submit": "true"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "validation_error"


def test_cancel_run_api(tmp_path):
    client = make_client(tmp_path)
    challenge = client.post(
        "/api/challenges", json={"path": str(write_challenge(tmp_path / "cancel-run"))}
    ).get_json()["challenge"]
    run = client.post("/api/runs", json={"challenge_id": challenge["id"]}).get_json()["run"]

    response = client.post(f"/api/runs/{run['id']}/cancel")

    assert response.status_code == 200
    assert response.get_json()["run"]["status"] == "cancelled"


def test_run_log_view_and_clear_api(tmp_path):
    client = make_client(tmp_path)
    challenge = client.post(
        "/api/challenges", json={"path": str(write_challenge(tmp_path / "log-run"))}
    ).get_json()["challenge"]
    run = client.post("/api/runs", json={"challenge_id": challenge["id"]}).get_json()["run"]

    log_response = client.get(f"/api/runs/{run['id']}/logs")
    assert log_response.status_code == 200
    assert "queued" in log_response.get_json()["log"]["content"]

    clear_response = client.delete(f"/api/runs/{run['id']}/logs")
    assert clear_response.status_code == 200
    assert "log cleared" in clear_response.get_json()["log"]["content"]


def test_run_log_view_can_return_tail_lines(tmp_path):
    client = make_client(tmp_path)
    challenge = client.post(
        "/api/challenges", json={"path": str(write_challenge(tmp_path / "tail-log-run"))}
    ).get_json()["challenge"]
    run = client.post("/api/runs", json={"challenge_id": challenge["id"]}).get_json()["run"]
    client.post(f"/api/runs/{run['id']}/cancel")
    log_path = tmp_path / "logs" / "runs" / f"{run['id']}.log"
    log_path.write_text("one\ntwo\nthree\n", encoding="utf-8")

    response = client.get(f"/api/runs/{run['id']}/logs?tail_lines=2")

    assert response.status_code == 200
    assert response.get_json()["log"]["content"] == "two\nthree\n"


def test_run_delete_api_removes_terminal_run(tmp_path):
    client = make_client(tmp_path)
    challenge = client.post(
        "/api/challenges", json={"path": str(write_challenge(tmp_path / "delete-run"))}
    ).get_json()["challenge"]
    run = client.post("/api/runs", json={"challenge_id": challenge["id"]}).get_json()["run"]
    client.post(f"/api/runs/{run['id']}/cancel")

    response = client.delete(f"/api/runs/{run['id']}")

    assert response.status_code == 200
    assert client.get(f"/api/runs/{run['id']}").status_code == 404


def test_writeup_download_api_returns_markdown(tmp_path):
    client = make_client(tmp_path)
    challenge = client.post(
        "/api/challenges", json={"path": str(write_challenge(tmp_path / "writeup-run"))}
    ).get_json()["challenge"]
    run = client.post("/api/runs", json={"challenge_id": challenge["id"]}).get_json()["run"]
    writeup_path = tmp_path / "writeups" / "run.md"
    writeup_path.parent.mkdir()
    writeup_path.write_text("# Demo\n", encoding="utf-8")
    manager = client.application.config["run_manager"]
    manager.run_repo.update(run["id"], {"writeup_path": str(writeup_path)})

    response = client.get(f"/api/runs/{run['id']}/writeup/download")

    assert response.status_code == 200
    assert response.mimetype == "text/markdown"
    assert response.get_data(as_text=True) == "# Demo\n"


def test_models_api_keeps_default_model_separate_from_unavailable_catalog(tmp_path):
    client = make_client(tmp_path)

    response = client.get("/api/models")

    assert response.status_code == 200
    body = response.get_json()
    assert body["default_models"] == ["openai/gpt-5.5"]
    assert body["models"] == []
    assert body["source"] == "fallback"
    assert body["model_count"] == 0


def test_models_api_reads_openai_compatible_model_list(tmp_path, monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"id": "gpt-5.5"}, {"id": "gpt-5.5-mini"}]}

    def fake_get(url, headers, timeout):
        assert url == "https://proxy.example/v1/models"
        assert headers["Authorization"] == "Bearer sk-test"
        assert timeout == 3
        return FakeResponse()

    monkeypatch.setattr(model_routes.httpx, "get", fake_get)
    client = make_client(tmp_path)
    (tmp_path / ".env").write_text(
        "OPENAI_BASE_URL=https://proxy.example/v1\nOPENAI_API_KEY=sk-test\n",
        encoding="utf-8",
    )

    response = client.get("/api/models")

    assert response.status_code == 200
    body = response.get_json()
    assert body["source"] == "api"
    assert body["model_ids"] == ["gpt-5.5", "gpt-5.5-mini"]
    assert body["models"] == ["openai/gpt-5.5", "openai/gpt-5.5-mini"]


def test_models_api_tries_v1_models_when_base_url_has_no_v1(tmp_path, monkeypatch):
    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            if self.payload is None:
                raise RuntimeError("not found")

        def json(self):
            return self.payload

    seen_urls = []

    def fake_get(url, headers, timeout):
        seen_urls.append(url)
        if url.endswith("/v1/models"):
            return FakeResponse({"data": [{"id": "gpt-5.5"}]})
        return FakeResponse(None)

    monkeypatch.setattr(model_routes.httpx, "get", fake_get)
    client = make_client(tmp_path)
    (tmp_path / ".env").write_text(
        "OPENAI_BASE_URL=https://proxy.example\nOPENAI_API_KEY=sk-test\n",
        encoding="utf-8",
    )

    response = client.get("/api/models")

    assert response.status_code == 200
    assert response.get_json()["models"] == ["openai/gpt-5.5"]
    assert seen_urls == ["https://proxy.example/models", "https://proxy.example/v1/models"]


def test_models_test_api_reports_openai_compatible_success(tmp_path, monkeypatch):
    class FakeResponse:
        elapsed = type("Elapsed", (), {"total_seconds": lambda self: 0.123})()

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"id": "gpt-5.5"}, {"id": "gpt-5.5-mini"}]}

    seen_urls = []

    def fake_get(url, headers, timeout):
        seen_urls.append(url)
        assert headers["Authorization"] == "Bearer sk-test"
        assert timeout == 5
        return FakeResponse()

    monkeypatch.setattr(model_routes.httpx, "get", fake_get)
    client = make_client(tmp_path)
    (tmp_path / ".env").write_text(
        "OPENAI_BASE_URL=https://proxy.example/v1\nOPENAI_API_KEY=sk-test\n",
        encoding="utf-8",
    )

    response = client.post("/api/models/test")

    assert response.status_code == 200
    body = response.get_json()["test"]
    assert body["ok"] is True
    assert body["source"] == "api"
    assert body["model_count"] == 2
    assert body["sample_models"] == ["gpt-5.5", "gpt-5.5-mini"]
    assert body["checked_url"] == "https://proxy.example/v1/models"
    assert seen_urls == ["https://proxy.example/v1/models"]


def test_models_test_api_reports_missing_credentials(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = make_client(tmp_path)

    response = client.post("/api/models/test")

    assert response.status_code == 200
    body = response.get_json()["test"]
    assert body["ok"] is False
    assert body["error"] == "OPENAI_BASE_URL or OPENAI_API_KEY is not configured"
