import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from spade65.desktop import (
    ActivationBridge,
    DesktopApi,
    DesktopUnavailable,
    desktop_backend,
    desktop_storage_path,
    run_desktop,
    verify_desktop_runtime,
)


class DesktopTests(unittest.TestCase):
    def test_activation_is_queued_until_the_native_window_is_ready(self) -> None:
        class ShownEvent:
            def __init__(self):
                self.handler = None

            def __iadd__(self, handler):
                self.handler = handler
                return self

            def is_set(self):
                return False

            def fire(self):
                assert self.handler is not None
                self.handler()

        bridge = ActivationBridge()
        shown = ShownEvent()
        window = SimpleNamespace(
            events=SimpleNamespace(shown=shown),
            show=MagicMock(),
            restore=MagicMock(),
        )
        with patch("spade65.desktop.threading.Thread") as thread:
            self.assertTrue(bridge())
            bridge.bind(window)
            thread.assert_not_called()
            shown.fire()
        thread.assert_called_once()
        thread.return_value.start.assert_called_once_with()
        thread.call_args.kwargs["target"](*thread.call_args.kwargs["args"])
        window.show.assert_called_once_with()
        window.restore.assert_called_once_with()

    def test_ready_window_activation_reports_renderer_failure(self) -> None:
        bridge = ActivationBridge()
        window = SimpleNamespace(
            show=MagicMock(side_effect=RuntimeError("renderer is gone")),
            restore=MagicMock(),
        )
        bridge.bind(window)
        with self.assertRaisesRegex(RuntimeError, "renderer is gone"):
            bridge()
        window.restore.assert_not_called()

    def test_native_json_export_uses_save_dialog_and_sanitizes_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "profile.json"
            window = SimpleNamespace(
                create_file_dialog=MagicMock(return_value=(str(output),))
            )
            api = DesktopApi(
                SimpleNamespace(FileDialog=SimpleNamespace(SAVE=30))
            )
            api._bind_window(window)
            result = api.save_json('{"profile": true}\n', "../../my/profile.json")

            self.assertEqual(
                output.read_text(encoding="utf-8"), '{"profile": true}\n'
            )
            self.assertEqual(result, {"saved": True, "name": "profile.json"})
            self.assertEqual(
                window.create_file_dialog.call_args.kwargs["save_filename"],
                "profile.json",
            )

    def test_native_json_export_rejects_invalid_content(self) -> None:
        api = DesktopApi(SimpleNamespace())
        with self.assertRaisesRegex(ValueError, "valid JSON"):
            api.save_json("not json", "profile.json")

    def test_storage_path_uses_platform_application_data(self) -> None:
        home = Path("/users/test")
        self.assertEqual(
            desktop_storage_path(
                "linux", environ={"XDG_DATA_HOME": "/data"}, home=home
            ),
            Path("/data/spade65/webview"),
        )
        self.assertEqual(
            desktop_storage_path(
                "win32", environ={"LOCALAPPDATA": "C:/Local"}, home=home
            ),
            Path("C:/Local/Spade65/WebView"),
        )
        self.assertIsNone(desktop_storage_path("darwin", environ={}, home=home))

    def test_linux_forces_the_bundled_qt_backend(self) -> None:
        self.assertEqual(desktop_backend("linux"), "qt")
        self.assertEqual(desktop_backend("linux2"), "qt")
        self.assertIsNone(desktop_backend("win32"))
        self.assertIsNone(desktop_backend("darwin"))

    def test_linux_does_not_import_qt_before_start_sets_storage(self) -> None:
        window = SimpleNamespace(
            destroy=MagicMock(),
            show=MagicMock(),
            restore=MagicMock(),
        )
        webview = SimpleNamespace(
            settings={"ALLOW_DOWNLOADS": False},
            create_window=MagicMock(return_value=window),
            start=MagicMock(),
        )
        server = SimpleNamespace(
            serve_forever=MagicMock(),
            shutdown=MagicMock(),
            server_close=MagicMock(),
            on_activate=None,
            on_quit=None,
        )
        with (
            patch("spade65.desktop.load_webview", return_value=webview),
            patch("spade65.desktop.verify_desktop_runtime") as verify,
            patch("spade65.desktop.sys.stdout", None),
            patch(
                "spade65.desktop.create_gui_server",
                return_value=(server, "http://127.0.0.1:49152/"),
            ),
        ):
            run_desktop(port=0, platform_name="linux")

        verify.assert_not_called()
        webview.start.assert_called_once()

    def test_desktop_window_persists_storage_and_enables_downloads(self) -> None:
        window = SimpleNamespace(
            destroy=MagicMock(),
            show=MagicMock(),
            restore=MagicMock(),
        )
        webview = SimpleNamespace(
            settings={"ALLOW_DOWNLOADS": False},
            create_window=MagicMock(return_value=window),
            start=MagicMock(),
            WebViewException=RuntimeError,
        )
        server = SimpleNamespace(
            serve_forever=MagicMock(),
            shutdown=MagicMock(),
            server_close=MagicMock(),
            on_activate=None,
            on_quit=None,
        )
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch(
                    "spade65.desktop.desktop_storage_path",
                    return_value=Path(directory) / "webview",
                ),
                patch(
                    "spade65.desktop.create_gui_server",
                    return_value=(server, "http://127.0.0.1:49152/"),
                ),
            ):
                run_desktop(port=0, webview_module=webview, platform_name="linux")

        self.assertTrue(webview.settings["ALLOW_DOWNLOADS"])
        self.assertTrue(webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"])
        _, url = webview.create_window.call_args.args[:2]
        self.assertEqual(url, "http://127.0.0.1:49152/")
        self.assertEqual(webview.create_window.call_args.kwargs["min_size"], (1000, 640))
        self.assertIsInstance(
            webview.create_window.call_args.kwargs["js_api"], DesktopApi
        )
        webview.start.assert_called_once_with(
            gui="qt",
            debug=False,
            private_mode=False,
            storage_path=str(Path(directory) / "webview"),
        )
        server.server_close.assert_called_once_with()

    def test_windows_uses_webview2_download_instead_of_worker_dialog(self) -> None:
        window = SimpleNamespace(
            destroy=MagicMock(), show=MagicMock(), restore=MagicMock()
        )
        webview = SimpleNamespace(
            settings={"ALLOW_DOWNLOADS": False},
            create_window=MagicMock(return_value=window),
            start=MagicMock(),
        )
        server = SimpleNamespace(
            serve_forever=MagicMock(),
            shutdown=MagicMock(),
            server_close=MagicMock(),
            on_activate=None,
            on_quit=None,
        )
        with patch(
            "spade65.desktop.create_gui_server",
            return_value=(server, "http://127.0.0.1:49152/"),
        ):
            run_desktop(
                port=0, webview_module=webview, platform_name="win32"
            )

        self.assertIsNone(webview.create_window.call_args.kwargs["js_api"])
        self.assertTrue(webview.settings["ALLOW_DOWNLOADS"])
        self.assertTrue(webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"])

    def test_runtime_check_rejects_windows_mshtml_fallback(self) -> None:
        modules = {
            "webview": SimpleNamespace(),
            "webview.platforms.winforms": SimpleNamespace(renderer="mshtml"),
        }
        with patch(
            "spade65.desktop.importlib.import_module",
            side_effect=lambda name: modules[name],
        ):
            with self.assertRaisesRegex(DesktopUnavailable, "WebView2"):
                verify_desktop_runtime("win32")

    def test_backend_failure_is_reported_for_browser_fallback(self) -> None:
        window = SimpleNamespace(
            destroy=MagicMock(),
            show=MagicMock(),
            restore=MagicMock(),
        )
        webview = SimpleNamespace(
            settings={"ALLOW_DOWNLOADS": False},
            create_window=MagicMock(return_value=window),
            start=MagicMock(side_effect=RuntimeError("renderer failed")),
        )
        server = SimpleNamespace(
            serve_forever=MagicMock(),
            shutdown=MagicMock(),
            server_close=MagicMock(),
            on_activate=None,
            on_quit=None,
        )
        with (
            patch(
                "spade65.desktop.create_gui_server",
                return_value=(server, "http://127.0.0.1:49152/"),
            ),
            self.assertRaisesRegex(DesktopUnavailable, "renderer failed"),
        ):
            run_desktop(port=0, webview_module=webview, platform_name="linux")
        server.server_close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
