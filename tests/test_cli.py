import io
import json
import plistlib
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path, PureWindowsPath
from unittest.mock import patch

from spade65.cli import main
from spade65.device import Device, ReportShape
from spade65.protocol import SHORT_USAGE


class CliTests(unittest.TestCase):
    @staticmethod
    def _short_report_device() -> Device:
        return Device(
            path=Path("/dev/hidraw-test"),
            vendor_id=0x0603,
            product_id=0x0351,
            usages={SHORT_USAGE},
            reports=[ReportShape("feature", 8, 7 * 8)],
        )

    def test_gui_port_is_validated_before_socket_creation(self) -> None:
        for port in ("-1", "65536"):
            with self.subTest(port=port), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    main(["gui", "--port", port])
            self.assertEqual(raised.exception.code, 2)

    def test_cli_error_path_tolerates_a_windowed_process_without_stderr(self) -> None:
        with patch("spade65.cli.sys.stderr", None):
            self.assertEqual(main(["profile", "validate", "/missing-profile"]), 1)

    def test_gui_prefers_the_shared_desktop_coordinator(self) -> None:
        with patch("spade65.application.launch_gui") as launch_gui:
            self.assertEqual(main(["gui", "--port", "0"]), 0)
        launch_gui.assert_called_once_with(
            host="127.0.0.1", port=0, mode="desktop", start_hidden=False
        )

    def test_gui_can_force_browser_or_server_only_mode(self) -> None:
        with patch("spade65.application.launch_gui") as launch_gui:
            self.assertEqual(main(["gui", "--browser", "--port", "0"]), 0)
            self.assertEqual(main(["gui", "--no-browser", "--port", "0"]), 0)
        self.assertEqual(launch_gui.call_args_list[0].kwargs["mode"], "browser")
        self.assertEqual(launch_gui.call_args_list[1].kwargs["mode"], "server")

    def test_gui_can_start_hidden_for_login_startup(self) -> None:
        with patch("spade65.application.launch_gui") as launch_gui:
            self.assertEqual(main(["gui", "--start-hidden", "--port", "0"]), 0)
        launch_gui.assert_called_once_with(
            host="127.0.0.1", port=0, mode="desktop", start_hidden=True
        )

    def test_profile_create_validate_and_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profile.json"
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["profile", "create", str(profile)]), 0)
                self.assertEqual(main(["profile", "validate", str(profile)]), 0)
                self.assertEqual(
                    main(["profile", "apply", str(profile), "--dry-run"]), 0
                )
            data = json.loads(profile.read_text())
            self.assertEqual(data["format"], "spade65-profile-v1")
            self.assertIn("Profile template written to", output.getvalue())

    def test_generic_feature_write_rejects_short_transport_result(self) -> None:
        error = io.StringIO()
        output = io.StringIO()
        with (
            patch(
                "spade65.cli.discover_devices",
                return_value=[self._short_report_device()],
            ),
            patch("spade65.cli.send_feature_report", return_value=7),
            redirect_stdout(output),
            redirect_stderr(error),
        ):
            self.assertEqual(main(["debounce", "5", "--confirm"]), 1)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("short feature write: 7/8", error.getvalue())

    def test_generic_feature_write_reports_success_in_english(self) -> None:
        output = io.StringIO()
        with (
            patch(
                "spade65.cli.discover_devices",
                return_value=[self._short_report_device()],
            ),
            patch("spade65.cli.send_feature_report", return_value=8),
            redirect_stdout(output),
        ):
            self.assertEqual(main(["debounce", "5", "--confirm"]), 0)
        self.assertEqual(
            output.getvalue(),
            f"Sent to {self._short_report_device().path}; transport result=8.\n",
        )

    def test_probe_not_found_message_defaults_to_english(self) -> None:
        output = io.StringIO()
        with (
            patch("spade65.cli.discover_devices", return_value=[]),
            redirect_stdout(output),
        ):
            self.assertEqual(main(["probe"]), 2)
        self.assertEqual(
            output.getvalue(),
            "Spade65 not found (USB VID 0603 PID 0351/0352/0356 or the "
            "verified Linux Bluetooth descriptor).\n",
        )

    def test_profile_write_requires_double_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profile.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["profile", "create", str(profile)]), 0)
            error = io.StringIO()
            with redirect_stderr(error):
                self.assertEqual(
                    main(["profile", "apply", str(profile), "--confirm"]), 1
                )
            self.assertIn("--i-understand-profile-overwrite", error.getvalue())

    def test_stream_dry_run_builds_five_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profile.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["profile", "create", str(profile)]), 0)
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    main(["stream-rgb", str(profile), "--dry-run"]), 0
                )
            self.assertEqual(output.getvalue().count("report_id=0x06"), 5)

    def test_vendor_import_converts_apmode_export(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "APMode.json"
            output = root / "profile.json"
            source.write_text(json.dumps({
                "filename": "APMode",
                "value": {"Light_Export": [{
                    "name": "Static", "check": True,
                    "colors": ["#123456"],
                    "frame_selection_range": [True],
                }]},
            }))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(["vendor-import", str(source), str(output)]), 0
                )
            profile = json.loads(output.read_text())
            self.assertEqual(profile["settings"]["app_effects"][0]["mode"], "static")

    def test_cross_host_integration_requires_explicit_target_details(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "spade65-background.cmd"
            error = io.StringIO()
            with (
                patch(
                    "spade65.startup.platform_family",
                    side_effect=lambda value=None: "linux" if value is None else value,
                ),
                redirect_stderr(error),
            ):
                result = main(
                    [
                        "service",
                        "integration",
                        "local-background.json",
                        str(output),
                        "--platform",
                        "windows",
                    ]
                )
        self.assertEqual(result, 1)
        self.assertFalse(output.exists())
        self.assertIn("--target-config", error.getvalue())
        self.assertIn("--target-executable", error.getvalue())
        self.assertIn("--target-runtime", error.getvalue())

    def test_single_positional_binds_to_output_not_config(self) -> None:
        # config is nargs="?", so argparse backtracks and gives the lone
        # positional to output. The failure must then name the missing config.
        from spade65.cli import build_parser

        parsed = build_parser().parse_args(
            ["service", "integration", "launcher.cmd"]
        )
        self.assertIsNone(parsed.config)
        self.assertEqual(parsed.output, Path("launcher.cmd"))

        parsed = build_parser().parse_args(
            ["service", "integration", "config.json", "launcher.cmd"]
        )
        self.assertEqual(parsed.config, Path("config.json"))
        self.assertEqual(parsed.output, Path("launcher.cmd"))

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "launcher.cmd"
            error = io.StringIO()
            with redirect_stderr(error):
                result = main(["service", "integration", str(output)])
        self.assertEqual(result, 1)
        self.assertIn("--target-config", error.getvalue())
        self.assertFalse(output.exists())

    def test_linux_can_generate_deployable_packaged_windows_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "spade65-background.cmd"
            stdout = io.StringIO()
            with (
                patch(
                    "spade65.startup.platform_family",
                    side_effect=lambda value=None: "linux" if value is None else value,
                ),
                redirect_stdout(stdout),
            ):
                result = main(
                    [
                        "service",
                        "integration",
                        "local-background.json",
                        str(output),
                        "--platform",
                        "windows",
                        "--target-config",
                        "C:/Users/Alice/AppData/Roaming/Spade65/background.json",
                        "--target-executable",
                        "C:/Program Files/Spade65/Spade65.exe",
                        "--target-runtime",
                        "packaged",
                    ]
                )
            launcher = output.read_text(encoding="utf-8")
        self.assertEqual(result, 0)
        self.assertIn(r'"C:\Program Files\Spade65\Spade65.exe"', launcher)
        self.assertIn(
            r'"C:\Users\Alice\AppData\Roaming\Spade65\background.json"',
            launcher,
        )
        self.assertNotIn("-m spade65", launcher)
        # str(Path.cwd()) is POSIX-separated on this host while the launcher is
        # backslash-rendered, so that comparison could never fail. Assert on
        # both separator flavours of a value that would actually leak.
        for host in (str(Path.cwd()), str(Path(sys.executable).parent)):
            for flavour in (host, str(PureWindowsPath(host))):
                self.assertNotIn(flavour, launcher)
        self.assertIn("Background launcher written to", stdout.getvalue())

    def test_linux_can_generate_deployable_python_macos_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "com.spade65.background.plist"
            with patch(
                "spade65.startup.platform_family",
                side_effect=lambda value=None: "linux" if value is None else value,
            ):
                with redirect_stdout(io.StringIO()):
                    result = main(
                        [
                            "service",
                            "integration",
                            "local-background.json",
                            str(output),
                            "--platform",
                            "macos",
                            "--target-config",
                            "/Users/alice/Library/Application Support/Spade65/background.json",
                            "--target-executable",
                            "/usr/local/bin/python3",
                            "--target-runtime",
                            "python",
                        ]
                    )
            payload = plistlib.loads(output.read_bytes())
        self.assertEqual(result, 0)
        self.assertEqual(
            payload["ProgramArguments"],
            [
                "/usr/local/bin/python3",
                "-m",
                "spade65",
                "service",
                "run",
                "/Users/alice/Library/Application Support/Spade65/background.json",
            ],
        )


if __name__ == "__main__":
    unittest.main()
