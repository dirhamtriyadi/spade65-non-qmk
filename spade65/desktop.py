"""Standalone native-window shell for the localhost Spade65 GUI."""

from __future__ import annotations

import importlib
import json
import os
import re
import sys
import threading
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


class DesktopUnavailable(RuntimeError):
    """Raised when the optional native WebView runtime cannot be loaded."""


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


def run_desktop(
    *,
    host: str = GUI_HOST,
    port: int = GUI_PORT,
    webview_module: ModuleType | None = None,
    platform_name: str | None = None,
) -> None:
    """Run the local API and HTML UI inside a native desktop window."""

    current = platform_name or sys.platform
    if webview_module is None:
        webview = load_webview()
        if current.startswith("linux"):
            # The Qt backend snapshots webview._state["storage_path"] when its
            # module is imported.  Let webview.start() set the application-
            # specific path before it initializes Qt, otherwise Linux silently
            # falls back to ~/.pywebview and profile data leaks across apps.
            _backend_module(current)
        else:
            # Windows must reject pywebview's legacy MSHTML fallback.  Its
            # backend reads the storage path later during setup, so this early
            # verification does not defeat persistent application storage.
            verify_desktop_runtime(current)
    else:
        webview = webview_module
    server, url = create_gui_server(host=host, port=port)
    worker = threading.Thread(
        target=server.serve_forever,
        name="spade65-gui-server",
        daemon=True,
    )
    try:
        webview.settings["ALLOW_DOWNLOADS"] = True
        # PyWebView's WinForms file-dialog API is called from its JavaScript
        # worker thread. Use WebView2's UI-thread download handler on Windows;
        # Qt and Cocoa safely marshal DesktopApi dialogs to their UI threads.
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
        server.on_activate = lambda: _restore_window(window)
        server.on_quit = window.destroy
        worker.start()
        if sys.stdout is not None:
            print(f"Spade65 desktop GUI: {url}")
        storage_path = desktop_storage_path(platform_name)
        webview.start(
            gui=desktop_backend(platform_name),
            debug=False,
            private_mode=False,
            storage_path=str(storage_path) if storage_path is not None else None,
        )
    except DesktopUnavailable:
        raise
    except Exception as error:
        raise DesktopUnavailable(f"native desktop window failed: {error}") from error
    finally:
        if worker.is_alive():
            server.shutdown()
            worker.join(timeout=5)
        server.server_close()
