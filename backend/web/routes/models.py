"""Model catalog routes."""

from __future__ import annotations

from typing import Any

import httpx
from flask import Blueprint, current_app, jsonify, request

from backend.config import Settings
from backend.models import DEFAULT_MODELS

bp = Blueprint("models", __name__, url_prefix="/api/models")


@bp.get("")
def list_models():
    settings = _settings()
    catalog = _openai_compatible_catalog(settings)
    return jsonify(catalog)


@bp.post("/test")
def test_models():
    settings = _settings()
    payload = request.get_json(silent=True) or {}
    if isinstance(payload, dict):
        base_url = payload.get("base_url")
        if isinstance(base_url, str) and base_url.strip():
            settings.openai_base_url = base_url.strip()
        api_key = payload.get("api_key")
        if isinstance(api_key, str) and api_key.strip():
            settings.openai_api_key = api_key.strip()
    return jsonify({"test": _test_openai_compatible_api(settings)})


def _settings() -> Settings:
    env_path = current_app.config.get("CTF_AGENT_ENV_PATH")
    settings = Settings(_env_file=env_path) if env_path else Settings()
    config_service = current_app.config.get("config_service")
    read_values = getattr(config_service, "read_values", None)
    if callable(read_values):
        values = read_values()
        if "OPENAI_BASE_URL" in values:
            settings.openai_base_url = values["OPENAI_BASE_URL"] or settings.openai_base_url
        if "OPENAI_API_KEY" in values:
            settings.openai_api_key = values["OPENAI_API_KEY"]
    return settings


def _test_openai_compatible_api(settings: Settings) -> dict[str, Any]:
    candidate_urls = (
        _candidate_model_urls(settings.openai_base_url) if settings.openai_base_url else []
    )
    base = {
        "ok": False,
        "source": "api",
        "base_url": settings.openai_base_url,
        "candidate_urls": candidate_urls,
        "checked_url": "",
        "model_count": 0,
        "sample_models": [],
        "latency_ms": None,
        "error": "",
    }

    if not settings.openai_base_url or not settings.openai_api_key:
        return {
            **base,
            "error": "OPENAI_BASE_URL or OPENAI_API_KEY is not configured",
        }

    last_error = ""
    for url in candidate_urls:
        try:
            response = httpx.get(
                url,
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                timeout=5,
            )
            response.raise_for_status()
            model_ids = _extract_model_ids(response.json())
            if not model_ids:
                last_error = "Model API returned an empty model list"
                continue
            elapsed = getattr(response, "elapsed", None)
            latency_ms = (
                round(elapsed.total_seconds() * 1000)
                if elapsed is not None and callable(getattr(elapsed, "total_seconds", None))
                else None
            )
            return {
                **base,
                "ok": True,
                "checked_url": url,
                "model_count": len(model_ids),
                "sample_models": model_ids[:8],
                "latency_ms": latency_ms,
            }
        except Exception as error:
            last_error = str(error)

    return {
        **base,
        "checked_url": candidate_urls[-1] if candidate_urls else "",
        "error": last_error,
    }


def _openai_compatible_catalog(settings: Settings) -> dict[str, Any]:
    default_models = list(DEFAULT_MODELS)
    fallback = {
        "models": [],
        "model_ids": [],
        "default_models": default_models,
        "source": "fallback",
        "base_url": settings.openai_base_url,
        "candidate_urls": _candidate_model_urls(settings.openai_base_url)
        if settings.openai_base_url
        else [],
        "configured": bool(settings.openai_base_url and settings.openai_api_key),
        "model_count": 0,
        "error": "",
    }

    if not settings.openai_base_url or not settings.openai_api_key:
        fallback["error"] = "OPENAI_BASE_URL or OPENAI_API_KEY is not configured"
        return fallback

    last_error = ""
    for url in _candidate_model_urls(settings.openai_base_url):
        try:
            response = httpx.get(
                url,
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                timeout=3,
            )
            response.raise_for_status()
            model_ids = _extract_model_ids(response.json())
            if not model_ids:
                last_error = "Model API returned an empty model list"
                continue
            return {
                "models": [f"openai/{model_id}" for model_id in model_ids],
                "model_ids": model_ids,
                "default_models": default_models,
                "source": "api",
                "base_url": settings.openai_base_url,
                "candidate_urls": _candidate_model_urls(settings.openai_base_url),
                "configured": True,
                "model_count": len(model_ids),
                "error": "",
            }
        except Exception as error:
            last_error = str(error)

    fallback["error"] = last_error
    fallback["model_count"] = len(fallback["models"])
    return fallback


def _candidate_model_urls(base_url: str) -> list[str]:
    base = base_url.rstrip("/")
    urls = [f"{base}/models"]
    if not base.endswith("/v1"):
        urls.append(f"{base}/v1/models")
    return urls


def _extract_model_ids(payload: Any) -> list[str]:
    raw_models = payload.get("data", []) if isinstance(payload, dict) else payload
    if not isinstance(raw_models, list):
        return []

    ids: list[str] = []
    for item in raw_models:
        model_id = item.get("id") if isinstance(item, dict) else item
        if not isinstance(model_id, str):
            continue
        model_id = model_id.strip()
        if model_id and model_id not in ids:
            ids.append(model_id)
    return sorted(ids)
