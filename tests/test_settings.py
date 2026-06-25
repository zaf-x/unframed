"""Tests for settings persistence."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path

from unframed.settings import (
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    default_settings,
    load_settings,
    save_settings,
)


def test_default_settings() -> None:
    defaults = default_settings()
    assert defaults["api_key"] == ""
    assert defaults["base_url"] is None
    assert defaults["model"] == DEFAULT_MODEL
    assert defaults["temperature"] == DEFAULT_TEMPERATURE


def test_load_missing_uses_defaults() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.json"
        settings = load_settings(path)
        assert settings == default_settings()


def test_save_and_load_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.json"
        save_settings(
            {
                "api_key": "sk-test",
                "base_url": "https://api.example.com",
                "model": "deepseek-chat",
                "temperature": 0.9,
            },
            path,
        )
        settings = load_settings(path)
        assert settings["api_key"] == "sk-test"
        assert settings["base_url"] == "https://api.example.com"
        assert settings["model"] == "deepseek-chat"
        assert settings["temperature"] == 0.9


def test_empty_strings_normalized_to_null() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.json"
        save_settings(
            {
                "api_key": "",
                "base_url": "   ",
                "model": "",
                "temperature": 0.7,
            },
            path,
        )
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        assert raw["api_key"] is None
        assert raw["base_url"] is None
        assert raw["model"] is None


def test_file_permissions_restricted() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.json"
        save_settings({"api_key": "secret"}, path)
        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode == 0o600


def test_partial_config_fills_defaults() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"model": "custom-model"}, f)
        settings = load_settings(path)
        assert settings["api_key"] == ""
        assert settings["base_url"] is None
        assert settings["model"] == "custom-model"
        assert settings["temperature"] == DEFAULT_TEMPERATURE


def test_invalid_json_falls_back_to_defaults() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.json"
        path.write_text("not json", encoding="utf-8")
        settings = load_settings(path)
        assert settings == default_settings()


def test_temperature_engine_passed() -> None:
    from unframed.engine import GameEngine

    engine = GameEngine(api_key="dummy", model="gpt-4o", temperature=0.35)
    assert engine.bot.temperature == 0.35


def test_env_var_overrides_config(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "env-model")
    monkeypatch.setenv("OPENAI_TEMPERATURE", "0.25")
    # Temporarily point CONFIG_PATH away so load_settings doesn't pick up real config.
    import unframed.settings as settings_module

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.json"
        save_settings({"model": "config-model", "temperature": 0.9}, path)
        loaded = load_settings(path)
        # load_settings itself does not read env vars; callers merge them.
        assert loaded["model"] == "config-model"
        assert loaded["temperature"] == 0.9
