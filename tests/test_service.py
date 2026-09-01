import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from spade65.device import Device, ReportShape
from spade65.keymap import profile_template
from spade65.protocol import (
    MAIN_REPORT_ID,
    MAIN_REPORT_LENGTH,
    MAIN_USAGE,
    SHORT_REPORT_ID,
    SHORT_REPORT_LENGTH,
    SHORT_USAGE,
    VENDOR_ID,
    debounce_report,
)
from spade65.service import (
    BackgroundService,
    active_process_name,
    apply_profile,
    load_service_config,
    matching_rule,
    service_template,
)
from tests.session_support import FeatureSessionRecorder


def _profile_interfaces() -> list[Device]:
    return [
        Device(
            path=Path("/dev/hidraw-main"),
            vendor_id=VENDOR_ID,
            product_id=0x0351,
            usages={MAIN_USAGE},
            reports=[
                ReportShape(
                    "feature", MAIN_REPORT_ID, (MAIN_REPORT_LENGTH - 1) * 8
                )
            ],
        ),
        Device(
            path=Path("/dev/hidraw-short"),
            vendor_id=VENDOR_ID,
            product_id=0x0351,
            usages={SHORT_USAGE},
            reports=[
                ReportShape(
                    "feature", SHORT_REPORT_ID, (SHORT_REPORT_LENGTH - 1) * 8
                )
            ],
        ),
    ]


class ServiceTests(unittest.TestCase):
    def test_config_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "service.json"
            path.write_text(json.dumps(service_template()))
            self.assertEqual(load_service_config(path)["format"], "spade65-service-v1")

    def test_background_timeline_streams_without_profile_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = profile_template()
            profile["settings"]["custom_timeline"] = {
                "frames": [{"duration_ms": 100, "colors": {"esc": "#ff0000"}}]
            }
            (root / "profile.json").write_text(json.dumps(profile))
            config = service_template()
            config["background_profile"] = "profile.json"
            config["associations"] = []
            (root / "service.json").write_text(json.dumps(config))
            with patch("spade65.service.stream_colors") as stream:
                status = BackgroundService(root / "service.json", clock=lambda: 1).step()
            self.assertEqual(status, "timeline:profile.json")
            stream.assert_called_once_with({"esc": "#ff0000"}, path=None)

    @patch("spade65.service.active_process_name", return_value="firefox")
    def test_x11_foreground_process_selects_profile(self, active) -> None:
        config = service_template()
        config["associations"] = [
            {"process": "/usr/bin/firefox", "profile": "browser.json"},
            {"process": "code", "profile": "editor.json"},
        ]
        self.assertEqual(matching_rule(config)["profile"], "browser.json")

    @patch("spade65.service.active_process_name", return_value="FIREFOX.EXE")
    def test_windows_executable_suffix_is_normalized(self, active) -> None:
        config = service_template()
        config["associations"] = [
            {"process": r"C:\\Program Files\\Mozilla Firefox\\firefox.exe",
             "profile": "browser.json"},
        ]
        self.assertEqual(matching_rule(config)["profile"], "browser.json")

    def test_foreground_process_dispatches_for_windows_and_macos(self) -> None:
        with patch(
            "spade65.service._active_process_windows", return_value="code.exe"
        ) as windows:
            self.assertEqual(active_process_name("win32"), "code.exe")
            windows.assert_called_once_with()
        with patch(
            "spade65.service._active_process_macos", return_value="Safari"
        ) as macos:
            self.assertEqual(active_process_name("darwin"), "Safari")
            macos.assert_called_once_with()

    @patch("spade65.service.running_process_names", return_value={"code"})
    @patch("spade65.service.active_process_name", return_value=None)
    def test_wayland_running_process_fallback_selects_profile(self, active, running) -> None:
        config = service_template()
        config["associations"] = [
            {"process": "firefox", "profile": "browser.json"},
            {"process": "/usr/bin/code", "profile": "editor.json"},
        ]
        self.assertEqual(matching_rule(config)["profile"], "editor.json")

    def test_profile_writes_need_runtime_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "profile.json").write_text(json.dumps(profile_template()))
            config = service_template()
            config.update({
                "background_profile": "profile.json", "associations": [],
                "allow_profile_writes": True,
            })
            (root / "service.json").write_text(json.dumps(config))
            with self.assertRaisesRegex(RuntimeError, "--allow-profile-writes"):
                BackgroundService(root / "service.json").step()

    def test_background_profile_sends_debounce_after_main_reports(self) -> None:
        interfaces = _profile_interfaces()
        sessions = FeatureSessionRecorder()
        with (
            patch("spade65.service.discover_devices", return_value=interfaces),
            patch(
                "spade65.service.feature_report_session", new=sessions.session
            ),
            patch("spade65.service.time.sleep"),
        ):
            apply_profile(profile_template())

        self.assertEqual(
            [
                (device.path, report[0], report[1])
                for device, report in sessions.calls
            ],
            [
                (interfaces[0].path, MAIN_REPORT_ID, 0x03),
                (interfaces[0].path, MAIN_REPORT_ID, 0x02),
                (interfaces[1].path, SHORT_REPORT_ID, 0x09),
            ],
        )
        self.assertEqual(sessions.calls[-1][1], debounce_report(5))
        self.assertEqual(
            [device.path for device in sessions.opened],
            [interfaces[0].path, interfaces[1].path],
        )

    def test_background_profile_rejects_invalid_debounce_before_discovery(self) -> None:
        profile = profile_template()
        profile["settings"]["debounce_ms"] = 256
        with (
            patch("spade65.service.discover_devices") as discover,
            patch("spade65.service.feature_report_session") as session,
        ):
            with self.assertRaisesRegex(ValueError, "debounce"):
                apply_profile(profile)
        discover.assert_not_called()
        session.assert_not_called()


if __name__ == "__main__":
    unittest.main()
