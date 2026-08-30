"""Dependency-free localhost web GUI for Spade65 configuration."""

from __future__ import annotations

import json
import re
import secrets
import socket
import sys
import threading
import time
import webbrowser
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import __version__
from .transport import (
    Device,
    choose_device,
    discover_devices,
    readonly_device_info,
    send_feature_report,
    send_output_report,
)
from .keymap import (
    BUTTON_TO_SLOT,
    HID_USAGES,
    USAGE_GROUPS,
    compile_profile,
    profile_template,
)
from .protocol import (
    EFFECTS,
    MAIN_REPORT_ID,
    MAIN_REPORT_LENGTH,
    MAIN_USAGE,
    OUTPUT_USAGE,
    PRODUCT_IDS,
    SHORT_REPORT_ID,
    SHORT_REPORT_LENGTH,
    SHORT_USAGE,
    VENDOR_ID,
    debounce_report,
    reset_report,
    rgb_effect_report,
    sleep_report,
    streaming_activation_report,
    streaming_rgb_reports,
)
from .settings import GUI_HOST, GUI_PORT
from .startup import release_service_setup


WRITE_LOCK = threading.Lock()
MAX_REQUEST_BYTES = 1_000_000
SAFE_ACTIONS = frozenset(
    {
        "validate", "vendor-convert", "rgb", "per-key", "profile", "stream",
        "debounce", "sleep", "reset",
    }
)


def _device_summary(device: Device) -> dict[str, object]:
    return {
        "path": str(device.path),
        "backend": device.backend,
        "vid": f"{device.vendor_id:04x}",
        "pid": f"{device.product_id:04x}",
        "transport": PRODUCT_IDS.get(device.product_id, "unknown"),
        "name": device.name,
        "usages": [f"{page:04x}:{usage:04x}" for page, usage in sorted(device.usages)],
        "reports": [
            {"kind": report.kind, "id": report.report_id, "bytes": report.byte_length}
            for report in device.reports
        ],
        "readonly": readonly_device_info(device),
    }


def gui_metadata() -> dict[str, object]:
    devices = [
        device
        for device in discover_devices()
        if device.vendor_id == VENDOR_ID and device.product_id in PRODUCT_IDS
    ]
    return {
        "version": __version__,
        "devices": [_device_summary(device) for device in devices],
        "effects": sorted(EFFECTS),
        "buttons": list(BUTTON_TO_SLOT),
        "usages": HID_USAGES,
        "usage_groups": USAGE_GROUPS,
        "profile": profile_template(),
        "firmware_update": False,
        "safe_actions": sorted(SAFE_ACTIONS),
        "service_setup": release_service_setup(),
    }


def _choose(
    usage: tuple[int, int],
    *,
    product_ids: set[int] | None = None,
    explicit_path: str | None = None,
) -> Device:
    return choose_device(
        discover_devices(),
        vendor_id=VENDOR_ID,
        product_ids=product_ids or set(PRODUCT_IDS),
        usage=usage,
        explicit_path=Path(explicit_path) if explicit_path else None,
    )


def _send_features(device: Device, reports: list[bytes]) -> list[int]:
    allowed_shapes = {
        MAIN_REPORT_ID: MAIN_REPORT_LENGTH,
        SHORT_REPORT_ID: SHORT_REPORT_LENGTH,
    }
    for report in reports:
        if not report or report[0] not in allowed_shapes:
            raise RuntimeError("refusing unknown feature report")
        required = allowed_shapes[report[0]]
        if len(report) != required:
            raise RuntimeError(
                f"invalid report 0x{report[0]:02x} length: {len(report)}/{required}"
            )
        advertised = device.report_length("feature", report[0])
        if advertised != required:
            raise RuntimeError(
                f"report 0x{report[0]:02x} mismatch: "
                f"descriptor={advertised}, expected={required}"
            )
    results = []
    with WRITE_LOCK:
        for index, report in enumerate(reports):
            result = send_feature_report(device, report)
            if result != len(report):
                raise RuntimeError(f"short feature write: {result}/{len(report)}")
            results.append(result)
            if index + 1 < len(reports):
                time.sleep(0.1)
    return results


