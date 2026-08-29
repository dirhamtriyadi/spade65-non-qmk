"""Generate opt-in background launchers without modifying OS startup state."""

from __future__ import annotations

import html
import sys
from pathlib import Path


def platform_family(value: str | None = None) -> str:
    current = value or sys.platform
    if current == "win32" or current == "windows":
        return "windows"
    if current == "darwin" or current == "macos":
        return "macos"
    if current.startswith("linux"):
        return "linux"
    raise ValueError(f"unsupported startup platform: {current}")


def startup_filename(platform: str | None = None) -> str:
    return {
        "linux": "spade65-background.service",
        "windows": "spade65-background.cmd",
        "macos": "com.spade65.background.plist",
    }[platform_family(platform)]


def render_startup(
    config: Path, *, platform: str | None = None,
    python_executable: Path | None = None,
) -> str:
    family = platform_family(platform)
    executable = (python_executable or Path(sys.executable)).resolve()
    config = config.expanduser().resolve()
    if family == "linux":
        return f"""[Unit]
Description=Spade65 background effects and application profile service
After=graphical-session.target

[Service]
Type=simple
ExecStart="{executable}" -m spade65 service run "{config}"
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
"""
    if family == "windows":
        pythonw = executable.with_name("pythonw.exe")
        return (
            "@echo off\n"
            f'start "Spade65" /b "{pythonw}" -m spade65 service run "{config}"\n'
        )
    executable_xml = html.escape(str(executable))
    config_xml = html.escape(str(config))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.spade65.background</string>
  <key>ProgramArguments</key>
  <array>
    <string>{executable_xml}</string><string>-m</string><string>spade65</string>
    <string>service</string><string>run</string><string>{config_xml}</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict>
</plist>
"""
