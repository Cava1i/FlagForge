import io
import json

import yaml

from backend.web.app import create_app


class BlockingRunner:
    async def run(self):
        while True:
            import asyncio

            await asyncio.sleep(1)

    def cancel(self):
        pass


def write_challenge(path, metadata=None):
    path.mkdir()
    data = {
        "name": "API Warmup",
        "category": "web",
        "value": 50,
        "connection_info": "http://example.test",
    }
    if metadata:
        data.update(metadata)
    (path / "metadata.yml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def make_client(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "CTF_AGENT_DB_PATH": tmp_path / "web.sqlite3",
            "CTF_AGENT_CHALLENGE_ROOT": tmp_path / "challenges",
            "CTF_AGENT_RUNNER_FACTORY": lambda run, challenge, cancel_event: BlockingRunner(),
        }
    )
    return app.test_client()


def test_import_list_and_get_challenge_api(tmp_path):
    client = make_client(tmp_path)
    challenge_path = write_challenge(tmp_path / "api-warmup")
    dist_dir = challenge_path / "distfiles"
    dist_dir.mkdir()
    (dist_dir / "notes.txt").write_text("hello", encoding="utf-8")

    create_response = client.post("/api/challenges", json={"path": str(challenge_path)})
    assert create_response.status_code == 201
    challenge = create_response.get_json()["challenge"]
    assert challenge["name"] == "API Warmup"

    list_response = client.get("/api/challenges")
    assert list_response.status_code == 200
    assert list_response.get_json()["challenges"][0]["id"] == challenge["id"]

    detail_response = client.get(f"/api/challenges/{challenge['id']}")
    assert detail_response.status_code == 200
    detail = detail_response.get_json()["challenge"]
    assert detail["metadata"]["category"] == "web"
    assert detail["distfiles"] == ["notes.txt"]


def test_manual_challenge_create_api_writes_metadata_and_files(tmp_path):
    client = make_client(tmp_path)

    response = client.post(
        "/api/challenges/manual",
        data={
            "slug": "api-manual",
            "metadata": json.dumps(
                {
                    "name": "API Manual",
                    "category": "forensics",
                    "value": 125,
                    "description": "uploaded in browser",
                    "connection_info": "",
                    "tags": ["browser"],
                    "hints": [],
                }
            ),
            "file_names": json.dumps(["renamed.bin", "notes.txt"]),
            "files": [
                (io.BytesIO(b"payload"), "original.bin"),
                (io.BytesIO(b"note"), "notes.txt"),
            ],
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    challenge = response.get_json()["challenge"]
    challenge_path = tmp_path / "challenges" / "api-manual"
    metadata = yaml.safe_load((challenge_path / "metadata.yml").read_text(encoding="utf-8"))
    assert challenge["name"] == "API Manual"
    assert metadata["description"] == "uploaded in browser"
    assert (challenge_path / "distfiles" / "renamed.bin").read_bytes() == b"payload"
    assert (challenge_path / "distfiles" / "notes.txt").read_bytes() == b"note"

    detail = client.get(f"/api/challenges/{challenge['id']}").get_json()["challenge"]
    assert detail["distfiles"] == ["notes.txt", "renamed.bin"]


def test_manual_challenge_create_api_rejects_bad_metadata_json(tmp_path):
    client = make_client(tmp_path)

    response = client.post(
        "/api/challenges/manual",
        data={"metadata": "{not json"},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "validation_error"


def test_update_challenge_api_updates_metadata_and_index(tmp_path):
    client = make_client(tmp_path)
    challenge_path = write_challenge(tmp_path / "api-warmup")
    challenge = client.post("/api/challenges", json={"path": str(challenge_path)}).get_json()[
        "challenge"
    ]

    response = client.put(
        f"/api/challenges/{challenge['id']}",
        json={"category": "misc", "value": 75},
    )

    assert response.status_code == 200
    updated = response.get_json()["challenge"]
    metadata = yaml.safe_load((challenge_path / "metadata.yml").read_text(encoding="utf-8"))
    assert updated["category"] == "misc"
    assert updated["value"] == 75
    assert metadata["category"] == "misc"


def test_update_challenge_api_rejects_invalid_payload(tmp_path):
    client = make_client(tmp_path)
    challenge = client.post(
        "/api/challenges", json={"path": str(write_challenge(tmp_path / "api-warmup"))}
    ).get_json()["challenge"]

    response = client.put(f"/api/challenges/{challenge['id']}", json={"bad": "field"})

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "validation_error"


def test_delete_challenge_api_removes_index_and_terminal_runs(tmp_path):
    client = make_client(tmp_path)
    challenge_path = write_challenge(tmp_path / "delete-me")
    challenge = client.post("/api/challenges", json={"path": str(challenge_path)}).get_json()[
        "challenge"
    ]
    run = client.post("/api/runs", json={"challenge_id": challenge["id"]}).get_json()["run"]
    client.post(f"/api/runs/{run['id']}/cancel")

    response = client.delete(f"/api/challenges/{challenge['id']}", json={"delete_files": False})

    assert response.status_code == 200
    assert client.get(f"/api/challenges/{challenge['id']}").status_code == 404
    assert client.get(f"/api/runs/{run['id']}").status_code == 404
    assert challenge_path.exists()


def test_delete_challenge_api_rejects_active_runs(tmp_path):
    client = make_client(tmp_path)
    challenge = client.post(
        "/api/challenges", json={"path": str(write_challenge(tmp_path / "active-delete"))}
    ).get_json()["challenge"]
    client.post("/api/runs", json={"challenge_id": challenge["id"]})

    response = client.delete(f"/api/challenges/{challenge['id']}", json={"delete_files": False})

    assert response.status_code == 400
    assert "Stop active runs" in response.get_json()["error"]["message"]


def test_import_challenge_api_rejects_non_object_json(tmp_path):
    client = make_client(tmp_path)

    response = client.post("/api/challenges", json=["not", "an", "object"])

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "validation_error"


def test_import_challenge_api_rejects_empty_path(tmp_path):
    client = make_client(tmp_path)

    response = client.post("/api/challenges", json={"path": "  "})

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "validation_error"


def test_import_challenge_api_returns_400_for_malformed_metadata(tmp_path):
    client = make_client(tmp_path)
    challenge_path = tmp_path / "broken"
    challenge_path.mkdir()
    (challenge_path / "metadata.yml").write_text("name: [unterminated\n", encoding="utf-8")

    response = client.post("/api/challenges", json={"path": str(challenge_path)})

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "validation_error"
    assert "malformed" in body["error"]["message"]
