"""Local .env configuration service for the web API."""

from __future__ import annotations

import json
import os
import re
import shlex
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.challenge_service import ValidationError
from backend.app.skill_catalog import DEFAULT_SKILL_ROOTS, list_available_skills
from backend.models import DEFAULT_MODELS

DEFAULT_WRITEUP_PROMPT = (
    "请基于你刚才完整的 CTF 解题过程，输出一份适合初学者学习复盘的中文 Markdown writeup。"
    "要求包含：题目背景、关键漏洞/思路、尝试过程、最终利用步骤、flag、常见坑点和复盘建议。"
    "不要省略关键命令或推理。"
)


@dataclass(frozen=True)
class ConfigField:
    key: str
    label: str
    group: str
    sensitive: bool


CONFIG_FIELDS: tuple[ConfigField, ...] = (
    ConfigField("OPENAI_API_KEY", "OpenAI API Key", "models", True),
    ConfigField("OPENAI_BASE_URL", "OpenAI Base URL", "models", False),
    ConfigField("ANTHROPIC_API_KEY", "Anthropic API Key", "models", True),
    ConfigField("ANTHROPIC_BASE_URL", "Anthropic Base URL", "models", False),
    ConfigField("ANTHROPIC_AUTH_TOKEN", "Anthropic Auth Token", "models", True),
    ConfigField("GEMINI_API_KEY", "Gemini API Key", "models", True),
    ConfigField("CTFD_URL", "CTFd URL", "ctfd", False),
    ConfigField("CTFD_TOKEN", "CTFd Token", "ctfd", True),
    ConfigField("CTFD_USER", "CTFd Username", "ctfd", False),
    ConfigField("CTFD_PASS", "CTFd Password", "ctfd", True),
    ConfigField("FLAGFORGE_AGENT_COUNT", "Agent Count", "agents", False),
    ConfigField("FLAGFORGE_AGENT_MODELS", "Agent Models", "agents", False),
    ConfigField("FLAGFORGE_AGENT_SKILLS", "Agent Skills", "agents", False),
    ConfigField("FLAGFORGE_WRITEUP_PROMPT", "Writeup Prompt", "writeup", False),
)

CONFIG_FIELD_BY_KEY = {field.key: field for field in CONFIG_FIELDS}
CONFIG_DEFAULTS = {
    "FLAGFORGE_AGENT_COUNT": "1",
    "FLAGFORGE_AGENT_MODELS": "gpt-5.5",
    "FLAGFORGE_AGENT_SKILLS": "",
    "OPENAI_BASE_URL": "https://api.psydo.top",
    "FLAGFORGE_WRITEUP_PROMPT": DEFAULT_WRITEUP_PROMPT,
}


