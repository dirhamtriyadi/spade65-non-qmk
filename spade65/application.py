"""Desktop-first GUI lifecycle shared by source and frozen entry points."""

from __future__ import annotations

import errno
import sys
import threading
import time
import webbrowser
from typing import Literal

from .desktop import ActivationBridge, DesktopUnavailable, run_desktop_session
from .gui import GuiServer, create_gui_server
from .instance import (
    activate_running_gui,
    gui_url,
    reopen_running_gui_in_browser,
    running_gui_token,
)
from .settings import GUI_HOST, GUI_PORT


GuiMode = Literal["desktop", "browser", "server"]
INSTANCE_RETRY_SECONDS = 5.0
INSTANCE_RETRY_INTERVAL = 0.1


class GuiPortInUse(RuntimeError):
    """Raised when the GUI port belongs to an unverified/unresponsive service."""


def _address_in_use(error: OSError) -> bool:
    # SO_EXCLUSIVEADDRUSE may report WSAEACCES (10013), rather than
    # WSAEADDRINUSE (10048), when a second Windows process binds the port.
    # It is safe to treat both as a collision here because the existing
    # endpoint still has to pass the authenticated Spade65 verification.
    return error.errno in {errno.EADDRINUSE, 10013, 10048} or getattr(
        error, "winerror", None
    ) in {10013, 10048}


def _canonical_host(host: str) -> str:
    """Use one authority for the two equivalent IPv4 loopback spellings."""

    return "127.0.0.1" if host.casefold() == "localhost" else host


def _reuse_existing(url: str, mode: GuiMode) -> bool:
    if running_gui_token(url) is None:
        return False
    if mode == "server":
        return True
    if mode == "browser":
        return reopen_running_gui_in_browser(url)
    return activate_running_gui(url) or reopen_running_gui_in_browser(url)


def _claim_server(host: str, port: int, mode: GuiMode) -> tuple[GuiServer, str] | None:
    """Atomically bind the GUI port, or reuse a verified primary instance."""

    host = _canonical_host(host)
    expected_url = gui_url(host, port)
    deadline = time.monotonic() + INSTANCE_RETRY_SECONDS
    while True:
        try:
            return create_gui_server(host=host, port=port)
        except OSError as error:
            if not _address_in_use(error):
                raise
        if port != 0:
            verified = running_gui_token(expected_url) is not None
            if verified and _reuse_existing(expected_url, mode):
                if sys.stdout is not None:
                    print(f"Spade65 GUI already running: {expected_url}")
                return None
            if verified:
                raise GuiPortInUse(
                    "a verified Spade65 instance is running, but its window or "
                    "browser could not be activated; close that instance and try again"
                )
        if time.monotonic() >= deadline:
            raise GuiPortInUse(
                f"port {port} is already used by another application or an "
                "unresponsive Spade65 instance; close it, then start Spade65 again"
            )
        time.sleep(INSTANCE_RETRY_INTERVAL)


def _start_server(server: GuiServer) -> threading.Thread:
    worker = threading.Thread(
        target=server.serve_forever,
        name="spade65-gui-server",
        daemon=True,
    )
    worker.start()
    return worker


def _wait_for_server(server: GuiServer, worker: threading.Thread) -> None:
    try:
        while worker.is_alive():
            worker.join(timeout=0.5)
    except KeyboardInterrupt:
        server.shutdown()


def _open_browser(url: str) -> bool:
    try:
        return bool(webbrowser.open(url))
    except (OSError, webbrowser.Error):
        return False


def launch_gui(
    *,
    host: str = GUI_HOST,
    port: int = GUI_PORT,
    mode: GuiMode = "desktop",
) -> None:
    """Launch one primary GUI, or activate the verified primary instance."""

    claimed = _claim_server(host, port, mode)
    if claimed is None:
        return
    server, url = claimed
    bridge = ActivationBridge()
    server.on_activate = bridge if mode == "desktop" else None
    worker: threading.Thread | None = None
    try:
        worker = _start_server(server)
        if mode == "desktop":
            try:
                run_desktop_session(server=server, url=url, activation=bridge)
                return
            except DesktopUnavailable as error:
                # run_desktop_session may have attached window.destroy before
                # the native renderer failed. Browser mode must not retain a
                # callback into that dead window.
                server.on_quit = None
                if sys.stderr is not None:
                    print(
                        f"desktop GUI unavailable ({error}); opening browser GUI",
                        file=sys.stderr,
                    )
                mode = "browser"
        if mode == "browser":
            server.on_activate = lambda: _open_browser(url)
            if not _open_browser(url):
                raise DesktopUnavailable(
                    f"could not open the default browser; open {url} manually"
                )
        _wait_for_server(server, worker)
    finally:
        if worker is not None and worker.is_alive():
            server.shutdown()
            worker.join(timeout=5)
        server.server_close()
