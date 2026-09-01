import tempfile
import unittest
import webbrowser
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

from spade65.desktop import (
    ActivationBridge,
    DesktopApi,
    DesktopUnavailable,
    MAX_NATIVE_CLIPBOARD_BYTES,
    _copy_linux_text,
    _copy_macos_text,
    _copy_native_text,
    _copy_qt_text,
    _copy_windows_text,
    _linux_external_environment,
    _open_linux_external_url,
    _trusted_external_opener,
    _validated_external_url,
    desktop_backend,
    desktop_storage_path,
    run_desktop,
    verify_desktop_runtime,
)


class DesktopTests(unittest.TestCase):
    def test_linux_external_environment_restores_host_libraries(self) -> None:
        environment = _linux_external_environment(
            {
                "PATH": "/usr/bin",
                "LD_LIBRARY_PATH": "/app/bundled-libs",
                "LD_LIBRARY_PATH_ORIG": "/host/libs",
                "QT_PLUGIN_PATH": "/app/qt/plugins",
                "QTWEBENGINEPROCESS_PATH": "/app/QtWebEngineProcess",
            }
        )

        self.assertEqual(environment["LD_LIBRARY_PATH"], "/host/libs")
        self.assertNotIn("LD_LIBRARY_PATH_ORIG", environment)
        self.assertNotIn("QT_PLUGIN_PATH", environment)
        self.assertNotIn("QTWEBENGINEPROCESS_PATH", environment)

    def test_linux_external_url_uses_clean_host_environment(self) -> None:
        process = MagicMock()
        process.wait.return_value = 0
        clean_environment = {"PATH": "/usr/bin", "DISPLAY": ":0"}
        with (
            patch(
                "spade65.desktop._linux_external_environment",
                return_value=clean_environment,
            ),
            patch("spade65.desktop.shutil.which", return_value="/usr/bin/xdg-open"),
            patch("spade65.desktop.subprocess.Popen", return_value=process) as popen,
        ):
            opened = _open_linux_external_url("https://example.com", 2, True)

        self.assertTrue(opened)
        popen.assert_called_once_with(
            ["/usr/bin/xdg-open", "https://example.com"],
            env=clean_environment,
            stdout=-3,
            stderr=-3,
            start_new_session=True,
        )

    def test_linux_external_url_falls_back_after_opener_failure(self) -> None:
        failed = MagicMock()
        failed.wait.return_value = 3
        opened = MagicMock()
        opened.wait.return_value = 0
        with (
            patch(
                "spade65.desktop._linux_external_environment",
                return_value={"PATH": "/usr/bin"},
            ),
            patch(
                "spade65.desktop.shutil.which",
                side_effect=lambda name, path=None: f"/usr/bin/{name}",
            ),
            patch(
                "spade65.desktop.subprocess.Popen",
                side_effect=[failed, opened],
            ) as popen,
        ):
            result = _open_linux_external_url("https://example.com")

        self.assertTrue(result)
        self.assertEqual(popen.call_count, 2)
        self.assertEqual(
            popen.call_args_list[1].args[0],
            ["/usr/bin/gio", "open", "https://example.com"],
        )

    def test_linux_clipboard_uses_clean_host_environment_and_exact_text(self) -> None:
        clean_environment = {
            "PATH": "/usr/bin",
            "WAYLAND_DISPLAY": "wayland-1",
        }
        copied = SimpleNamespace(returncode=0)
        contents = "mkdir -p ~/.config/spade65\nspade65ctl service install\n"
        with (
            patch(
                "spade65.desktop._linux_external_environment",
                return_value=clean_environment,
            ),
            patch(
                "spade65.desktop.shutil.which",
                return_value="/usr/bin/wl-copy",
            ) as which,
            patch(
                "spade65.desktop.subprocess.run", return_value=copied
            ) as run,
        ):
            self.assertTrue(_copy_linux_text(contents))

        which.assert_called_once_with("wl-copy", path="/usr/bin")
        run.assert_called_once_with(
            [
                "/usr/bin/wl-copy",
                "--type",
                "text/plain;charset=utf-8",
            ],
            input=contents.encode("utf-8"),
            env=clean_environment,
            stdout=-3,
            stderr=-3,
            timeout=3,
            check=False,
        )

    def test_linux_clipboard_falls_back_between_host_tools(self) -> None:
        failed = SimpleNamespace(returncode=1)
        copied = SimpleNamespace(returncode=0)
        with (
            patch(
                "spade65.desktop._linux_external_environment",
                return_value={"PATH": "/usr/bin"},
            ),
            patch(
                "spade65.desktop.shutil.which",
                side_effect=lambda name, path=None: f"/usr/bin/{name}",
            ),
            patch(
                "spade65.desktop.subprocess.run",
                side_effect=[failed, copied],
            ) as run,
        ):
            self.assertTrue(_copy_linux_text("copy me"))

        self.assertEqual(run.call_count, 2)
        self.assertEqual(
            run.call_args_list[1].args[0],
            ["/usr/bin/xclip", "-selection", "clipboard", "-in"],
        )

    def test_macos_clipboard_uses_appkit_with_unicode(self) -> None:
        contents = "Spade65 — profile"
        pasteboard = SimpleNamespace(
            clearContents=MagicMock(),
            setString_forType_=MagicMock(return_value=True),
        )
        appkit = ModuleType("AppKit")
        appkit.NSPasteboard = SimpleNamespace(
            generalPasteboard=MagicMock(return_value=pasteboard)
        )
        appkit.NSPasteboardTypeString = "public.utf8-plain-text"
        foundation = ModuleType("Foundation")
        foundation.NSOperationQueue = SimpleNamespace()
        foundation.NSThread = SimpleNamespace(isMainThread=lambda: True)
        with patch.dict(
            "sys.modules", {"AppKit": appkit, "Foundation": foundation}
        ):
            self.assertTrue(_copy_macos_text(contents))

        pasteboard.clearContents.assert_called_once_with()
        pasteboard.setString_forType_.assert_called_once_with(
            contents, "public.utf8-plain-text"
        )

    def test_macos_clipboard_queues_a_background_call_on_main(self) -> None:
        pasteboard = SimpleNamespace(
            clearContents=MagicMock(),
            setString_forType_=MagicMock(return_value=True),
        )
        queue = SimpleNamespace(
            addOperationWithBlock_=MagicMock(
                side_effect=lambda callback: callback()
            )
        )
        appkit = ModuleType("AppKit")
        appkit.NSPasteboard = SimpleNamespace(
            generalPasteboard=lambda: pasteboard
        )
        appkit.NSPasteboardTypeString = "public.utf8-plain-text"
        foundation = ModuleType("Foundation")
        foundation.NSOperationQueue = SimpleNamespace(mainQueue=lambda: queue)
        foundation.NSThread = SimpleNamespace(isMainThread=lambda: False)
        with patch.dict(
            "sys.modules", {"AppKit": appkit, "Foundation": foundation}
        ):
            self.assertTrue(_copy_macos_text("activation — Spade65"))

        queue.addOperationWithBlock_.assert_called_once()
        pasteboard.setString_forType_.assert_called_once_with(
            "activation — Spade65", "public.utf8-plain-text"
        )

    def test_macos_timed_out_request_cannot_later_clear_clipboard(self) -> None:
        class TimedOutEvent:
            def __init__(self):
                self.ready = False

            def set(self):
                self.ready = True

            def is_set(self):
                return self.ready

            def wait(self, _timeout):
                return False

        callbacks = []
        pasteboard = SimpleNamespace(
            clearContents=MagicMock(),
            setString_forType_=MagicMock(return_value=True),
        )
        queue = SimpleNamespace(
            addOperationWithBlock_=lambda callback: callbacks.append(callback)
        )
        appkit = ModuleType("AppKit")
        appkit.NSPasteboard = SimpleNamespace(
            generalPasteboard=lambda: pasteboard
        )
        appkit.NSPasteboardTypeString = "public.utf8-plain-text"
        foundation = ModuleType("Foundation")
        foundation.NSOperationQueue = SimpleNamespace(mainQueue=lambda: queue)
        foundation.NSThread = SimpleNamespace(isMainThread=lambda: False)
        with (
            patch.dict(
                "sys.modules", {"AppKit": appkit, "Foundation": foundation}
            ),
            patch("spade65.desktop.threading.Event", TimedOutEvent),
        ):
            self.assertFalse(_copy_macos_text("late commands"))

        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        pasteboard.clearContents.assert_not_called()
        pasteboard.setString_forType_.assert_not_called()

    def test_windows_clipboard_invokes_the_native_sta_window(self) -> None:
        writes = []

        class Clipboard:
            @staticmethod
            def SetText(value):
                writes.append(value)

            @staticmethod
            def GetText():
                return writes[-1]

        system = ModuleType("System")
        system.Action = lambda callback: callback
        windows = ModuleType("System.Windows")
        forms = ModuleType("System.Windows.Forms")
        forms.Clipboard = Clipboard
        form = SimpleNamespace(
            InvokeRequired=True,
            Invoke=MagicMock(side_effect=lambda action: action()),
        )
        window = SimpleNamespace(native=form)
        with patch.dict(
            "sys.modules",
            {
                "System": system,
                "System.Windows": windows,
                "System.Windows.Forms": forms,
            },
        ):
            self.assertTrue(_copy_windows_text("Spade65 — commands", window))

        self.assertEqual(writes, ["Spade65 — commands"])
        form.Invoke.assert_called_once()

    def test_native_clipboard_dispatches_by_platform(self) -> None:
        window = SimpleNamespace(native=object())
        with (
            patch("spade65.desktop._copy_qt_text", return_value=True) as qt,
            patch("spade65.desktop._copy_linux_text") as linux,
        ):
            self.assertTrue(_copy_native_text("commands", "linux"))
        qt.assert_called_once_with("commands")
        linux.assert_not_called()

        with (
            patch("spade65.desktop._copy_qt_text", return_value=False),
            patch(
                "spade65.desktop._copy_linux_text", return_value=True
            ) as linux,
        ):
            self.assertTrue(_copy_native_text("commands", "linux"))
        linux.assert_called_once_with("commands")

        with patch(
            "spade65.desktop._copy_macos_text", return_value=True
        ) as macos:
            self.assertTrue(_copy_native_text("commands", "darwin"))
        macos.assert_called_once_with("commands")

        with patch(
            "spade65.desktop._copy_windows_text", return_value=True
        ) as windows:
            self.assertTrue(
                _copy_native_text("commands", "win32", window=window)
            )
        windows.assert_called_once_with("commands", window)

        self.assertFalse(_copy_native_text("commands", "freebsd"))

    def test_desktop_api_copies_exact_canonical_service_commands(self) -> None:
        copied = []
        contents = "command one\ncommand two --flag='nilai'\n"
        api = DesktopApi(
            SimpleNamespace(),
            platform_name="linux",
            clipboard_writer=lambda text: copied.append(text) or True,
        )
        with patch(
            "spade65.desktop.release_service_setup",
            return_value={"prepare_commands": contents},
        ) as setup:
            self.assertEqual(
                api.copy_service_commands("prepare_commands"),
                {"copied": True},
            )
        self.assertEqual(copied, [contents])
        setup.assert_called_once_with(platform="linux")

    def test_desktop_api_rejects_unknown_service_command_fields(self) -> None:
        writer = MagicMock(return_value=True)
        api = DesktopApi(SimpleNamespace(), clipboard_writer=writer)
        for field in (None, b"prepare_commands", "", "firmware_commands"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                api.copy_service_commands(field)
        writer.assert_not_called()

    def test_desktop_api_rejects_unsafe_generated_command_contents(self) -> None:
        writer = MagicMock(return_value=True)
        api = DesktopApi(SimpleNamespace(), clipboard_writer=writer)
        for contents, message in (
            ("", "only in a release package"),
            ("safe\x00unsafe", "NUL"),
            ("x" * (MAX_NATIVE_CLIPBOARD_BYTES + 1), "too large"),
        ):
            with (
                self.subTest(message=message),
                patch(
                    "spade65.desktop.release_service_setup",
                    return_value={"prepare_commands": contents},
                ),
                self.assertRaisesRegex((RuntimeError, ValueError), message),
            ):
                api.copy_service_commands("prepare_commands")
        writer.assert_not_called()

    def test_desktop_api_reports_native_clipboard_failure(self) -> None:
        api = DesktopApi(
            SimpleNamespace(), clipboard_writer=lambda _contents: False
        )
        with (
            patch(
                "spade65.desktop.release_service_setup",
                return_value={"activate_commands": "activate commands"},
            ),
            self.assertRaisesRegex(RuntimeError, "could not be updated"),
        ):
            api.copy_service_commands("activate_commands")

    def test_desktop_api_passes_the_bound_window_to_native_clipboard(self) -> None:
        window = SimpleNamespace(native=object())
        api = DesktopApi(SimpleNamespace(), platform_name="win32")
        api._bind_window(window)
        with (
            patch(
                "spade65.desktop.release_service_setup",
                return_value={"prepare_commands": "prepare commands"},
            ),
            patch(
                "spade65.desktop._copy_native_text", return_value=True
            ) as copy,
        ):
            self.assertEqual(
                api.copy_service_commands("prepare_commands"),
                {"copied": True},
            )

        copy.assert_called_once_with(
            "prepare commands", "win32", window=window
        )

    def test_desktop_api_opens_project_links_with_the_host_browser(self) -> None:
        url = (
            "https://github.com/dirhamtriyadi/spade65-non-qmk/"
            "blob/main/docs/host-features.md"
        )
        api = DesktopApi(SimpleNamespace(), platform_name="linux")
        with patch(
            "spade65.desktop._open_linux_external_url", return_value=True
        ) as open_url:
            result = api.open_external_url(url)

        self.assertEqual(result, {"opened": True})
        open_url.assert_called_once_with(url, new=2, autoraise=True)

    def test_all_shipped_external_destinations_are_approved(self) -> None:
        for url in (
            "https://github.com/dirhamtriyadi/spade65-non-qmk",
            "https://github.com/dirhamtriyadi/spade65-non-qmk/releases",
            "https://github.com/dirhamtriyadi/spade65-non-qmk/"
            "blob/main/docs/host-features.md",
            "https://github.com/dirhamtriyadi/spade65-non-qmk/"
            "blob/main/docs/id/host-features.md",
        ):
            with self.subTest(url=url):
                self.assertEqual(_validated_external_url(url), url)

    def test_desktop_api_uses_the_system_browser_outside_linux(self) -> None:
        url = "https://github.com/dirhamtriyadi/spade65-non-qmk/releases"
        for platform in ("win32", "darwin"):
            with self.subTest(platform=platform):
                api = DesktopApi(SimpleNamespace(), platform_name=platform)
                with patch(
                    "spade65.desktop.webbrowser.open", return_value=True
                ) as open_url:
                    self.assertEqual(api.open_external_url(url), {"opened": True})
                open_url.assert_called_once_with(url, new=2, autoraise=True)

    def test_desktop_api_rejects_untrusted_external_links(self) -> None:
        for value in (
            "http://github.com/dirhamtriyadi/spade65-non-qmk",
            "https://example.com/dirhamtriyadi/spade65-non-qmk",
            "https://github.com.evil.test/dirhamtriyadi/spade65-non-qmk",
            "https://user@github.com/dirhamtriyadi/spade65-non-qmk",
            "https://github.com/another/project",
            "https://github.com/dirhamtriyadi/spade65-non-qmk/../another/project",
            "https://github.com/dirhamtriyadi/spade65-non-qmk/"
            "%2e%2e/%2e%2e/another/project",
            " https://github.com/dirhamtriyadi/spade65-non-qmk",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _validated_external_url(value)

    def test_pywebview_fallback_opener_uses_the_same_allowlist(self) -> None:
        system_open = MagicMock(return_value=True)
        linux_open = _trusted_external_opener("linux", system_open)
        valid = "https://github.com/dirhamtriyadi/spade65-non-qmk/releases"
        invalid = "https://example.com/"
        with patch(
            "spade65.desktop._open_linux_external_url", return_value=True
        ) as open_url:
            self.assertTrue(linux_open(valid, 2, True))
            self.assertFalse(linux_open(invalid, 2, True))

        open_url.assert_called_once_with(valid, 2, True)
        system_open.assert_not_called()

    def test_desktop_api_reports_external_browser_failure(self) -> None:
        url = "https://github.com/dirhamtriyadi/spade65-non-qmk/releases"
        api = DesktopApi(SimpleNamespace(), platform_name="win32")
        with (
            patch("spade65.desktop.webbrowser.open", return_value=False),
            self.assertRaisesRegex(RuntimeError, "could not be opened"),
        ):
            api.open_external_url(url)

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
                SimpleNamespace(FileDialog=SimpleNamespace(SAVE=30)),
                platform_name="linux",
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
        api = DesktopApi(SimpleNamespace(), platform_name="linux")
        with self.assertRaisesRegex(ValueError, "valid JSON"):
            api.save_json("not json", "profile.json")

    def test_windows_native_export_bridge_is_explicitly_disabled(self) -> None:
        api = DesktopApi(SimpleNamespace(), platform_name="win32")
        with self.assertRaisesRegex(RuntimeError, "WebView2"):
            api.save_json("{}", "profile.json")

    def test_desktop_api_persists_tray_and_controls_login_startup(self) -> None:
        class FakeTray:
            ready = True
            available = True
            close_to_tray = True

            def wait_until_ready(self, _timeout):
                return True

            def set_close_to_tray(self, enabled):
                self.close_to_tray = enabled

        startup = {
            "platform": "linux",
            "supported": True,
            "enabled": False,
            "current": False,
            "path": "/config/autostart/spade65.desktop",
        }
        with tempfile.TemporaryDirectory() as directory:
            preferences = Path(directory) / "desktop.json"
            tray = FakeTray()
            api = DesktopApi(
                SimpleNamespace(),
                tray_controller=tray,
                platform_name="linux",
                preferences_path=preferences,
            )
            with (
                patch(
                    "spade65.desktop.gui_auto_start_status",
                    return_value=startup,
                ),
                patch("spade65.desktop.set_gui_auto_start") as set_startup,
            ):
                status = api.desktop_status()
                self.assertTrue(status["tray_available"])
                self.assertTrue(status["native_export"])
                changed = api.set_close_to_tray(False)
                self.assertFalse(changed["close_to_tray"])
                api.set_auto_start(True)

            self.assertIn(
                '"close_to_tray": false',
                preferences.read_text(encoding="utf-8"),
            )
            set_startup.assert_called_once_with(True, platform="linux")

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
        original_browser_open = webbrowser.open
        window = SimpleNamespace(
            destroy=MagicMock(),
            show=MagicMock(),
            restore=MagicMock(),
        )
        browser_open_during_start = []
        webview = SimpleNamespace(
            settings={"ALLOW_DOWNLOADS": False},
            create_window=MagicMock(return_value=window),
            start=MagicMock(
                side_effect=lambda **kwargs: browser_open_during_start.append(
                    webbrowser.open
                )
            ),
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
        self.assertEqual(len(browser_open_during_start), 1)
        self.assertIsNot(browser_open_during_start[0], original_browser_open)
        self.assertIsNot(browser_open_during_start[0], _open_linux_external_url)
        self.assertIs(webbrowser.open, original_browser_open)
        _, url = webview.create_window.call_args.args[:2]
        self.assertEqual(url, "http://127.0.0.1:49152/")
        self.assertEqual(webview.create_window.call_args.kwargs["min_size"], (1000, 640))
        self.assertFalse(webview.create_window.call_args.kwargs["hidden"])
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

    def test_windows_exposes_desktop_settings_but_keeps_webview2_downloads(self) -> None:
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

        desktop_api = webview.create_window.call_args.kwargs["js_api"]
        self.assertIsInstance(desktop_api, DesktopApi)
        with patch(
            "spade65.desktop.gui_auto_start_status",
            return_value={
                "platform": "windows",
                "supported": True,
                "enabled": False,
                "current": False,
                "path": "C:/Startup/spade65-gui.cmd",
            },
        ):
            self.assertFalse(desktop_api.desktop_status()["native_export"])
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
