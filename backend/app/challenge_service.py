"""Challenge import, lookup, and metadata editing service."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

import yaml

from backend.storage.challenge_repo import ChallengeRepo


class ServiceError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(ServiceError):
    status_code = 404
    code = "not_found"


class ValidationError(ServiceError):
    status_code = 400
    code = "validation_error"


class ChallengeService:
    editable_fields = {"name", "category", "value", "connection_info", "description", "tags", "hints"}

    def __init__(self, repo: ChallengeRepo, *, challenge_root: str | Path = "challenges") -> None:
        self.repo = repo
        self.challenge_root = Path(challenge_root)

    def import_from_path(self, challenge_path: str | Path) -> dict[str, Any]:
        if not isinstance(challenge_path, str | Path) or not str(challenge_path).strip():
            raise ValidationError("path must be a non-empty string")
        path = Path(challenge_path).expanduser().resolve()
        metadata_path = path / "metadata.yml"
        if not path.is_dir():
            raise ValidationError(f"Challenge path does not exist: {path}")
        if not metadata_path.exists():
            raise ValidationError(f"metadata.yml not found in {path}")

        metadata = self._read_metadata(metadata_path)
        record = self._record_from_metadata(path, metadata)
        return self.repo.upsert(record)

    def list_challenges(self) -> list[dict[str, Any]]:
        return self.repo.list()

    def get_challenge(self, challenge_id: int) -> dict[str, Any]:
        challenge = self.repo.get(challenge_id)
        if challenge is None:
            raise NotFoundError("Challenge not found")
        metadata_path = Path(challenge["path"]) / "metadata.yml"
        metadata = self._read_metadata(metadata_path) if metadata_path.exists() else {}
        return {**challenge, "metadata": metadata, "distfiles": self._list_distfiles(Path(challenge["path"]))}

    def create_manual_challenge(
        self,
        metadata: dict[str, Any],
        *,
        files: list[tuple[str, bytes]],
        slug: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(metadata, dict):
            raise ValidationError("metadata must be a JSON object")

        self._validate_metadata(metadata)
        challenge_slug = self._slugify(slug or str(metadata["name"]))
        root = self.challenge_root.expanduser().resolve()
        challenge_path = root / challenge_slug
        if challenge_path.exists():
            raise ValidationError(f"Challenge slug already exists: {challenge_slug}")

        safe_files = [(self._validate_distfile_name(name), content) for name, content in files]
        names = [name for name, _content in safe_files]
        if len(names) != len(set(names)):
            raise ValidationError("distfile names must be unique")

        root.mkdir(parents=True, exist_ok=True)
        challenge_path.mkdir()
        try:
            self._write_metadata(challenge_path / "metadata.yml", metadata)
            if safe_files:
                dist_dir = challenge_path / "distfiles"
                dist_dir.mkdir()
                for name, content in safe_files:
                    (dist_dir / name).write_bytes(content)
                self._fsync_directory(dist_dir)
            self._fsync_directory(challenge_path)
            record = self._record_from_metadata(challenge_path, metadata)
            return self.repo.upsert(record)
        except Exception:
            self._remove_created_challenge(challenge_path)
            raise

    def update_challenge_metadata(self, challenge_id: int, updates: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(updates, dict) or not updates:
            raise ValidationError("Request body must be a non-empty JSON object")

        unknown = sorted(set(updates) - self.editable_fields)
        if unknown:
            raise ValidationError(f"Unsupported metadata fields: {', '.join(unknown)}")

        challenge = self.repo.get(challenge_id)
        if challenge is None:
            raise NotFoundError("Challenge not found")

        metadata_path = Path(challenge["path"]) / "metadata.yml"
        if not metadata_path.exists():
            raise ValidationError("metadata.yml not found for challenge")

        metadata = self._read_metadata(metadata_path)
        metadata.update(updates)
        self._validate_metadata(metadata)
        self._write_metadata(metadata_path, metadata)

        summary = self._record_from_metadata(Path(challenge["path"]), metadata)
        updated = self.repo.update_summary(challenge_id, summary)
        if updated is None:
            raise NotFoundError("Challenge not found")
        return {**updated, "metadata": metadata}

    def delete_challenge(self, challenge_id: int, *, delete_files: bool = False) -> dict[str, Any]:
        challenge = self.repo.get(challenge_id)
        if challenge is None:
            raise NotFoundError("Challenge not found")

        if not self.repo.delete(challenge_id):
            raise NotFoundError("Challenge not found")

        if delete_files:
            path = Path(challenge["path"])
            if path.exists():
                shutil.rmtree(path)
        return challenge

    def _record_from_metadata(self, path: Path, metadata: dict[str, Any]) -> dict[str, Any]:
        self._validate_metadata(metadata)
        name = str(metadata["name"])
        return {
            "name": name,
            "slug": self._slugify(path.name or name),
            "path": str(path),
            "category": metadata.get("category"),
            "value": metadata.get("value"),
            "connection_info": metadata.get("connection_info"),
        }

    def _read_metadata(self, metadata_path: Path) -> dict[str, Any]:
        try:
            with metadata_path.open(encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
        except yaml.YAMLError as error:
            raise ValidationError(f"metadata.yml is malformed: {error}") from error
        if not isinstance(data, dict):
            raise ValidationError("metadata.yml must contain a mapping")
        return data

    def _write_metadata(self, metadata_path: Path, metadata: dict[str, Any]) -> None:
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=metadata_path.parent,
                prefix=f".{metadata_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                yaml.safe_dump(metadata, handle, sort_keys=False, allow_unicode=True)
                handle.flush()
                os.fsync(handle.fileno())

            temp_path.replace(metadata_path)
            self._fsync_directory(metadata_path.parent)
        except Exception:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise

    def _fsync_directory(self, path: Path) -> None:
        try:
            directory_fd = os.open(path, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

    def _list_distfiles(self, challenge_path: Path) -> list[str]:
        distfiles_path = challenge_path / "distfiles"
        if not distfiles_path.exists():
            return []
        return sorted(path.name for path in distfiles_path.iterdir() if path.is_file())

    def _validate_distfile_name(self, name: str) -> str:
        if not isinstance(name, str):
            raise ValidationError("Invalid distfile name")
        cleaned = name.strip()
        if (
            not cleaned
            or cleaned in {".", ".."}
            or "/" in cleaned
            or "\\" in cleaned
            or "\x00" in cleaned
        ):
            raise ValidationError(f"Invalid distfile name: {name}")
        return cleaned

    def _remove_created_challenge(self, path: Path) -> None:
        if not path.exists():
            return
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_file() or child.is_symlink():
                child.unlink(missing_ok=True)
            elif child.is_dir():
                child.rmdir()
        path.rmdir()

    def _validate_metadata(self, metadata: dict[str, Any]) -> None:
        name = metadata.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValidationError("metadata.name is required")

        category = metadata.get("category")
        if category is not None and not isinstance(category, str):
            raise ValidationError("metadata.category must be a string or null")

        connection_info = metadata.get("connection_info")
        if connection_info is not None and not isinstance(connection_info, str):
            raise ValidationError("metadata.connection_info must be a string or null")

        description = metadata.get("description")
        if description is not None and not isinstance(description, str):
            raise ValidationError("metadata.description must be a string or null")

        value = metadata.get("value")
        if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
            raise ValidationError("metadata.value must be an integer")

        tags = metadata.get("tags")
        if tags is not None and not isinstance(tags, list):
            raise ValidationError("metadata.tags must be a list")

        hints = metadata.get("hints")
        if hints is not None and not isinstance(hints, list):
            raise ValidationError("metadata.hints must be a list")

    def _slugify(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "challenge"
