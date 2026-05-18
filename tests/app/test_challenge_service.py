import yaml

from backend.app.challenge_service import ChallengeService, ValidationError
from backend.storage.challenge_repo import ChallengeRepo
from backend.storage.db import bootstrap


def write_challenge(path, metadata=None):
    path.mkdir(parents=True)
    data = {
        "name": "Warmup",
        "category": "pwn",
        "value": 100,
        "connection_info": "nc example.com 31337",
        "description": "solve it",
    }
    if metadata:
        data.update(metadata)
    (path / "metadata.yml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def make_service(tmp_path):
    db_path = tmp_path / "web.sqlite3"
    bootstrap(db_path)
    return ChallengeService(ChallengeRepo(db_path))


def test_import_from_path_indexes_metadata(tmp_path):
    service = make_service(tmp_path)
    challenge_path = write_challenge(tmp_path / "warmup")

    challenge = service.import_from_path(challenge_path)

    assert challenge["name"] == "Warmup"
    assert challenge["slug"] == "warmup"
    assert challenge["path"] == str(challenge_path.resolve())
    assert challenge["category"] == "pwn"
    assert challenge["value"] == 100
    assert challenge["connection_info"] == "nc example.com 31337"


def test_list_and_get_challenges(tmp_path):
    service = make_service(tmp_path)
    challenge_path = write_challenge(tmp_path / "warmup")
    dist_dir = challenge_path / "distfiles"
    dist_dir.mkdir()
    (dist_dir / "binary").write_bytes(b"\x7fELF")
    challenge = service.import_from_path(challenge_path)

    assert service.list_challenges() == [challenge]
    detail = service.get_challenge(challenge["id"])
    assert detail["id"] == challenge["id"]
    assert detail["metadata"]["description"] == "solve it"
    assert detail["distfiles"] == ["binary"]


def test_create_manual_challenge_writes_metadata_distfiles_and_index(tmp_path):
    service = ChallengeService(ChallengeRepo(tmp_path / "web.sqlite3"), challenge_root=tmp_path / "challenges")
    bootstrap(tmp_path / "web.sqlite3")

    challenge = service.create_manual_challenge(
        {
            "name": "Manual Upload",
            "category": "misc",
            "value": 150,
            "description": "inspect the file",
            "connection_info": "",
            "tags": ["upload", "example"],
            "hints": [{"content": "strings first"}],
        },
        files=[("payload.bin", b"abc123"), ("readme.txt", b"hello")],
        slug="manual-upload",
    )

    challenge_path = tmp_path / "challenges" / "manual-upload"
    metadata = yaml.safe_load((challenge_path / "metadata.yml").read_text(encoding="utf-8"))
    assert challenge["name"] == "Manual Upload"
    assert challenge["path"] == str(challenge_path.resolve())
    assert metadata["tags"] == ["upload", "example"]
    assert (challenge_path / "distfiles" / "payload.bin").read_bytes() == b"abc123"
    assert (challenge_path / "distfiles" / "readme.txt").read_text(encoding="utf-8") == "hello"
    assert service.get_challenge(challenge["id"])["distfiles"] == ["payload.bin", "readme.txt"]


def test_create_manual_challenge_rejects_duplicate_slug(tmp_path):
    db_path = tmp_path / "web.sqlite3"
    bootstrap(db_path)
    service = ChallengeService(ChallengeRepo(db_path), challenge_root=tmp_path / "challenges")
    metadata = {"name": "Manual Upload", "category": "misc", "value": 150}

    service.create_manual_challenge(metadata, files=[], slug="manual-upload")

    try:
        service.create_manual_challenge(metadata, files=[], slug="manual-upload")
    except ValidationError as error:
        assert "already exists" in error.message
    else:
        raise AssertionError("expected ValidationError")


def test_create_manual_challenge_rejects_unsafe_distfile_names(tmp_path):
    db_path = tmp_path / "web.sqlite3"
    bootstrap(db_path)
    service = ChallengeService(ChallengeRepo(db_path), challenge_root=tmp_path / "challenges")

    try:
        service.create_manual_challenge(
            {"name": "Manual Upload", "category": "misc", "value": 150},
            files=[("../escape.txt", b"bad")],
            slug="manual-upload",
        )
    except ValidationError as error:
        assert "Invalid distfile name" in error.message
    else:
        raise AssertionError("expected ValidationError")


def test_import_allows_same_basename_under_different_parents(tmp_path):
    service = make_service(tmp_path)

    first = service.import_from_path(write_challenge(tmp_path / "parent-a" / "same"))
    second = service.import_from_path(
        write_challenge(tmp_path / "parent-b" / "same", {"name": "Warmup 2"})
    )

    assert first["slug"] == "same"
    assert second["slug"] == "same"
    assert first["path"] != second["path"]
    assert [challenge["id"] for challenge in service.list_challenges()] == [
        first["id"],
        second["id"],
    ]


def test_update_metadata_updates_file_and_index(tmp_path):
    service = make_service(tmp_path)
    challenge_path = write_challenge(tmp_path / "warmup")
    challenge = service.import_from_path(challenge_path)

    updated = service.update_challenge_metadata(
        challenge["id"],
        {"name": "New Name", "value": 250, "connection_info": "nc host 4444"},
    )

    metadata = yaml.safe_load((challenge_path / "metadata.yml").read_text(encoding="utf-8"))
    assert metadata["name"] == "New Name"
    assert metadata["value"] == 250
    assert updated["name"] == "New Name"
    assert updated["value"] == 250
    assert service.get_challenge(challenge["id"])["connection_info"] == "nc host 4444"


def test_update_metadata_rejects_invalid_payload(tmp_path):
    service = make_service(tmp_path)
    challenge = service.import_from_path(write_challenge(tmp_path / "warmup"))

    try:
        service.update_challenge_metadata(challenge["id"], {"unknown": "field"})
    except ValidationError as error:
        assert error.code == "validation_error"
    else:
        raise AssertionError("expected ValidationError")


def test_update_metadata_rejects_invalid_field_types_without_writing(tmp_path):
    service = make_service(tmp_path)
    challenge_path = write_challenge(tmp_path / "warmup")
    challenge = service.import_from_path(challenge_path)
    original = (challenge_path / "metadata.yml").read_text(encoding="utf-8")

    invalid_updates = [
        {"name": 123},
        {"category": 123},
        {"connection_info": 123},
        {"description": 123},
        {"value": True},
        {"tags": "pwn"},
        {"hints": "look closer"},
    ]

    for updates in invalid_updates:
        try:
            service.update_challenge_metadata(challenge["id"], updates)
        except ValidationError as error:
            assert error.code == "validation_error"
        else:
            raise AssertionError(f"expected ValidationError for {updates}")
        assert (challenge_path / "metadata.yml").read_text(encoding="utf-8") == original


def test_import_malformed_metadata_raises_validation_error(tmp_path):
    service = make_service(tmp_path)
    challenge_path = tmp_path / "broken"
    challenge_path.mkdir()
    (challenge_path / "metadata.yml").write_text("name: [unterminated\n", encoding="utf-8")

    try:
        service.import_from_path(challenge_path)
    except ValidationError as error:
        assert error.code == "validation_error"
        assert "malformed" in error.message
    else:
        raise AssertionError("expected ValidationError")
