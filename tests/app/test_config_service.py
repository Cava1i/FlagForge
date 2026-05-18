import os

import pytest

from backend.app.challenge_service import ValidationError
from backend.app.config_service import ConfigService


def test_config_status_masks_sensitive_values(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "OPENAI_API_KEY=sk-file\nANTHROPIC_BASE_URL=https://anthropic.example\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-env")

    status = ConfigService(env_path).get_config()

    assert status["env_path"] == str(env_path)
    assert status["fields"]["OPENAI_API_KEY"]["configured"] is True
    assert "value" not in status["fields"]["OPENAI_API_KEY"]
    assert status["fields"]["GEMINI_API_KEY"]["configured"] is True
    assert "value" not in status["fields"]["GEMINI_API_KEY"]
    assert status["fields"]["ANTHROPIC_BASE_URL"]["value"] == "https://anthropic.example"


def test_config_can_reveal_sensitive_value_on_demand(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=sk-local-secret\n", encoding="utf-8")

    secret = ConfigService(env_path).reveal_secret("OPENAI_API_KEY")

    assert secret == {
        "key": "OPENAI_API_KEY",
        "label": "OpenAI API Key",
        "configured": True,
        "value": "sk-local-secret",
    }


def test_config_rejects_reveal_for_non_sensitive_field(tmp_path):
    with pytest.raises(ValidationError):
        ConfigService(tmp_path / ".env").reveal_secret("OPENAI_BASE_URL")


def test_update_config_writes_env_and_updates_process_env(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("# keep me\nUNKNOWN_SETTING=yes\nOPENAI_API_KEY=old\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    status = ConfigService(env_path).update_config(
        {
            "OPENAI_API_KEY": "sk-new",
            "ANTHROPIC_BASE_URL": "https://api.example/v1",
            "CTFD_URL": "https://ctf.example",
        }
    )

    saved = env_path.read_text(encoding="utf-8")
    assert "# keep me" in saved
    assert "UNKNOWN_SETTING=yes" in saved
    assert "OPENAI_API_KEY=sk-new" in saved
    assert "ANTHROPIC_BASE_URL=https://api.example/v1" in saved
    assert "CTFD_URL=https://ctf.example" in saved
    assert os.environ["OPENAI_API_KEY"] == "sk-new"
    assert status["fields"]["OPENAI_API_KEY"]["configured"] is True


def test_config_status_prefers_env_file_over_process_env(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_BASE_URL=https://api.psydo.top\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://old.example/v1")

    status = ConfigService(env_path).get_config()

    assert status["fields"]["OPENAI_BASE_URL"]["value"] == "https://api.psydo.top"


def test_config_status_includes_default_chinese_writeup_prompt(tmp_path):
    status = ConfigService(tmp_path / ".env").get_config()

    prompt = status["fields"]["FLAGFORGE_WRITEUP_PROMPT"]["value"]
    assert status["fields"]["FLAGFORGE_WRITEUP_PROMPT"]["group"] == "writeup"
    assert "中文 Markdown writeup" in prompt
    assert "适合初学者" in prompt


def test_update_config_can_clear_sensitive_value(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=sk-old\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-old")

    status = ConfigService(env_path).update_config({"OPENAI_API_KEY": ""})

    assert "OPENAI_API_KEY=\n" in env_path.read_text(encoding="utf-8")
    assert os.environ.get("OPENAI_API_KEY", "") == ""
    assert status["fields"]["OPENAI_API_KEY"]["configured"] is False


def test_update_config_rejects_unknown_field(tmp_path):
    with pytest.raises(ValidationError):
        ConfigService(tmp_path / ".env").update_config({"BAD_KEY": "value"})


def test_config_status_includes_agent_fields_and_available_skills(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "FLAGFORGE_AGENT_COUNT=3\n"
        "FLAGFORGE_AGENT_MODELS=codex/gpt-5.4,codex/gpt-5.4-mini\n"
        "FLAGFORGE_AGENT_SKILLS=ctf-web,ctf-misc\n",
        encoding="utf-8",
    )
    skill_root = tmp_path / "skills"
    web_skill = skill_root / "ctf-web"
    web_skill.mkdir(parents=True)
    (web_skill / "SKILL.md").write_text(
        "---\nname: ctf-web\ndescription: Web challenge workflow\n---\n# CTF Web\n",
        encoding="utf-8",
    )
    misc_skill = skill_root / "ctf-misc"
    misc_skill.mkdir()
    (misc_skill / "SKILL.md").write_text("# CTF Misc\n", encoding="utf-8")
    monkeypatch.delenv("FLAGFORGE_AGENT_COUNT", raising=False)
    monkeypatch.delenv("FLAGFORGE_AGENT_MODELS", raising=False)
    monkeypatch.delenv("FLAGFORGE_AGENT_SKILLS", raising=False)

    status = ConfigService(env_path, skill_roots=[skill_root]).get_config()

    assert status["fields"]["FLAGFORGE_AGENT_COUNT"]["value"] == "3"
    assert status["agent_defaults"]["count"] == 3
    assert status["agent_defaults"]["models"] == ["codex/gpt-5.4", "codex/gpt-5.4-mini"]
    assert status["agent_defaults"]["skills"] == ["ctf-web", "ctf-misc"]
    assert status["available_skills"][0]["name"] == "ctf-misc"
    assert status["available_skills"][1]["name"] == "ctf-web"
    assert status["available_skills"][1]["selected"] is True


def test_config_status_selects_all_skills_by_default(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("", encoding="utf-8")
    skill_root = tmp_path / "skills"
    for name in ("ctf-web", "ctf-misc"):
        skill_dir = skill_root / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\n---\n# {name}\n", encoding="utf-8")
    monkeypatch.delenv("FLAGFORGE_AGENT_SKILLS", raising=False)

    status = ConfigService(env_path, skill_roots=[skill_root]).get_config()

    assert status["agent_defaults"]["skills"] == ["ctf-misc", "ctf-web"]
    assert [skill["selected"] for skill in status["available_skills"]] == [True, True]


def test_update_config_rejects_invalid_agent_count(tmp_path):
    with pytest.raises(ValidationError):
        ConfigService(tmp_path / ".env").update_config({"FLAGFORGE_AGENT_COUNT": "0"})
