import errno
import threading
import unittest
import urllib.request
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from spade65.gui import (
    GuiHandler,
    SAFE_ACTIONS,
    _send_features,
    create_gui_server,
    execute_action,
    gui_metadata,
    run_gui,
)
from spade65.device import Device, ReportShape
from spade65.keymap import profile_template


class GuiTests(unittest.TestCase):
    def test_gui_port_can_be_rebound_after_serving_a_request(self) -> None:
        try:
            server, url = create_gui_server(host="127.0.0.1", port=0)
        except PermissionError as error:
            if error.errno == errno.EPERM:
                self.skipTest("test sandbox does not permit loopback sockets")
            raise
        port = server.server_port
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(url, timeout=5) as response:
                self.assertEqual(response.status, HTTPStatus.OK)
                self.assertIn(b"Spade65 Control Center", response.read())
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)

        replacement, _url = create_gui_server(host="127.0.0.1", port=port)
        replacement.server_close()

    def test_browser_fallback_runs_without_a_console_stream(self) -> None:
        server = SimpleNamespace(
            serve_forever=MagicMock(),
            server_close=MagicMock(),
            on_activate=None,
        )
        with (
            patch(
                "spade65.gui.create_gui_server",
                return_value=(server, "http://127.0.0.1:8765/"),
            ),
            patch("spade65.gui.sys.stdout", None),
        ):
            run_gui(open_browser=False)
        server.serve_forever.assert_called_once_with()
        server.server_close.assert_called_once_with()

    def test_metadata_exposes_safe_scope_and_no_firmware(self) -> None:
        with patch("spade65.gui.discover_devices", return_value=[]):
            metadata = gui_metadata()
        self.assertFalse(metadata["firmware_update"])
        self.assertEqual(set(metadata["safe_actions"]), set(SAFE_ACTIONS))
        self.assertNotIn("firmware", metadata["safe_actions"])
        self.assertIn("Mouse", metadata["usage_groups"])
        self.assertIn("mouse-left", metadata["usage_groups"]["Mouse"])

    def test_validate_compiles_without_device_write(self) -> None:
        result = execute_action("validate", {"profile": profile_template()})
        self.assertEqual(result["keymap_bytes"], 620)

    def test_unknown_and_firmware_actions_are_rejected(self) -> None:
        for action in ("firmware", "flash", "bootloader", "raw-write"):
            with self.subTest(action=action), self.assertRaises(ValueError):
                execute_action(action, {})

    def test_reset_requires_exact_confirmation_before_discovery(self) -> None:
        with patch("spade65.gui.discover_devices") as discover:
            with self.assertRaisesRegex(RuntimeError, "RESET SPADE65"):
                execute_action("reset", {"confirmation": "yes"})
        discover.assert_not_called()

    def test_profile_requires_exact_confirmation_before_discovery(self) -> None:
        with patch("spade65.gui.discover_devices") as discover:
            with self.assertRaisesRegex(RuntimeError, "APPLY PROFILE"):
                execute_action("profile", {"profile": profile_template()})
        discover.assert_not_called()

    def test_every_feature_write_is_descriptor_gated(self) -> None:
        device = Device(
            path="/dev/hidraw-test",  # type: ignore[arg-type]
            vendor_id=0x0603,
            product_id=0x0351,
            reports=[ReportShape("feature", 7, 619 * 8)],
        )
        with patch("spade65.gui.send_feature_report") as send:
            with self.assertRaisesRegex(RuntimeError, "report 0x08 mismatch"):
                _send_features(device, [bytes([8]) + bytes(7)])
        send.assert_not_called()

    def test_authenticated_quit_stops_only_the_local_server(self) -> None:
        handler = GuiHandler.__new__(GuiHandler)
        handler.headers = {
            "Host": "127.0.0.1:8765",
            "X-Spade65-Token": "test-token",
        }
        handler.path = "/api/quit"
        handler.server = SimpleNamespace(
            token="test-token",
            allowed_authority="127.0.0.1:8765",
            allowed_origin="http://127.0.0.1:8765",
            shutdown=MagicMock(),
            on_quit=MagicMock(),
        )
        handler._json = MagicMock()
        with patch("spade65.gui.threading.Thread") as thread:
            handler.do_POST()
        handler._json.assert_called_once_with(HTTPStatus.OK, {"ok": True})
        thread.assert_called_once()
        self.assertTrue(thread.call_args.kwargs["daemon"])
        thread.call_args.kwargs["target"]()
        handler.server.on_quit.assert_called_once_with()
        handler.server.shutdown.assert_called_once_with()
        thread.return_value.start.assert_called_once_with()

    def test_quit_rejects_an_invalid_session_token(self) -> None:
        handler = GuiHandler.__new__(GuiHandler)
        handler.headers = {
            "Host": "127.0.0.1:8765",
            "X-Spade65-Token": "wrong-token",
        }
        handler.path = "/api/quit"
        handler.server = SimpleNamespace(
            token="test-token",
            allowed_authority="127.0.0.1:8765",
            allowed_origin="http://127.0.0.1:8765",
            shutdown=MagicMock(),
            on_quit=MagicMock(),
        )
        handler._json = MagicMock()
        with patch("spade65.gui.threading.Thread") as thread:
            handler.do_POST()
        handler._json.assert_called_once_with(
            HTTPStatus.FORBIDDEN, {"error": "invalid session token"}
        )
        handler.server.shutdown.assert_not_called()
        thread.assert_not_called()

    def test_authenticated_activate_restores_the_existing_window(self) -> None:
        handler = GuiHandler.__new__(GuiHandler)
        handler.headers = {
            "Host": "127.0.0.1:8765",
            "X-Spade65-Token": "test-token",
        }
        handler.path = "/api/activate"
        handler.server = SimpleNamespace(
            token="test-token",
            allowed_authority="127.0.0.1:8765",
            allowed_origin="http://127.0.0.1:8765",
            on_activate=MagicMock(),
        )
        handler._json = MagicMock()
        handler.do_POST()
        handler._json.assert_called_once_with(HTTPStatus.OK, {"ok": True})
        handler.server.on_activate.assert_called_once_with()

    def test_activate_reports_a_browser_or_window_restore_failure(self) -> None:
        handler = GuiHandler.__new__(GuiHandler)
        handler.headers = {
            "Host": "127.0.0.1:8765",
            "X-Spade65-Token": "test-token",
        }
        handler.path = "/api/activate"
        handler.server = SimpleNamespace(
            token="test-token",
            allowed_authority="127.0.0.1:8765",
            allowed_origin="http://127.0.0.1:8765",
            on_activate=MagicMock(return_value=False),
        )
        handler._json = MagicMock()
        handler.do_POST()
        handler._json.assert_called_once_with(
            HTTPStatus.SERVICE_UNAVAILABLE,
            {"ok": False, "error": "GUI activation was not accepted"},
        )

    def test_foreign_host_cannot_read_the_page_token(self) -> None:
        handler = GuiHandler.__new__(GuiHandler)
        handler.headers = {"Host": "attacker.example:8765"}
        handler.path = "/"
        handler.server = SimpleNamespace(
            token="test-token",
            allowed_authority="127.0.0.1:8765",
            allowed_origin="http://127.0.0.1:8765",
        )
        handler._json = MagicMock()
        handler.do_GET()
        handler._json.assert_called_once_with(
            HTTPStatus.MISDIRECTED_REQUEST,
            {"error": "request host is not the Spade65 localhost authority"},
        )

    def test_foreign_origin_cannot_call_an_authenticated_action(self) -> None:
        handler = GuiHandler.__new__(GuiHandler)
        handler.headers = {
            "Host": "127.0.0.1:8765",
            "Origin": "https://attacker.example",
            "X-Spade65-Token": "test-token",
        }
        handler.path = "/api/reset"
        handler.server = SimpleNamespace(
            token="test-token",
            allowed_authority="127.0.0.1:8765",
            allowed_origin="http://127.0.0.1:8765",
        )
        handler._json = MagicMock()
        handler.do_POST()
        handler._json.assert_called_once_with(
            HTTPStatus.FORBIDDEN,
            {"error": "invalid request origin"},
        )


if __name__ == "__main__":
    unittest.main()
