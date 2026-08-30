"""Standalone native-window shell for the localhost Spade65 GUI."""

from __future__ import annotations

import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from types import ModuleType
from typing import Mapping

from .gui import create_gui_server
from .settings import GUI_HOST, GUI_PORT


WINDOW_TITLE = "Spade65 Control Center"
WINDOW_WIDTH = 1360
WINDOW_HEIGHT = 860
WINDOW_MIN_SIZE = (1000, 640)
MAX_NATIVE_EXPORT_BYTES = 5_000_000
LINUX_EXTERNAL_OPENERS = (
    ("xdg-open",),
    ("gio", "open"),
    ("kde-open5",),
    ("kde-open",),
)
QT_EXTERNAL_ENVIRONMENT = (
    "QML2_IMPORT_PATH",
    "QML_IMPORT_PATH",
    "QT_PLUGIN_PATH",
    "QT_QPA_PLATFORM_PLUGIN_PATH",
    "QTWEBENGINEPROCESS_PATH",
    "QTWEBENGINE_LOCALES_PATH",
    "QTWEBENGINE_RESOURCES_PATH",
)


class DesktopUnavailable(RuntimeError):
    """Raised when the optional native WebView runtime cannot be loaded."""


def _linux_external_environment(
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Restore host library paths before launching a system application."""

    environment = dict(os.environ if environ is None else environ)
    original_library_path = environment.pop("LD_LIBRARY_PATH_ORIG", None)
    if original_library_path:
        environment["LD_LIBRARY_PATH"] = original_library_path
    else:
        environment.pop("LD_LIBRARY_PATH", None)
    for variable in QT_EXTERNAL_ENVIRONMENT:
        environment.pop(variable, None)
    return environment


def _open_linux_external_url(
    url: str, new: int = 0, autoraise: bool = True,
) -> bool:
    """Open a URL outside a frozen Qt process using clean host libraries."""

    del new, autoraise
    environment = _linux_external_environment()
    for command in LINUX_EXTERNAL_OPENERS:
        executable = shutil.which(command[0], path=environment.get("PATH"))
        if executable is None:
            continue
        try:
            process = subprocess.Popen(
                [executable, *command[1:], url],
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            try:
                if process.wait(timeout=2) == 0:
                    return True
            except subprocess.TimeoutExpired:
                return True
        except OSError:
            continue
    return False


def _safe_export_filename(value: object) -> str:
    leaf = str(value or "").replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", leaf).strip(" .")
    if cleaned.casefold().endswith(".json"):
        cleaned = cleaned[:-5].rstrip(" .")
    stem = cleaned[:120].rstrip(" .") or "spade65-export"
    return f"{stem}.json"


class DesktopApi:
    """Small native bridge for reliable, user-approved JSON exports."""

    def __init__(self, webview_module: ModuleType) -> None:
        self._window: object | None = None
        dialogs = getattr(webview_module, "FileDialog", None)
        self._save_dialog = getattr(dialogs, "SAVE", 30)

    def _bind_window(self, window: object) -> None:
        self._window = window

    def save_json(self, contents: str, suggested_name: str) -> dict[str, object]:
        if not isinstance(contents, str):
            raise ValueError("export contents must be text")
        if len(contents.encode("utf-8")) > MAX_NATIVE_EXPORT_BYTES:
            raise ValueError("export is too large")
        try:
            payload = json.loads(contents)
        except json.JSONDecodeError as error:
            raise ValueError("export contents must be valid JSON") from error
        if not isinstance(payload, (dict, list)):
            raise ValueError("export JSON must contain an object or array")
        if self._window is None:
            raise RuntimeError("desktop window is not ready")

        filename = _safe_export_filename(suggested_name)
        create_dialog = getattr(self._window, "create_file_dialog")
        selection = create_dialog(
            dialog_type=self._save_dialog,
            save_filename=filename,
            file_types=("JSON files (*.json)",),
        )
        if not selection:
            return {"saved": False}
        selected = selection if isinstance(selection, str) else selection[0]
        target = Path(selected)
        target.write_text(contents, encoding="utf-8")
        return {"saved": True, "name": target.name}


def desktop_storage_path(
    platform_name: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path | None:
    """Return a custom persistent data directory when the backend supports it."""

    current = platform_name or sys.platform
    environment = environ if environ is not None else os.environ
    user_home = home if home is not None else Path.home()
    if current == "win32":
        base = environment.get("LOCALAPPDATA") or environment.get("APPDATA")
        root = Path(base) if base else user_home / "AppData" / "Local"
        return root / "Spade65" / "WebView"
    if current == "darwin":
        # Cocoa's WKWebView backend ignores pywebview's custom storage path and
        # persists through its system-managed default website data store.
        return None
    base = environment.get("XDG_DATA_HOME")
    root = Path(base) if base else user_home / ".local" / "share"
    return root / "spade65" / "webview"


def desktop_backend(platform_name: str | None = None) -> str | None:
    """Select the renderer bundled by the native release for this platform."""

    current = platform_name or sys.platform
    return "qt" if current.startswith("linux") else None


def _backend_module(platform_name: str | None = None) -> str:
    current = platform_name or sys.platform
    if current.startswith("linux"):
        return "webview.platforms.qt"
    if current == "win32":
        return "webview.platforms.winforms"
    if current == "darwin":
        return "webview.platforms.cocoa"
    raise DesktopUnavailable(f"standalone desktop is unsupported on {current}")


def load_webview() -> ModuleType:
    try:
        return importlib.import_module("webview")
    except ImportError as error:
        raise DesktopUnavailable(
            "native desktop runtime is missing; install the 'desktop' extra or "
            "use the browser GUI"
        ) from error


def verify_desktop_runtime(platform_name: str | None = None) -> None:
    """Import the packaged WebView backend without creating a GUI window."""

    load_webview()
    module_name = _backend_module(platform_name)
    try:
        backend = importlib.import_module(module_name)
    except Exception as error:
        raise DesktopUnavailable(
            f"native desktop backend failed to load: {module_name}"
        ) from error
    if (platform_name or sys.platform) == "win32" and (
        getattr(backend, "renderer", None) != "edgechromium"
    ):
        raise DesktopUnavailable(
            "Microsoft Edge WebView2 Runtime is required for the desktop GUI"
        )


def _restore_window(window: object) -> None:
    """Bring an existing window back after a second launcher invocation."""

    show = getattr(window, "show", None)
    restore = getattr(window, "restore", None)
    if callable(show):
        show()
    if callable(restore):
        restore()


class ActivationBridge:
    """Queue a second-launch activation until the native window exists."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._window: object | None = None
        self._pending = False
        self._ready = False

    @staticmethod
    def _dispatch(window: object) -> None:
        threading.Thread(
            target=_restore_window,
            args=(window,),
            name="spade65-window-activation",
            daemon=True,
        ).start()

    def __call__(self) -> bool:
        with self._lock:
            window = self._window
            if window is None or not self._ready:
                self._pending = True
                return True
        # Once the shown event has fired there is no startup wait to deadlock
        # against. Run the restore synchronously so a broken/zombie backend is
        # reported to the second launcher, which can then open the browser.
        _restore_window(window)
        return True

    def bind(self, window: object) -> None:
        with self._lock:
            self._window = window
        shown = getattr(getattr(window, "events", None), "shown", None)
        if shown is None:
            # Test doubles and alternate WebView implementations without the
            # lifecycle event are already expected to be callable.
            self.mark_ready()
            return
        shown += self.mark_ready
        if callable(getattr(shown, "is_set", None)) and shown.is_set():
            self.mark_ready()

    def mark_ready(self) -> None:
        with self._lock:
            self._ready = True
            pending = self._pending
            self._pending = False
            window = self._window
        if pending and window is not None:
            self._dispatch(window)


def run_desktop_session(
    *,
    server: object,
    url: str,
    activation: ActivationBridge,
    webview_module: ModuleType | None = None,
    platform_name: str | None = None,
) -> None:
    """Run only the native window around an already-serving GUI server."""

    current = platform_name or sys.platform
    if webview_module is None:
        webview = load_webview()
        if current.startswith("linux"):
            _backend_module(current)
        else:
            verify_desktop_runtime(current)
    else:
        webview = webview_module
    try:
        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        desktop_api = None if current == "win32" else DesktopApi(webview)
        window = webview.create_window(
            WINDOW_TITLE,
            url,
            js_api=desktop_api,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            min_size=WINDOW_MIN_SIZE,
            background_color="#0d0d12",
            text_select=True,
        )
        if window is None:
            raise DesktopUnavailable("native desktop window creation was cancelled")
        if desktop_api is not None:
            desktop_api._bind_window(window)
        activation.bind(window)
        server.on_quit = window.destroy
        if sys.stdout is not None:
            print(f"Spade65 desktop GUI: {url}")
        storage_path = desktop_storage_path(platform_name)
        original_browser_open = webbrowser.open
        if current.startswith("linux"):
            webbrowser.open = _open_linux_external_url
        try:
            webview.start(
                gui=desktop_backend(platform_name),
                debug=False,
                private_mode=False,
                storage_path=str(storage_path) if storage_path is not None else None,
            )
        finally:
            webbrowser.open = original_browser_open
    except DesktopUnavailable:
        raise
    except Exception as error:
        raise DesktopUnavailable(f"native desktop window failed: {error}") from error


def run_desktop(
    *,
    host: str = GUI_HOST,
    port: int = GUI_PORT,
    webview_module: ModuleType | None = None,
    platform_name: str | None = None,
) -> None:
    """Run the local API and HTML UI inside a native desktop window."""

    server, url = create_gui_server(host=host, port=port)
    activation = ActivationBridge()
    server.on_activate = activation
    worker = threading.Thread(
        target=server.serve_forever,
        name="spade65-gui-server",
        daemon=True,
    )
    try:
        worker.start()
        run_desktop_session(
            server=server,
            url=url,
            activation=activation,
            webview_module=webview_module,
            platform_name=platform_name,
        )
    finally:
        if worker.is_alive():
            server.shutdown()
            worker.join(timeout=5)
        server.server_close()
