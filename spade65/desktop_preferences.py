"""Persistent preferences owned by the native desktop shell."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path


DEFAULT_DESKTOP_PREFERENCES = {"close_to_tray": True}


def desktop_preferences_path(
    platform_name: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Return the per-user path for native desktop preferences."""

    current = platform_name or sys.platform
    environment = os.environ if environ is None else environ
    user_home = Path.home() if home is None else home
    if current == "win32" or current == "windows":
        root = Path(
            environment.get("APPDATA") or user_home / "AppData" / "Roaming"
        )
        return root / "Spade65" / "desktop-settings.json"
    if current == "darwin" or current == "macos":
        return (
            user_home
            / "Library"
            / "Application Support"
            / "Spade65"
            / "desktop-settings.json"
        )
    if current.startswith("linux"):
        root = Path(environment.get("XDG_CONFIG_HOME") or user_home / ".config")
        return root / "spade65" / "desktop-settings.json"
    raise ValueError(f"unsupported desktop platform: {current}")


def load_desktop_preferences(path: Path | None = None) -> dict[str, bool]:
    """Load validated preferences, falling back safely after file corruption."""

    target = path or desktop_preferences_path()
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return dict(DEFAULT_DESKTOP_PREFERENCES)
    if not isinstance(value, dict):
        return dict(DEFAULT_DESKTOP_PREFERENCES)
    return {
        "close_to_tray": (
            value["close_to_tray"]
            if isinstance(value.get("close_to_tray"), bool)
            else DEFAULT_DESKTOP_PREFERENCES["close_to_tray"]
        )
    }


def save_desktop_preferences(
    preferences: Mapping[str, object], path: Path | None = None
) -> dict[str, bool]:
    """Validate and atomically persist native desktop preferences."""

    close_to_tray = preferences.get("close_to_tray")
    if not isinstance(close_to_tray, bool):
        raise ValueError("close-to-tray state must be a boolean")
    normalized = {"close_to_tray": close_to_tray}
    target = path or desktop_preferences_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(normalized, stream, indent=2)
            stream.write("\n")
        temporary.chmod(0o600)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return normalized
