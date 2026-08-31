"""Entry point used by the frozen desktop distributions."""

from __future__ import annotations

import importlib
import json
import multiprocessing
import os
import re
import shutil
import subprocess
import sys
import threading
import traceback
import webbrowser
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path

from spade65.application import launch_gui
from spade65.instance import (
    LOCALHOST_OPENER,
    activate_running_gui as _activate_running_gui,
    running_gui_token as _running_gui_token,
)
from spade65.settings import GUI_HOST, GUI_PORT, GUI_URL


_DEVNULL_STREAMS: list[object] = []


class _TeeStream:
    """Mirror a non-interactive inherited stream into the launcher log."""

    def __init__(self, primary: object, log: object) -> None:
        self._primary = primary
        self._log = log

    def write(self, value: str) -> int:
        written = self._primary.write(value)
        self._log.write(value)
        return written if isinstance(written, int) else len(value)

    def flush(self) -> None:
        self._primary.flush()
        self._log.flush()

    def isatty(self) -> bool:
        return False

    def __getattr__(self, name: str) -> object:
        return getattr(self._primary, name)


def launcher_log_path(platform_name: str | None = None) -> Path:
    """Return the per-user diagnostic log used by a windowed executable."""

    current = platform_name or sys.platform
    if current == "win32":
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local")
        return root / "Spade65" / "Logs" / "launcher.log"
    if current == "darwin":
        return Path.home() / "Library" / "Logs" / "Spade65" / "launcher.log"
    root = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    return root / "spade65" / "launcher.log"


def has_visible_console(stream: object | None = None) -> bool:
    """Return whether launch errors are immediately visible to a terminal user."""

    candidate = sys.stderr if stream is None else stream
    try:
        return candidate is not None and bool(candidate.isatty())
    except (AttributeError, OSError, ValueError):
        return False


def ensure_standard_streams(
    *, log_path: Path | None = None, force_log: bool = False
) -> Path | None:
    """Send missing GUI-process streams to a persistent diagnostic log."""

    missing = [name for name in ("stdout", "stderr") if getattr(sys, name) is None]
    if not missing and not force_log:
        return None
    destination = log_path or launcher_log_path()
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        stream = destination.open("a", encoding="utf-8", buffering=1)
        stream.write(
            f"\n[{datetime.now(timezone.utc).isoformat()}] Spade65 launcher\n"
        )
    except OSError:
        destination = None
        if not missing:
            return None
        stream = open(os.devnull, "w", encoding="utf-8")
    _DEVNULL_STREAMS.append(stream)
    for name in ("stdout", "stderr"):
        current = getattr(sys, name)
        if current is None:
            setattr(sys, name, stream)
        elif force_log:
            setattr(sys, name, _TeeStream(current, stream))
    return destination


