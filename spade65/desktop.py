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
from typing import Callable, Mapping

from .desktop_preferences import (
    desktop_preferences_path,
    load_desktop_preferences,
    save_desktop_preferences,
)
from .gui import create_gui_server
from .settings import GUI_HOST, GUI_PORT
from .startup import (
    gui_auto_start_status,
    release_service_setup,
    set_gui_auto_start,
)
from .tray import TrayController


WINDOW_TITLE = "Spade65 Control Center"
WINDOW_WIDTH = 1360
WINDOW_HEIGHT = 860
WINDOW_MIN_SIZE = (1000, 640)
MAX_NATIVE_EXPORT_BYTES = 5_000_000
MAX_NATIVE_CLIPBOARD_BYTES = 100_000
MAX_EXTERNAL_URL_LENGTH = 2_048
SERVICE_COMMAND_FIELDS = frozenset({"prepare_commands", "activate_commands"})
EXTERNAL_REPOSITORY_URL = "https://github.com/dirhamtriyadi/spade65-non-qmk"
EXTERNAL_LINK_URLS = frozenset(
    {
        EXTERNAL_REPOSITORY_URL,
        f"{EXTERNAL_REPOSITORY_URL}/releases",
        f"{EXTERNAL_REPOSITORY_URL}/blob/main/docs/host-features.md",
        f"{EXTERNAL_REPOSITORY_URL}/blob/main/docs/id/host-features.md",
    }
)
LINUX_EXTERNAL_OPENERS = (
    ("xdg-open",),
    ("gio", "open"),
    ("kde-open5",),
    ("kde-open",),
)
LINUX_CLIPBOARD_COMMANDS = (
    ("wl-copy", "--type", "text/plain;charset=utf-8"),
    ("xclip", "-selection", "clipboard", "-in"),
    ("xsel", "--clipboard", "--input"),
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


def _copy_linux_text(text: str) -> bool:
    """Fallback through a host compositor tool outside bundled AppImage libs."""

    environment = _linux_external_environment()
    for command in LINUX_CLIPBOARD_COMMANDS:
        executable = shutil.which(command[0], path=environment.get("PATH"))
        if executable is None:
            continue
        try:
            result = subprocess.run(
                [executable, *command[1:]],
                input=text.encode("utf-8"),
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            return True
    return False


def _copy_qt_text(text: str) -> bool:
    """Synchronously copy text on the Qt GUI thread used by Linux releases."""

    try:
        from qtpy import QtCore, QtGui
    except ImportError:
        return False
    application = QtGui.QGuiApplication.instance()
    if application is None:
        return False

    outcome = {"copied": False}

    class ClipboardRequest(QtCore.QObject):
        @QtCore.Slot(str)
        def copy(self, value: str) -> None:
            try:
                if (
                    "wayland" in application.platformName().casefold()
                    and application.focusWindow() is None
                ):
                    return
                clipboard = QtGui.QGuiApplication.clipboard()
                clipboard.setText(value)
                outcome["copied"] = clipboard.text() == value
            except Exception:
                outcome["copied"] = False

    request = ClipboardRequest()
    gui_thread = application.thread()
    try:
        if QtCore.QThread.currentThread() == gui_thread:
            request.copy(text)
        else:
            request.moveToThread(gui_thread)
            invoked = QtCore.QMetaObject.invokeMethod(
                request,
                "copy",
                QtCore.Qt.ConnectionType.BlockingQueuedConnection,
                QtCore.Q_ARG(str, text),
            )
            if not invoked:
                return False
        return outcome["copied"]
    except Exception:
        return False
    finally:
        request.deleteLater()


def _copy_macos_text(text: str) -> bool:
    """Copy text with AppKit on the main Cocoa queue."""

    try:
        from AppKit import NSPasteboard, NSPasteboardTypeString
        from Foundation import NSOperationQueue, NSThread
    except ImportError:
        return False

    completed = threading.Event()
    state_lock = threading.Lock()
    outcome = {"cancelled": False, "copied": False}

    def write() -> None:
        with state_lock:
            try:
                if outcome["cancelled"]:
                    return
                pasteboard = NSPasteboard.generalPasteboard()
                pasteboard.clearContents()
                outcome["copied"] = bool(
                    pasteboard.setString_forType_(text, NSPasteboardTypeString)
                )
            except Exception:
                outcome["copied"] = False
            finally:
                completed.set()

    try:
        if NSThread.isMainThread():
            write()
        else:
            NSOperationQueue.mainQueue().addOperationWithBlock_(write)
            if not completed.wait(3):
                with state_lock:
                    if not completed.is_set():
                        outcome["cancelled"] = True
                        return False
        return outcome["copied"]
    except Exception:
        with state_lock:
            outcome["cancelled"] = True
        return False


def _copy_windows_text(text: str, window: object | None) -> bool:
    """Copy text through the Spade65 WinForms window's STA GUI thread."""

    form = getattr(window, "native", None)
    if form is None:
        return False
    try:
        from System import Action
        import System.Windows.Forms as WinForms
    except ImportError:
        return False

    outcome = {"copied": False}

    def write() -> None:
        try:
            WinForms.Clipboard.SetText(text)
            outcome["copied"] = WinForms.Clipboard.GetText() == text
        except Exception:
            outcome["copied"] = False

    try:
        if bool(form.InvokeRequired):
            form.Invoke(Action(write))
        else:
            write()
        return outcome["copied"]
    except Exception:
        return False


def _copy_native_text(
    text: str,
    platform_name: str | None = None,
    *,
    window: object | None = None,
) -> bool:
    """Dispatch clipboard writes to the current host platform."""

    current = platform_name or sys.platform
    if current.startswith("linux"):
        return _copy_qt_text(text) or _copy_linux_text(text)
    if current == "darwin":
        return _copy_macos_text(text)
    if current in {"win32", "windows"}:
        return _copy_windows_text(text, window)
    return False


def _safe_export_filename(value: object) -> str:
    leaf = str(value or "").replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", leaf).strip(" .")
    if cleaned.casefold().endswith(".json"):
        cleaned = cleaned[:-5].rstrip(" .")
    stem = cleaned[:120].rstrip(" .") or "spade65-export"
    return f"{stem}.json"


def _validated_external_url(value: object) -> str:
    """Accept only the exact external destinations shipped in the UI."""

    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_EXTERNAL_URL_LENGTH
    ):
        raise ValueError("external URL must be a non-empty string")
    if value != value.strip() or any(
        ord(character) < 0x20 for character in value
    ):
        raise ValueError("external URL contains invalid whitespace")
    if value not in EXTERNAL_LINK_URLS:
        raise ValueError("external URL is not an approved Spade65 project link")
    return value


def _trusted_external_opener(
    platform_name: str,
    system_open: Callable[[str, int, bool], object],
) -> Callable[[str, int, bool], bool]:
    """Wrap pywebview's generic target=_blank opener with the same allowlist."""

    def open_url(url: str, new: int = 0, autoraise: bool = True) -> bool:
        try:
            target = _validated_external_url(url)
            if platform_name.startswith("linux"):
                return _open_linux_external_url(target, new, autoraise)
            return bool(system_open(target, new, autoraise))
        except (OSError, ValueError, webbrowser.Error):
            return False

    return open_url


class DesktopApi:
    """Native bridge for exports, trusted links, clipboard, tray, and startup."""

    def __init__(
        self,
        webview_module: ModuleType,
        *,
        tray_controller: TrayController | None = None,
        platform_name: str | None = None,
        preferences_path: Path | None = None,
        clipboard_writer: Callable[[str], bool] | None = None,
    ) -> None:
        self._window: object | None = None
        self._tray = tray_controller
        self._platform_name = platform_name or sys.platform
        self._preferences_path = preferences_path
        self._clipboard_writer = clipboard_writer
        self._native_export = self._platform_name not in {"win32", "windows"}
        dialogs = getattr(webview_module, "FileDialog", None)
        self._save_dialog = getattr(dialogs, "SAVE", 30)

    def _bind_window(self, window: object) -> None:
        self._window = window

    def desktop_status(self) -> dict[str, object]:
        tray = self._tray
        if tray is not None and not tray.ready:
            tray.wait_until_ready(2)
        startup = gui_auto_start_status(platform=self._platform_name)
        return {
            "available": True,
            "platform": startup["platform"],
            "packaged": bool(getattr(sys, "frozen", False)),
            "native_export": self._native_export,
            "tray_ready": tray.ready if tray is not None else False,
            "tray_available": tray.available if tray is not None else False,
            "close_to_tray": tray.close_to_tray if tray is not None else False,
            "auto_start_supported": startup["supported"],
            "auto_start_enabled": startup["enabled"],
            "auto_start_current": startup["current"],
            "auto_start_path": startup["path"],
        }

    def set_close_to_tray(self, enabled: bool) -> dict[str, object]:
        if self._tray is None:
            raise RuntimeError("system tray integration is not ready")
        previous = self._tray.close_to_tray
        self._tray.set_close_to_tray(enabled)
        try:
            save_desktop_preferences(
                {"close_to_tray": enabled}, path=self._preferences_path
            )
        except Exception:
            self._tray.set_close_to_tray(previous)
            raise
        return self.desktop_status()

    def set_auto_start(self, enabled: bool) -> dict[str, object]:
        if not isinstance(enabled, bool):
            raise ValueError("auto-start state must be a boolean")
        tray = self._tray
        if enabled:
            if tray is None:
                raise RuntimeError("system tray integration is not ready")
            tray.wait_until_ready(2)
            if not tray.available:
                raise RuntimeError(
                    "hidden auto-start requires a system tray on this desktop"
                )
        set_gui_auto_start(enabled, platform=self._platform_name)
        return self.desktop_status()

    def open_external_url(self, url: str) -> dict[str, bool]:
        """Open a trusted project link in the host's default browser."""

        target = _validated_external_url(url)
        try:
            if self._platform_name.startswith("linux"):
                opened = _open_linux_external_url(target, new=2, autoraise=True)
            else:
                opened = webbrowser.open(target, new=2, autoraise=True)
        except (OSError, webbrowser.Error) as error:
            raise RuntimeError("the system browser could not be opened") from error
        if not opened:
            raise RuntimeError("the system browser could not be opened")
        return {"opened": True}

    def copy_service_commands(self, field: str) -> dict[str, bool]:
        """Copy one canonical packaged-service command block."""

        if not isinstance(field, str) or field not in SERVICE_COMMAND_FIELDS:
            raise ValueError("unknown service command field")
        setup = release_service_setup(platform=self._platform_name)
        contents = setup.get(field)
        if not isinstance(contents, str) or not contents:
            raise RuntimeError(
                "service setup commands are available only in a release package"
            )
        if "\x00" in contents:
            raise ValueError("clipboard contents contain a NUL character")
        if len(contents.encode("utf-8")) > MAX_NATIVE_CLIPBOARD_BYTES:
            raise ValueError("clipboard contents are too large")
        writer = self._clipboard_writer
        try:
            copied = (
                writer(contents)
                if writer is not None
                else _copy_native_text(
                    contents,
                    self._platform_name,
                    window=self._window,
                )
            )
        except Exception as error:
            raise RuntimeError(
                "the system clipboard could not be updated"
            ) from error
        if not copied:
            raise RuntimeError("the system clipboard could not be updated")
        return {"copied": True}

    def save_json(self, contents: str, suggested_name: str) -> dict[str, object]:
        if not self._native_export:
            raise RuntimeError("Windows exports use the WebView2 download handler")
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
    start_hidden: bool = False,
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
        preferences_path = desktop_preferences_path(current)
        preferences = load_desktop_preferences(preferences_path)
        tray = TrayController(
            platform_name=current,
            close_to_tray=preferences["close_to_tray"],
            start_hidden=start_hidden,
        )
        desktop_api = DesktopApi(
            webview,
            tray_controller=tray,
            platform_name=current,
            preferences_path=preferences_path,
        )
        window = webview.create_window(
            WINDOW_TITLE,
            url,
            js_api=desktop_api,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            min_size=WINDOW_MIN_SIZE,
            background_color="#0d0d12",
            text_select=True,
            hidden=start_hidden,
        )
        if window is None:
            raise DesktopUnavailable("native desktop window creation was cancelled")
        desktop_api._bind_window(window)
        tray.bind(window)
        activation.bind(window)
        server.on_quit = tray.quit
        if sys.stdout is not None:
            print(f"Spade65 desktop GUI: {url}")
        storage_path = desktop_storage_path(platform_name)
        original_browser_open = webbrowser.open
        webbrowser.open = _trusted_external_opener(current, original_browser_open)
        try:
            webview.start(
                gui=desktop_backend(platform_name),
                debug=False,
                private_mode=False,
                storage_path=str(storage_path) if storage_path is not None else None,
            )
        finally:
            webbrowser.open = original_browser_open
            tray.dispose()
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
    start_hidden: bool = False,
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
            start_hidden=start_hidden,
        )
    finally:
        if worker.is_alive():
            server.shutdown()
            worker.join(timeout=5)
        server.server_close()