def execute_action(action: str, payload: dict[str, Any]) -> dict[str, object]:
    if action not in SAFE_ACTIONS:
        raise ValueError(f"unknown or unsafe GUI action: {action}")
    path = payload.get("device") or None
    if action == "vendor-convert":
        from .vendor import convert_vendor_document

        profile, imported = convert_vendor_document(
            payload["document"], base_profile=payload.get("profile")
        )
        return {"profile": profile, "imported": imported}
    if action == "validate":
        compiled = compile_profile(payload["profile"])
        return {
            "keymap_bytes": len(compiled["keymap"]),
            "macros": len(compiled["macros"]),
            "colors": len(payload["profile"].get("colors", {})),
        }
    if action == "rgb":
        report = rgb_effect_report(
            str(payload["effect"]),
            brightness=int(payload.get("brightness", 4)),
            speed=int(payload.get("speed", 5)),
            color_index=int(payload.get("color_index", 0)),
            multicolor=bool(payload.get("multicolor", False)),
        )
        device = _choose(MAIN_USAGE, explicit_path=path)
        return {"device": str(device.path), "results": _send_features(device, [report])}
    if action == "per-key":
        compiled = compile_profile(payload["profile"])
        reports = [
            rgb_effect_report(
                "custom",
                brightness=int(payload.get("brightness", 4)),
                speed=int(payload.get("speed", 5)),
            ),
            compiled["colors"],
        ]
        device = _choose(MAIN_USAGE, explicit_path=path)
        return {"device": str(device.path), "results": _send_features(device, reports)}
    if action == "profile":
        if payload.get("confirmation") != "APPLY PROFILE":
            raise RuntimeError("type APPLY PROFILE to confirm profile overwrite")
        compiled = compile_profile(payload["profile"])
        reports = [compiled["keymap"], *compiled["macros"]]
        if payload["profile"].get("colors"):
            reports.extend((rgb_effect_report("custom"), compiled["colors"]))
        device = _choose(MAIN_USAGE, explicit_path=path)
        return {"device": str(device.path), "results": _send_features(device, reports)}
    if action == "stream":
        compiled = compile_profile(payload["profile"])
        activation = streaming_activation_report()
        chunks = streaming_rgb_reports(compiled["matrix_colors"])
        device = _choose(OUTPUT_USAGE, product_ids={0x0351}, explicit_path=path)
        if device.report_length("feature", SHORT_REPORT_ID) != SHORT_REPORT_LENGTH:
            raise RuntimeError("missing streaming activation report")
        if device.report_length("output", 0x06) != 64:
            raise RuntimeError("missing streaming output report")
        with WRITE_LOCK:
            feature_result = send_feature_report(device, activation)
            if feature_result != SHORT_REPORT_LENGTH:
                raise RuntimeError(
                    f"short streaming activation: {feature_result}/{SHORT_REPORT_LENGTH}"
                )
            output_results = []
            for chunk in chunks:
                result = send_output_report(device, chunk)
                if result != 64:
                    raise RuntimeError(f"short streaming output: {result}/64")
                output_results.append(result)
        return {
            "device": str(device.path),
            "results": [feature_result, *output_results],
        }
    if action == "debounce":
        report = debounce_report(int(payload["milliseconds"]))
        device = _choose(SHORT_USAGE, explicit_path=path)
        return {"device": str(device.path), "results": _send_features(device, [report])}
    if action == "sleep":
        report = sleep_report(
            light_off_minutes=int(payload["light_off"]),
            hibernate_minutes=int(payload["hibernate"]),
        )
        device = _choose(SHORT_USAGE, product_ids={0x0356}, explicit_path=path)
        return {"device": str(device.path), "results": _send_features(device, [report])}
    if action == "reset":
        if payload.get("confirmation") != "RESET SPADE65":
            raise RuntimeError("type RESET SPADE65 to confirm")
        device = _choose(SHORT_USAGE, explicit_path=path)
        return {
            "device": str(device.path),
            "results": _send_features(device, [reset_report()]),
        }
    raise AssertionError("unreachable safe action")


class GuiServer(ThreadingHTTPServer):
    daemon_threads = True
    # Windows SO_REUSEADDR can let another process bind the same endpoint and
    # intercept localhost traffic. Unix keeps reuse enabled for clean restarts.
    allow_reuse_address = sys.platform != "win32"

    def server_bind(self) -> None:
        if sys.platform == "win32" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(
                socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1
            )
        super().server_bind()

    def __init__(
        self,
        address: tuple[str, int],
        token: str,
        *,
        on_activate: Callable[[], bool | None] | None = None,
        on_quit: Callable[[], None] | None = None,
    ):
        super().__init__(address, GuiHandler)
        self.token = token
        quoted_host = f"[{address[0]}]" if ":" in address[0] else address[0]
        self.allowed_authority = (
            quoted_host
            if self.server_port == 80
            else f"{quoted_host}:{self.server_port}"
        )
        self.allowed_origin = f"http://{self.allowed_authority}"
        self.on_activate = on_activate
        self.on_quit = on_quit


