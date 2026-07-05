"""Configuration + secret loading.

Loads config/settings.yaml and the OPENDART_API_KEY from .env. Hard-stops
(ConfigError) if the key is missing — never proceeds silently. The key value is
never printed or logged.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.yaml"
KEY_NAME = "OPENDART_API_KEY"


class ConfigError(RuntimeError):
    """Missing/invalid configuration — a hard stop, not a fallback."""


def load_settings(path: Path = SETTINGS_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_api_key() -> str:
    """Return the OpenDART API key from .env / environment, or hard-stop."""
    load_dotenv(PROJECT_ROOT / ".env")
    key = (os.environ.get(KEY_NAME) or "").strip()
    if not key:
        raise ConfigError(
            "OPENDART_API_KEY가 설정되지 않았습니다. .env에 키를 넣어주세요. (STOP)"
        )
    return key


def resolve_paths(settings: dict) -> dict:
    def p(key: str, default: str) -> Path:
        return PROJECT_ROOT / settings.get(key, default)

    paths = {
        "raw": p("raw_dir", "data/raw"),
        "cache": p("cache_dir", "data/cache"),
        "parsed": p("parsed_dir", "data/parsed"),
        "output": p("output_dir", "output"),
    }
    for pth in paths.values():
        pth.mkdir(parents=True, exist_ok=True)
    return paths
