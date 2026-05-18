from backend.web.app import create_app


def make_client(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "CTF_AGENT_DB_PATH": tmp_path / "web.sqlite3",
            "CTF_AGENT_ENV_PATH": tmp_path / ".env",
        }
    )
    return app.test_client()


def test_get_config_masks_sensitive_values(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=sk-test\nCTFD_URL=https://ctf.example\n", encoding="utf-8")
    client = make_client(tmp_path)

    response = client.get("/api/config")

    assert response.status_code == 200
    config = response.get_json()["config"]
    assert config["fields"]["OPENAI_API_KEY"]["configured"] is True
    assert "value" not in config["fields"]["OPENAI_API_KEY"]
    assert config["fields"]["CTFD_URL"]["value"] == "https://ctf.example"


def test_get_config_secret_reveals_sensitive_value(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=sk-local-secret\n", encoding="utf-8")
    client = make_client(tmp_path)

    response = client.get("/api/config/secrets/OPENAI_API_KEY")

    assert response.status_code == 200
    assert response.get_json()["secret"]["value"] == "sk-local-secret"


def test_get_config_secret_rejects_non_sensitive_value(tmp_path):
    client = make_client(tmp_path)

    response = client.get("/api/config/secrets/OPENAI_BASE_URL")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "validation_error"


def test_put_config_saves_values(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = make_client(tmp_path)

    response = client.put(
        "/api/config",
        json={
            "values": {
                "OPENAI_API_KEY": "sk-new",
                "ANTHROPIC_BASE_URL": "https://anthropic.example",
                "FLAGFORGE_WRITEUP_PROMPT": "请输出中文复盘。",
            }
        },
    )

    assert response.status_code == 200
    config = response.get_json()["config"]
    assert config["fields"]["OPENAI_API_KEY"]["configured"] is True
    assert config["fields"]["ANTHROPIC_BASE_URL"]["value"] == "https://anthropic.example"
    assert config["fields"]["FLAGFORGE_WRITEUP_PROMPT"]["value"] == "请输出中文复盘。"
    assert "OPENAI_API_KEY=sk-new" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_put_config_rejects_invalid_payload(tmp_path):
    client = make_client(tmp_path)

    response = client.put("/api/config", json={"values": {"BAD_KEY": "value"}})

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "validation_error"
