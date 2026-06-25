"""Persistent user settings for unframed.

Settings are stored in ``~/.unframed_config.json`` with 0o600 permissions
because the file may contain a plaintext API key.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

DEFAULT_MODEL = "gpt-4o"
DEFAULT_TEMPERATURE = 0.7

CONFIG_PATH = Path.home() / ".unframed_config.json"


def default_settings() -> Dict[str, Any]:
    """Return the built-in default settings."""
    return {
        "api_key": "",
        "base_url": None,
        "model": DEFAULT_MODEL,
        "temperature": DEFAULT_TEMPERATURE,
    }


def load_settings(path: Path | str | None = None) -> Dict[str, Any]:
    """Load settings from disk, falling back to defaults.

    Missing keys are filled from defaults. Invalid JSON or read errors are
    swallowed and reported to stderr so the app can still start.
    """
    path = Path(path) if path else CONFIG_PATH
    settings = default_settings()

    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                for key in settings:
                    if key in raw:
                        settings[key] = raw[key]
        except json.JSONDecodeError as e:
            print(f"[警告] 配置文件解析失败，使用默认设置: {e}", file=sys.stderr)
        except OSError as e:
            print(f"[警告] 无法读取配置文件: {e}", file=sys.stderr)

    return settings


def save_settings(settings: Dict[str, Any], path: Path | str | None = None) -> None:
    """Save settings to disk with restricted permissions."""
    path = Path(path) if path else CONFIG_PATH

    # Normalize empty strings to None/null for optional fields.
    normalized: Dict[str, Any] = {}
    defaults = default_settings()
    for key in defaults:
        value = settings.get(key, defaults[key])
        if isinstance(value, str) and value.strip() == "":
            value = None
        normalized[key] = value

    # Ensure parent directory exists.
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to a temp file and rename for atomicity.
    temp_path = path.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # Restrict permissions before replacing the real file.
    os.chmod(temp_path, 0o600)
    temp_path.replace(path)
