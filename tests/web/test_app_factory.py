import os

from backend.web.app import create_app


def test_app_factory_returns_app(tmp_path):
    app = create_app({"TESTING": True, "CTF_AGENT_DB_PATH": tmp_path / "web.sqlite3"})

    assert app is not None


def test_health_endpoint(tmp_path):
    app = create_app({"TESTING": True, "CTF_AGENT_DB_PATH": tmp_path / "web.sqlite3"})

    response = app.test_client().get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_testing_app_does_not_export_env_file_values_to_process_env(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=sk-local\n", encoding="utf-8")

    create_app(
        {
            "TESTING": True,
            "CTF_AGENT_DB_PATH": tmp_path / "web.sqlite3",
            "CTF_AGENT_ENV_PATH": env_path,
        }
    )

    assert "OPENAI_API_KEY" not in os.environ