def show_startup_error(message: str, platform_name: str | None = None) -> bool:
    """Best-effort native error UI when a windowed process has no console."""

    current = platform_name or sys.platform
    try:
        if current == "win32":
            import ctypes

            ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
                None, message, "Spade65 could not start", 0x10
            )
            return True
        if current == "darwin":
            from AppKit import NSAlert

            alert = NSAlert.alloc().init()
            alert.setMessageText_("Spade65 could not start")
            alert.setInformativeText_(message)
            alert.runModal()
            return True
        commands = (
            ("zenity", ["--error", "--title=Spade65", f"--text={message}"]),
            ("kdialog", ["--error", message, "--title", "Spade65"]),
            ("notify-send", ["--urgency=critical", "Spade65", message]),
        )
        for executable, arguments in commands:
            path = shutil.which(executable)
            if path is None:
                continue
            result = subprocess.run(
                [path, *arguments],
                check=False,
                timeout=30,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                return True
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            application = QApplication.instance() or QApplication([])
            QMessageBox.critical(None, "Spade65 could not start", message)
            return application is not None
        except Exception:
            return False
    except (ImportError, OSError, subprocess.SubprocessError):
        return False
    return False


def report_windowed_failure(error: BaseException, log_path: Path | None) -> None:
    """Record a startup failure and display it outside a hidden console."""

    message = f"Spade65 could not start.\n\n{error}"
    if log_path is not None:
        message += f"\n\nDiagnostic log: {log_path}"
    if sys.stderr is not None:
        traceback.print_exception(
            type(error), error, error.__traceback__, file=sys.stderr
        )
    show_startup_error(message)


def verify_native_hid_load(platform_name: str | None = None) -> None:
    """Load the packaged native HID extension without touching a device."""

    current = platform_name or sys.platform
    if current in {"win32", "darwin"}:
        importlib.import_module("hid")


def running_gui_token(url: str = GUI_URL) -> str | None:
    return _running_gui_token(url)


def activate_running_gui(url: str = GUI_URL) -> bool:
    return _activate_running_gui(url)


def reopen_running_gui_in_browser(url: str = GUI_URL) -> bool:
    if running_gui_token(url) is None:
        return False
    try:
        return bool(webbrowser.open(url))
    except (OSError, webbrowser.Error):
        return False


def smoke_test() -> int:
    """Exercise bundled web resources and routing without probing USB HID."""

    verify_native_hid_load()
    from spade65.desktop import verify_desktop_runtime

    verify_desktop_runtime()
    desktop_root = files("webview")
    for relative_path in ("js/api.js", "js/finish.js"):
        resource = desktop_root.joinpath(*relative_path.split("/"))
        if not resource.read_bytes():
            raise RuntimeError(f"empty packaged WebView resource: {relative_path}")
    web_root = files("spade65.web")
    for relative_path in (
        "index.html", "layout-state.js", "key-events.js", "app.js",
    ):
        resource = web_root.joinpath(*relative_path.split("/"))
        contents = resource.read_bytes()
        if not contents:
            raise RuntimeError(f"empty packaged resource: {relative_path}")

    locale_index_path = web_root.joinpath("locales", "index.json")
    locale_index = json.loads(locale_index_path.read_bytes())
    if not isinstance(locale_index, dict):
        raise RuntimeError("invalid packaged locale index")
    default_locale = locale_index.get("default")
    languages = locale_index.get("languages")
    if not isinstance(default_locale, str) or not isinstance(languages, list):
        raise RuntimeError("invalid packaged locale index")
    locale_codes: list[str] = []
    for language in languages:
        code = language.get("code") if isinstance(language, dict) else None
        if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", code):
            raise RuntimeError("invalid locale code in packaged locale index")
        if code in locale_codes:
            raise RuntimeError(f"duplicate packaged locale: {code}")
        locale_codes.append(code)
        catalog = json.loads(
            web_root.joinpath("locales", f"{code}.json").read_bytes()
        )
        if not isinstance(catalog, dict) or not catalog:
            raise RuntimeError(f"invalid packaged locale catalog: {code}")
    if "en" not in locale_codes or default_locale not in locale_codes:
        raise RuntimeError("English and the default locale must be packaged")

    # Use the real HTTP handler, but request only a static locale. This catches
    # missing PyInstaller data and route regressions without enumerating HID or
    # opening a browser.
    from spade65.gui import GuiServer

    server = GuiServer(("127.0.0.1", 0), "packaging-smoke-test")
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        for relative_path in (
            "locales/index.json",
            *(f"locales/{code}.json" for code in locale_codes),
        ):
            with LOCALHOST_OPENER.open(
                f"http://127.0.0.1:{server.server_port}/{relative_path}", timeout=5
            ) as response:
                if response.status != 200 or not json.loads(response.read()):
                    raise RuntimeError(
                        f"packaged locale HTTP route failed: {relative_path}"
                    )
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)

    if sys.stdout is not None:
        print("Spade65 packaged smoke test: OK")
    return 0


def main() -> int:
    """Open the GUI by default, while retaining access to every CLI command."""

    visible_console = has_visible_console()
    multiprocessing.freeze_support()
    arguments = sys.argv[1:]

    # Generated background launchers from older versions used ``python -m
    # spade65``. Accept that spelling as well so an upgraded frozen binary can
    # still run an existing launcher.
    if arguments[:2] == ["-m", "spade65"]:
        arguments = arguments[2:]

    # A no-argument file-manager launch has no reliable place for diagnostics,
    # so mirror it to a log. Explicit CLI commands keep normal redirection
    # semantics and must never create popup/notification loops in services.
    graphical_request = not arguments or arguments[0] == "gui"
    fallback_log = ensure_standard_streams(
        force_log=not visible_console and graphical_request
    )

    if arguments == ["--smoke-test"]:
        return smoke_test()

    if arguments:
        from spade65.cli import main as cli_main

        try:
            result = cli_main(arguments)
        except SystemExit as error:
            result = int(error.code or 0)
        except Exception as error:
            if not visible_console and graphical_request:
                report_windowed_failure(error, fallback_log)
            elif sys.stderr is not None:
                traceback.print_exception(
                    type(error), error, error.__traceback__, file=sys.stderr
                )
            return 1
        if result and not visible_console and graphical_request:
            message = "The Spade65 graphical interface could not start."
            if fallback_log is not None:
                message += f"\n\nDiagnostic log: {fallback_log}"
            show_startup_error(message)
        return result

    if getattr(sys, "frozen", False) and Path(sys.executable).stem.casefold() == (
        "spade65cli"
    ):
        from spade65.cli import main as cli_main

        return cli_main(["--help"])

    try:
        launch_gui(host=GUI_HOST, port=GUI_PORT, mode="desktop")
        return 0
    except (OSError, RuntimeError) as error:
        if not visible_console:
            report_windowed_failure(error, fallback_log)
        elif sys.stderr is not None:
            traceback.print_exception(
                type(error), error, error.__traceback__, file=sys.stderr
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
