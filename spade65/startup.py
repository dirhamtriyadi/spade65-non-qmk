"""Generate background-service and desktop login-startup integrations."""

from __future__ import annotations

import html
import os
import plistlib
import shlex
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath


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


def gui_startup_filename(platform: str | None = None) -> str:
    """Return the per-user login-startup filename for the desktop GUI."""

    return {
        "linux": "io.github.dirhamtriyadi.spade65.desktop",
        "windows": "spade65-gui.cmd",
        "macos": "io.github.dirhamtriyadi.spade65.gui.plist",
    }[platform_family(platform)]


def default_gui_startup_path(
    platform: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    home: PurePath | str | None = None,
) -> PurePath:
    """Return the user-owned login-startup path for the desktop GUI."""

    family = platform_family(platform)
    environment = os.environ if environ is None else environ
    path_type = PureWindowsPath if family == "windows" else PurePosixPath
    user_home = path_type(Path.home() if home is None else home)
    if family == "linux":
        config_root = path_type(
            environment.get("XDG_CONFIG_HOME") or user_home / ".config"
        )
        return config_root / "autostart" / gui_startup_filename(family)
    if family == "windows":
        roaming = path_type(
            environment.get("APPDATA") or user_home / "AppData" / "Roaming"
        )
        return (
            roaming
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
            / "Startup"
            / gui_startup_filename(family)
        )
    return user_home / "Library" / "LaunchAgents" / gui_startup_filename(family)


def default_service_paths(
    platform: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    home: PurePath | str | None = None,
) -> tuple[PurePath, PurePath]:
    """Return user-owned config and startup-integration paths for a platform."""

    family = platform_family(platform)
    environment = os.environ if environ is None else environ
    path_type = PureWindowsPath if family == "windows" else PurePosixPath
    user_home = path_type(Path.home() if home is None else home)
    if family == "linux":
        config_root = path_type(
            environment.get("XDG_CONFIG_HOME") or user_home / ".config"
        )
        return (
            config_root / "spade65" / "background.json",
            config_root / "systemd" / "user" / startup_filename(family),
        )
    if family == "windows":
        roaming = path_type(
            environment.get("APPDATA") or user_home / "AppData" / "Roaming"
        )
        return (
            roaming / "Spade65" / "background.json",
            roaming
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
            / "Startup"
            / startup_filename(family),
        )
    return (
        user_home / "Library" / "Application Support" / "Spade65" / "background.json",
        user_home / "Library" / "LaunchAgents" / startup_filename(family),
    )