class ConfigService:
    def __init__(
        self,
        env_path: str | Path = ".env",
        *,
        skill_roots: list[str | Path] | tuple[str | Path, ...] | None = None,
    ) -> None:
        self.env_path = Path(env_path)
        self.skill_roots = tuple(Path(root) for root in (skill_roots or DEFAULT_SKILL_ROOTS))

    def get_config(self) -> dict[str, Any]:
        env_values = self._read_env_file()
        fields: dict[str, dict[str, Any]] = {}
        for field in CONFIG_FIELDS:
            value = self._current_value(field.key, env_values)
            entry: dict[str, Any] = {
                "key": field.key,
                "label": field.label,
                "group": field.group,
                "sensitive": field.sensitive,
                "configured": bool(value),
            }
            if not field.sensitive:
                entry["value"] = value
            fields[field.key] = entry

        agent_defaults = self._agent_defaults(fields)
        return {
            "env_path": str(self.env_path),
            "fields": fields,
            "agent_defaults": agent_defaults,
            "available_skills": self._available_skills(agent_defaults["skills"]),
        }

    def read_values(self) -> dict[str, str]:
        """Return raw non-masked values from the configured env file."""
        return self._read_env_file()

    def reveal_secret(self, key: str) -> dict[str, Any]:
        field = CONFIG_FIELD_BY_KEY.get(key)
        if field is None:
            raise ValidationError("Unsupported config field")
        if not field.sensitive:
            raise ValidationError(f"{key} is not a sensitive field")
        value = self._current_value(key, self._read_env_file())
        return {
            "key": key,
            "label": field.label,
            "configured": bool(value),
            "value": value,
        }

    def update_config(self, values: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(values, dict):
            raise ValidationError("values must be a JSON object")
        unknown = sorted(set(values) - set(CONFIG_FIELD_BY_KEY))
        if unknown:
            raise ValidationError(f"Unsupported config fields: {', '.join(unknown)}")

        normalized: dict[str, str] = {}
        for key, value in values.items():
            if value is None:
                normalized[key] = ""
            elif isinstance(value, str):
                normalized[key] = value.strip()
            else:
                raise ValidationError(f"{key} must be a string")

        self._validate_agent_config(normalized)
        self._write_env_updates(normalized)
        for key, value in normalized.items():
            os.environ[key] = value
        return self.get_config()

    def _current_value(self, key: str, env_values: dict[str, str]) -> str:
        if key in env_values:
            return env_values[key]
        if key in os.environ:
            return os.environ[key]
        return CONFIG_DEFAULTS.get(key, "")

    def _agent_defaults(self, fields: dict[str, dict[str, Any]]) -> dict[str, Any]:
        count_raw = str(fields["FLAGFORGE_AGENT_COUNT"].get("value") or "1")
        try:
            count = int(count_raw)
        except ValueError:
            count = 1
        count = min(max(count, 1), 12)
        models = self._parse_list(str(fields["FLAGFORGE_AGENT_MODELS"].get("value") or ""))
        raw_skills = str(fields["FLAGFORGE_AGENT_SKILLS"].get("value") or "")
        skills = self._parse_list(raw_skills)
        if not skills:
            skills = [skill["name"] for skill in self._available_skills([])]
        return {
            "count": count,
            "models": models or list(DEFAULT_MODELS),
            "skills": skills,
        }

    def _validate_agent_config(self, values: dict[str, str]) -> None:
        if "FLAGFORGE_AGENT_COUNT" in values and values["FLAGFORGE_AGENT_COUNT"]:
            try:
                count = int(values["FLAGFORGE_AGENT_COUNT"])
            except ValueError as error:
                raise ValidationError("FLAGFORGE_AGENT_COUNT must be an integer") from error
            if count < 1 or count > 12:
                raise ValidationError("FLAGFORGE_AGENT_COUNT must be between 1 and 12")

        if (
            "FLAGFORGE_AGENT_MODELS" in values
            and values["FLAGFORGE_AGENT_MODELS"]
            and not self._parse_list(values["FLAGFORGE_AGENT_MODELS"])
        ):
            raise ValidationError("FLAGFORGE_AGENT_MODELS must contain at least one model")

    def _available_skills(self, selected_skills: list[str]) -> list[dict[str, Any]]:
        return list_available_skills(self.skill_roots, selected_skills)

    def _read_skill_metadata(self, path: Path) -> dict[str, str]:
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

    def _parse_list(self, value: str) -> list[str]:
        items = re.split(r"[\n,]", value)
        result: list[str] = []
        for item in items:
            text = item.strip()
            if text and text not in result:
                result.append(text)
        return result

    def _read_env_file(self) -> dict[str, str]:
        values: dict[str, str] = {}
        if not self.env_path.exists():
            return values

        for line in self.env_path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$", line)
            if not match:
                continue
            values[match.group(1)] = self._parse_value(match.group(2))
        return values

    def _write_env_updates(self, values: dict[str, str]) -> None:
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        lines = self.env_path.read_text(encoding="utf-8").splitlines() if self.env_path.exists() else []
        seen: set[str] = set()
        next_lines: list[str] = []

        for line in lines:
            match = re.match(r"^(\s*(?:export\s+)?)([A-Za-z_][A-Za-z0-9_]*)(\s*=).*$", line)
            if not match:
                next_lines.append(line)
                continue

            key = match.group(2)
            if key not in values:
                next_lines.append(line)
                continue
            if key in seen:
                continue

            seen.add(key)
            next_lines.append(f"{key}={self._format_value(values[key])}")

        for key, value in values.items():
            if key not in seen:
                next_lines.append(f"{key}={self._format_value(value)}")

        self._atomic_write("\n".join(next_lines) + "\n")

    def _atomic_write(self, content: str) -> None:
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.env_path.parent,
                prefix=f".{self.env_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            temp_path.replace(self.env_path)
        except Exception:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise

    def _parse_value(self, value: str) -> str:
        raw = value.strip()
        if not raw:
            return ""
        try:
            parsed = shlex.split(raw, comments=True, posix=True)
        except ValueError:
            return raw.strip("\"'")
        return parsed[0] if parsed else ""

    def _format_value(self, value: str) -> str:
        if value == "":
            return ""
        if re.fullmatch(r"[A-Za-z0-9_./:@+\-=]+", value):
            return value
        return json.dumps(value, ensure_ascii=False)
