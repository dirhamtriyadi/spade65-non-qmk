"""Entry point used by the frozen desktop distributions."""

from __future__ import annotations

import importlib
import json
import multiprocessing
import re
import sys
import threading
import urllib.request
import webbrowser
from importlib.resources import files
from pathlib import Path


GUI_URL = "http://127.0.0.1:8765/"


def verify_native_hid_load(platform_name: str | None = None) -> None:
    """Load the packaged native HID extension without touching a device."""

    current = platform_name or sys.platform
    if current in {"win32", "darwin"}:
        importlib.import_module("hid")


def reopen_running_gui(url: str = GUI_URL) -> bool:
    """Reopen an existing verified Spade65 GUI without probing HID."""

    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            if response.status != 200:
                return False
            contents = response.read(1_000_000).decode("utf-8", errors="replace")
        marker = re.search(
            r'<meta\s+name="spade65-token"\s+content="([A-Za-z0-9_-]{20,})"',
            contents,
        )
        if marker is None or "<title>Spade65 Control Center</title>" not in contents:
            return False
    except (OSError, UnicodeError, ValueError):
        return False
    try:
        webbrowser.open(url)
    except (OSError, webbrowser.Error):
        # The verified server is already healthy; do not start a conflicting
        # second instance merely because this desktop has no browser handler.
        pass
    return True


def smoke_test() -> int:
    """Exercise bundled web resources and routing without probing USB HID."""

    verify_native_hid_load()
    web_root = files("spade65.web")
    for relative_path in ("index.html", "app.js"):
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
            with urllib.request.urlopen(
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

    multiprocessing.freeze_support()
    arguments = sys.argv[1:]

    # Generated background launchers from older versions used ``python -m
    # spade65``. Accept that spelling as well so an upgraded frozen binary can
    # still run an existing launcher.
    if arguments[:2] == ["-m", "spade65"]:
        arguments = arguments[2:]

    if arguments == ["--smoke-test"]:
        return smoke_test()

    if arguments:
        from spade65.cli import main as cli_main

        return cli_main(arguments)

    if getattr(sys, "frozen", False) and Path(sys.executable).stem.casefold() == (
        "spade65cli"
    ):
        from spade65.cli import main as cli_main

        return cli_main(["--help"])

    if reopen_running_gui():
        return 0

    from spade65.gui import run_gui

    # Keep a stable origin so browser-local profile and language preferences
    # survive restarts of the desktop launcher.
    try:
        run_gui(host="127.0.0.1", port=8765, open_browser=True)
    except OSError:
        # Cover the race where another launcher binds the port after our probe.
        if not reopen_running_gui():
            raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
