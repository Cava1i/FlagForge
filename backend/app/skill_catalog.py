"""Codex skill discovery helpers for FlagForge."""

from __future__ import annotations

from pathlib import Path
from typing import Any

DEFAULT_SKILL_ROOTS = (
    Path("/root/.codex/skills"),
    Path("/root/.codex/skills/.system"),
)


def list_available_skills(
    skill_roots: list[str | Path] | tuple[str | Path, ...] | None = None,
    selected_skills: list[str] | None = None,
) -> list[dict[str, Any]]:
    selected = set(selected_skills or [])
    roots = tuple(Path(root) for root in (skill_roots or DEFAULT_SKILL_ROOTS))
    by_name: dict[str, dict[str, Any]] = {}
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for skill_dir in root.iterdir():
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                continue
            metadata = read_skill_metadata(skill_file)
            name = metadata.get("name") or skill_dir.name
            if name in by_name:
                continue
            by_name[name] = {
                "name": name,
                "description": metadata.get("description", ""),
                "path": str(skill_file),
                "selected": name in selected or skill_dir.name in selected,
            }
    return sorted(by_name.values(), key=lambda item: item["name"].lower())


def list_available_skill_names(
    skill_roots: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> list[str]:
    return [skill["name"] for skill in list_available_skills(skill_roots)]


def read_skill_metadata(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    if not lines or lines[0].strip() != "---":
        return {"name": path.parent.name}

    metadata: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key in {"name", "description"}:
            metadata[key] = value.strip().strip("\"'")
    return metadata