def _powershell_quote(value: PurePath | str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def release_service_setup(
    platform: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    home: PurePath | str | None = None,
    executable: PurePath | str | None = None,
    frozen: bool | None = None,
) -> dict[str, object]:
    """Describe package-specific service setup without changing host startup."""

    family = platform_family(platform)
    environment = os.environ if environ is None else environ
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    config, launcher = default_service_paths(
        family, environ=environment, home=home
    )
    result: dict[str, object] = {
        "platform": family,
        "packaged": is_frozen,
        "config_path": str(config),
        "launcher_path": str(launcher),
        "prepare_commands": "",
        "activate_commands": "",
    }
    if not is_frozen:
        return result

    path_type = PureWindowsPath if family == "windows" else PurePosixPath
    selected = path_type(executable) if executable is not None else None
    if selected is None and family == "linux":
        selected = path_type(environment.get("APPIMAGE") or sys.executable)
    selected = selected or path_type(sys.executable)
    if family == "windows" and selected.name.casefold() == "spade65.exe":
        selected = selected.with_name("Spade65CLI.exe")

    if family == "windows":
        exe = _powershell_quote(selected)
        config_value = _powershell_quote(config)
        launcher_value = _powershell_quote(launcher)
        prepare_commands = [
            f"New-Item -ItemType Directory -Force -Path {_powershell_quote(config.parent)}",
            (
                f"if (-not (Test-Path {config_value})) "
                f"{{ & {exe} service example {config_value} }}"
            ),
        ]
        activate_commands = [
            (
                f"& {exe} service integration {config_value} "
                f"{launcher_value} --force"
            ),
        ]
    else:
        exe = shlex.quote(str(selected))
        config_value = shlex.quote(str(config))
        launcher_value = shlex.quote(str(launcher))
        prepare_commands = [
            f"mkdir -p {shlex.quote(str(config.parent))} {shlex.quote(str(launcher.parent))}",
            f"test -f {config_value} || {exe} service example {config_value}",
        ]
        activate_commands = [
            (
                f"{exe} service integration {config_value} "
                f"{launcher_value} --force"
            ),
        ]
        if family == "linux":
            activate_commands.extend(
                (
                    "systemctl --user daemon-reload",
                    f"systemctl --user enable --now {startup_filename(family)}",
                )
            )
        else:
            label = "com.spade65.background"
            activate_commands.extend(
                (
                    f"launchctl bootout gui/$(id -u)/{label} 2>/dev/null || true",
                    f"launchctl bootstrap gui/$(id -u) {launcher_value}",
                )
            )
    result["prepare_commands"] = "\n".join(prepare_commands)
    result["activate_commands"] = "\n".join(activate_commands)
    return result


def render_startup(
    config: Path, *, platform: str | None = None,
    python_executable: Path | None = None,
    frozen: bool | None = None,
) -> str:
    family = platform_family(platform)
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    selected_executable = python_executable
    if selected_executable is None and is_frozen and family == "linux":
        selected_executable = Path(os.environ.get("APPIMAGE", sys.executable))
    executable = (selected_executable or Path(sys.executable)).resolve()
    if (
        is_frozen
        and family == "windows"
        and executable.name.casefold() == "spade65cli.exe"
    ):
        executable = executable.with_name("Spade65.exe")
    config = config.expanduser().resolve()
    module_args = "" if is_frozen else " -m spade65"
    if family == "linux":
        return f"""[Unit]
Description=Spade65 background effects and application profile service
After=graphical-session.target

[Service]
Type=simple
ExecStart="{executable}"{module_args} service run "{config}"
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
"""
    if family == "windows":
        launcher = executable if is_frozen else executable.with_name("pythonw.exe")
        return (
            "@echo off\n"
            f'start "Spade65" /b "{launcher}"{module_args} service run "{config}"\n'
        )
    executable_xml = html.escape(str(executable))
    config_xml = html.escape(str(config))
    module_xml = (
        "" if is_frozen
        else "<string>-m</string><string>spade65</string>\n    "
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.spade65.background</string>
  <key>ProgramArguments</key>
  <array>
    <string>{executable_xml}</string>{module_xml}<string>service</string>
    <string>run</string><string>{config_xml}</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict>
</plist>
"""


def _gui_startup_command(
    platform: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    executable: PurePath | str | None = None,
    frozen: bool | None = None,
) -> tuple[str, PurePath, tuple[str, ...]]:
    family = platform_family(platform)
    environment = os.environ if environ is None else environ
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    path_type = PureWindowsPath if family == "windows" else PurePosixPath
    selected_value: PurePath | str
    if executable is not None:
        selected_value = executable
    elif is_frozen and family == "linux":
        selected_value = environment.get("APPIMAGE") or sys.executable
    else:
        selected_value = sys.executable
    selected = path_type(selected_value)

    if family == "windows":
        if is_frozen and selected.name.casefold() == "spade65cli.exe":
            selected = selected.with_name("Spade65.exe")
        elif not is_frozen:
            selected = selected.with_name("pythonw.exe")

    arguments = ("gui", "--start-hidden")
    if not is_frozen:
        arguments = ("-m", "spade65", *arguments)
    return family, selected, arguments


def _desktop_exec_argument(value: PurePath | str) -> str:
    escaped = (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("`", "\\`")
        .replace("$", "\\$")
    )
    return f'"{escaped}"'


def _batch_argument(value: PurePath | str) -> str:
    return '"' + str(value).replace("%", "%%") + '"'


def render_gui_startup(
    *,
    platform: str | None = None,
    environ: Mapping[str, str] | None = None,
    executable: PurePath | str | None = None,
    frozen: bool | None = None,
) -> str:
    """Render a login launcher that starts the desktop GUI in the tray."""

    family, selected, arguments = _gui_startup_command(
        platform,
        environ=environ,
        executable=executable,
        frozen=frozen,
    )
    if family == "linux":
        command = " ".join(
            _desktop_exec_argument(value) for value in (selected, *arguments)
        )
        return f"""[Desktop Entry]
Type=Application
Version=1.0
Name=Spade65
Comment=Start Spade65 Control Center in the system tray
Exec={command}
Terminal=false
X-GNOME-Autostart-enabled=true
"""
    if family == "windows":
        command = " ".join(_batch_argument(value) for value in (selected, *arguments))
        return f'@echo off\nstart "" /b {command}\n'

    payload = {
        "Label": "io.github.dirhamtriyadi.spade65.gui",
        "ProgramArguments": [str(selected), *arguments],
        "RunAtLoad": True,
        "KeepAlive": False,
        "LimitLoadToSessionType": "Aqua",
        "ProcessType": "Interactive",
        "AssociatedBundleIdentifiers": ["io.github.dirhamtriyadi.spade65"],
    }
    return plistlib.dumps(payload, sort_keys=False).decode("utf-8")


def gui_auto_start_status(
    *,
    platform: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: PurePath | str | None = None,
    executable: PurePath | str | None = None,
    frozen: bool | None = None,
    startup_path: Path | None = None,
) -> dict[str, object]:
    """Describe whether GUI login startup exists and targets this executable."""

    family = platform_family(platform)
    target = startup_path or Path(
        default_gui_startup_path(family, environ=environ, home=home)
    )
    expected = render_gui_startup(
        platform=family,
        environ=environ,
        executable=executable,
        frozen=frozen,
    )
    enabled = target.is_file()
    current = False
    if enabled:
        try:
            current = target.read_text(encoding="utf-8") == expected
        except (OSError, UnicodeError):
            current = False
    return {
        "supported": True,
        "enabled": enabled,
        "current": current,
        "path": str(target),
        "platform": family,
    }


def set_gui_auto_start(
    enabled: bool,
    *,
    platform: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: PurePath | str | None = None,
    executable: PurePath | str | None = None,
    frozen: bool | None = None,
    startup_path: Path | None = None,
) -> dict[str, object]:
    """Enable or disable per-user GUI startup for the current login session."""

    if not isinstance(enabled, bool):
        raise ValueError("auto-start state must be a boolean")
    family = platform_family(platform)
    target = startup_path or Path(
        default_gui_startup_path(family, environ=environ, home=home)
    )
    if enabled:
        contents = render_gui_startup(
            platform=family,
            environ=environ,
            executable=executable,
            frozen=frozen,
        )
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
                stream.write(contents)
            temporary.chmod(0o600)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    else:
        target.unlink(missing_ok=True)
    return gui_auto_start_status(
        platform=family,
        environ=environ,
        home=home,
        executable=executable,
        frozen=frozen,
        startup_path=target,
    )