class GuiIPv6Server(GuiServer):
    address_family = socket.AF_INET6


class GuiHandler(BaseHTTPRequestHandler):
    server: GuiServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, status: int, data: object) -> None:
        encoded = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _authorized(self) -> bool:
        return secrets.compare_digest(
            self.headers.get("X-Spade65-Token", ""), self.server.token
        )

    def _single_header(self, name: str) -> str | None:
        get_all = getattr(self.headers, "get_all", None)
        if callable(get_all):
            values = get_all(name, [])
            return values[0] if len(values) == 1 else None
        return self.headers.get(name)

    def _host_allowed(self) -> bool:
        host = self._single_header("Host")
        return host is not None and secrets.compare_digest(
            host.casefold(), self.server.allowed_authority.casefold()
        )

    def _origin_allowed(self) -> bool:
        origin = self._single_header("Origin")
        return origin is None or secrets.compare_digest(
            origin.casefold(), self.server.allowed_origin.casefold()
        )

    def _reject_invalid_host(self) -> bool:
        if self._host_allowed():
            return False
        self._json(
            HTTPStatus.MISDIRECTED_REQUEST,
            {"error": "request host is not the Spade65 localhost authority"},
        )
        return True

    def do_GET(self) -> None:
        if self._reject_invalid_host():
            return
        path = urlparse(self.path).path
        if path == "/api/status":
            if not self._authorized():
                self._json(HTTPStatus.FORBIDDEN, {"error": "invalid session token"})
                return
            self._json(HTTPStatus.OK, gui_metadata())
            return
        asset = "index.html" if path == "/" else path.removeprefix("/")
        if asset not in {
            "index.html",
            "app.css",
            "keyboard.css",
            "effects.css",
            "layout-state.js",
            "app.js",
        } and not re.fullmatch(r"locales/[A-Za-z0-9_-]+\.json", asset):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            content = files("spade65.web").joinpath(asset).read_bytes()
        except (FileNotFoundError, IsADirectoryError):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if asset == "index.html":
            content = content.replace(b"__SPADE65_TOKEN__", self.server.token.encode())
        content_type = {
            "index.html": "text/html; charset=utf-8",
            "app.css": "text/css; charset=utf-8",
            "keyboard.css": "text/css; charset=utf-8",
            "effects.css": "text/css; charset=utf-8",
            "layout-state.js": "text/javascript; charset=utf-8",
            "app.js": "text/javascript; charset=utf-8",
        }.get(asset, "application/json; charset=utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        if self._reject_invalid_host():
            return
        if not self._origin_allowed():
            self._json(HTTPStatus.FORBIDDEN, {"error": "invalid request origin"})
            return
        if not self._authorized():
            self._json(HTTPStatus.FORBIDDEN, {"error": "invalid session token"})
            return
        path = urlparse(self.path).path
        if path == "/api/activate":
            if self.server.on_activate is None:
                self._json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {"ok": False, "error": "GUI activation is unavailable"},
                )
                return
            try:
                activated = self.server.on_activate()
            except Exception as error:
                self._json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {"ok": False, "error": f"GUI activation failed: {error}"},
                )
                return
            if activated is False:
                self._json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {"ok": False, "error": "GUI activation was not accepted"},
                )
                return
            self._json(HTTPStatus.OK, {"ok": True})
            return
        if path == "/api/quit":
            self._json(HTTPStatus.OK, {"ok": True})

            def stop() -> None:
                try:
                    if self.server.on_quit is not None:
                        self.server.on_quit()
                finally:
                    self.server.shutdown()

            threading.Thread(target=stop, daemon=True).start()
            return
        if not path.startswith("/api/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= MAX_REQUEST_BYTES:
                raise ValueError("request is too large")
            payload = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("request body must be an object")
            result = execute_action(path.removeprefix("/api/"), payload)
            self._json(HTTPStatus.OK, {"ok": True, **result})
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(error)})


def create_gui_server(*, host: str, port: int) -> tuple[GuiServer, str]:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("GUI may only bind to localhost")
    token = secrets.token_urlsafe(24)
    server_class = GuiIPv6Server if host == "::1" else GuiServer
    server = server_class((host, port), token)
    url = f"{server.allowed_origin}/"
    return server, url


def run_gui(*, host: str = GUI_HOST, port: int = GUI_PORT, open_browser: bool = True) -> None:
    server, url = create_gui_server(host=host, port=port)
    if sys.stdout is not None:
        print(f"Spade65 GUI: {url}")
        print("Press Ctrl+C to stop.")
    if open_browser:
        server.on_activate = lambda: webbrowser.open(url)
        threading.Timer(0.2, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
