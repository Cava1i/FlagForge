from backend.web.app import create_app


def test_serves_built_frontend_shell_and_api_still_works(tmp_path):
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text(
        '<div id="app"></div><script type="module" src="/assets/app.js"></script>',
        encoding="utf-8",
    )
    (assets / "app.js").write_text("console.log('ctf-agent')", encoding="utf-8")

    app = create_app(
        {
            "TESTING": True,
            "CTF_AGENT_DB_PATH": tmp_path / "web.sqlite3",
            "CTF_AGENT_FRONTEND_DIST": dist,
        }
    )
    client = app.test_client()

    shell = client.get("/runs/123")
    assert shell.status_code == 200
    assert '<div id="app"></div>' in shell.get_data(as_text=True)

    asset = client.get("/assets/app.js")
    assert asset.status_code == 200
    assert "ctf-agent" in asset.get_data(as_text=True)

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.get_json() == {"status": "ok"}
