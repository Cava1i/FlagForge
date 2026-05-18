"""Flask application factory for the web API."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify, send_from_directory

from backend.app.challenge_service import ChallengeService, ServiceError
from backend.app.config_service import ConfigService
from backend.app.run_manager import RunManager
from backend.storage.challenge_repo import ChallengeRepo
from backend.storage.db import bootstrap
from backend.storage.run_repo import RunRepo
from backend.web.routes.challenges import bp as challenges_bp
from backend.web.routes.config import bp as config_bp
from backend.web.routes.models import bp as models_bp
from backend.web.routes.runs import bp as runs_bp
from backend.web.routes.stream import bp as stream_bp


def create_app(config: dict | None = None) -> Flask:
    repo_root = Path(__file__).resolve().parents[2]
    frontend_dist = repo_root / "frontend" / "dist"
    app = Flask(__name__, static_folder=None)
    app.config.update(
        CTF_AGENT_DB_PATH=os.environ.get(
            "CTF_AGENT_DB_PATH",
            str(Path.cwd() / ".ctf-agent" / "web.sqlite3"),
        ),
        CTF_AGENT_CHALLENGE_ROOT=Path(
            os.environ.get("CTF_AGENT_CHALLENGE_ROOT", str(Path.cwd() / "challenges"))
        ),
        CTF_AGENT_ENV_PATH=Path(os.environ.get("CTF_AGENT_ENV_PATH", str(Path.cwd() / ".env"))),
        CTF_AGENT_FRONTEND_DIST=frontend_dist,
        CTF_AGENT_SKILL_ROOTS=None,
    )
    if config:
        app.config.update(config)

    db_path = app.config["CTF_AGENT_DB_PATH"]
    bootstrap(db_path)

    challenge_repo = ChallengeRepo(db_path)
    run_repo = RunRepo(db_path)
    run_repo.mark_active_runs_interrupted()
    app.config["challenge_service"] = ChallengeService(
        challenge_repo,
        challenge_root=app.config["CTF_AGENT_CHALLENGE_ROOT"],
    )
    config_service = ConfigService(
        app.config["CTF_AGENT_ENV_PATH"],
        skill_roots=app.config.get("CTF_AGENT_SKILL_ROOTS"),
    )
    if not app.config.get("TESTING"):
        for key, value in config_service.read_values().items():
            os.environ[key] = value
    app.config["config_service"] = config_service
    app.config["run_manager"] = RunManager(
        run_repo,
        challenge_repo,
        runner_factory=app.config.get("CTF_AGENT_RUNNER_FACTORY"),
        log_dir=Path(db_path).parent / "logs" / "runs",
        env_path=app.config["CTF_AGENT_ENV_PATH"],
    )

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.errorhandler(ServiceError)
    def handle_service_error(error: ServiceError):
        return (
            jsonify({"error": {"code": error.code, "message": error.message}}),
            error.status_code,
        )

    @app.errorhandler(404)
    def handle_not_found(error):
        return jsonify({"error": {"code": "not_found", "message": "Not found"}}), 404

    app.register_blueprint(challenges_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(models_bp)
    app.register_blueprint(runs_bp)
    app.register_blueprint(stream_bp)

    @app.get("/")
    @app.get("/<path:path>")
    def frontend(path: str = ""):
        dist = Path(app.config["CTF_AGENT_FRONTEND_DIST"])
        if not dist.exists():
            return (
                jsonify(
                    {
                        "error": {
                            "code": "frontend_not_built",
                            "message": "Run `npm --prefix frontend run build` first.",
                        }
                    }
                ),
                404,
            )

        asset = dist / path
        if path and asset.is_file():
            return send_from_directory(dist, path)
        return send_from_directory(dist, "index.html")

    return app


def main() -> None:
    host = os.environ.get("CTF_AGENT_HOST", "127.0.0.1")
    port = int(os.environ.get("CTF_AGENT_PORT", "5000"))
    create_app().run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
