"""Every HID write path must abort when the transport moves too few bytes.

The keyboard offers no configuration readback, so a partial multi-report write
leaves the device in a state the operator cannot inspect. Each path therefore
has to raise, and the message has to identify which report stopped.
"""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from spade65.cli import main
from spade65.device import Device, ReportShape
from spade65.gui import execute_action
from spade65.keymap import profile_template
from spade65.protocol import (
    MAIN_REPORT_ID,
    MAIN_REPORT_LENGTH,
    MAIN_USAGE,
    OUTPUT_USAGE,
    SHORT_REPORT_ID,
    SHORT_REPORT_LENGTH,
    SHORT_USAGE,
    VENDOR_ID,
)
from spade65.service import apply_profile, stream_colors


def _short(_device: object, report: bytes) -> int:
    """Report one byte fewer than the caller handed to the transport."""

    return len(report) - 1


def _full(_device: object, report: bytes) -> int:
    """Report a complete write."""

    return len(report)


def _main_device() -> Device:
    return Device(
        path=Path("/dev/hidraw-main"),
        vendor_id=VENDOR_ID,
        product_id=0x0351,
        usages={MAIN_USAGE},
        reports=[ReportShape("feature", MAIN_REPORT_ID, (MAIN_REPORT_LENGTH - 1) * 8)],
    )


def _stream_device() -> Device:
    return Device(
        path=Path("/dev/hidraw-stream"),
        vendor_id=VENDOR_ID,
        product_id=0x0351,
        usages={OUTPUT_USAGE, SHORT_USAGE},
        reports=[
            ReportShape("feature", SHORT_REPORT_ID, (SHORT_REPORT_LENGTH - 1) * 8),
            ReportShape("output", 0x06, 63 * 8),
        ],
    )


def _short_feature_device() -> Device:
    return Device(
        path=Path("/dev/hidraw-short"),
        vendor_id=VENDOR_ID,
        product_id=0x0351,
        usages={SHORT_USAGE},
        reports=[ReportShape("feature", SHORT_REPORT_ID, (SHORT_REPORT_LENGTH - 1) * 8)],
    )


def _colors() -> dict[str, str]:
    return {"esc": "#ff0000"}


def _multi_report_profile() -> dict[str, object]:
    """A profile that compiles to several 620-byte reports."""

    profile = profile_template()
    profile["macros"] = [
        {
            "index": index,
            "repeat": 1,
            "events": [
                {"delay_ms": 20, "usage": "a", "pressed": True},
                {"delay_ms": 20, "usage": "a", "pressed": False},
            ],
        }
        for index in range(3)
    ]
    profile["colors"] = _colors()
    return profile


def _fail_on(index: int):
    """Short-write the report at ``index``; every other write is complete."""

    calls = {"n": 0}

    def send(_device: object, report: bytes) -> int:
        current = calls["n"]
        calls["n"] += 1
        return len(report) - 1 if current == index else len(report)

    return send


class ShortFeatureWriteTests(unittest.TestCase):
    """Single-report feature writes."""

    def test_cli_generic_feature_write_aborts(self) -> None:
        error = io.StringIO()
        with (
            patch("spade65.cli.discover_devices", return_value=[_short_feature_device()]),
            patch("spade65.cli.send_feature_report", side_effect=_short),
            redirect_stdout(io.StringIO()),
            redirect_stderr(error),
        ):
            self.assertEqual(main(["debounce", "5", "--confirm"]), 1)
        self.assertIn("short feature write: 7/8", error.getvalue())

    def test_gui_single_feature_write_aborts(self) -> None:
        with (
            patch("spade65.gui.discover_devices", return_value=[_short_feature_device()]),
            patch("spade65.gui.send_feature_report", side_effect=_short) as send,
        ):
            with self.assertRaisesRegex(RuntimeError, r"report 1/1 .*: 7/8"):
                execute_action("debounce", {"milliseconds": 5})
        self.assertEqual(send.call_count, 1)


class ShortProfileWriteTests(unittest.TestCase):
    """Multi-report sequences must name the report that failed and stop there."""

    def test_cli_profile_apply_aborts_and_names_the_failing_report(self) -> None:
        # Fail on the third of several reports so the index in the message is
        # load-bearing and the abort cannot be confused with "wrote them all".
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(
                json.dumps(_multi_report_profile()), encoding="utf-8"
            )
            error = io.StringIO()
            with (
                patch("spade65.cli.discover_devices", return_value=[_main_device()]),
                patch(
                    "spade65.cli.send_feature_report", side_effect=_fail_on(2)
                ) as send,
                redirect_stdout(io.StringIO()),
                redirect_stderr(error),
            ):
                self.assertEqual(
                    main(
                        [
                            "profile",
                            "apply",
                            str(path),
                            "--confirm",
                            "--i-understand-profile-overwrite",
                        ]
                    ),
                    1,
                )
        message = error.getvalue()
        self.assertRegex(message, r"short feature write on report 3/[2-9]\d*")
        self.assertIn("opcode 0x05", message)
        self.assertIn("619/620", message)
        # Stopped at the failure instead of writing the rest of the sequence.
        self.assertEqual(send.call_count, 3)

    def test_cli_per_key_rgb_aborts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            profile = profile_template()
            profile["colors"] = _colors()
            path.write_text(json.dumps(profile), encoding="utf-8")
            error = io.StringIO()
            with (
                patch("spade65.cli.discover_devices", return_value=[_main_device()]),
                patch("spade65.cli.send_feature_report", side_effect=_short),
                redirect_stdout(io.StringIO()),
                redirect_stderr(error),
            ):
                self.assertEqual(
                    main(["per-key-rgb", str(path), "--confirm"]), 1
                )
        self.assertIn("short feature write on report 1/", error.getvalue())

    def test_gui_profile_write_aborts_and_names_the_failing_report(self) -> None:
        with (
            patch("spade65.gui.discover_devices", return_value=[_main_device()]),
            patch(
                "spade65.gui.send_feature_report", side_effect=_fail_on(1)
            ) as send,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                r"short feature write on report 2/[2-9]\d* "
                r"\(id 0x07 opcode 0x05\): 619/620",
            ):
                execute_action(
                    "profile",
                    {
                        "profile": _multi_report_profile(),
                        "confirmation": "APPLY PROFILE",
                        "scopes": ["keymap", "macros", "colors"],
                    },
                )
        self.assertEqual(send.call_count, 2)

    def test_service_background_profile_write_aborts(self) -> None:
        with (
            patch("spade65.service.discover_devices", return_value=[_main_device()]),
            patch(
                "spade65.service.send_feature_report", side_effect=_fail_on(1)
            ) as send,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                r"short background profile write on report 2/[2-9]\d* "
                r"\(id 0x07 opcode 0x05\): 619/620",
            ):
                apply_profile(_multi_report_profile())
        self.assertEqual(send.call_count, 2)


class ShortStreamingWriteTests(unittest.TestCase):
    """Streaming activation and each of the five output chunks."""

    def test_cli_stream_activation_aborts_with_byte_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            profile = profile_template()
            profile["colors"] = _colors()
            path.write_text(json.dumps(profile), encoding="utf-8")
            error = io.StringIO()
            with (
                patch("spade65.cli.discover_devices", return_value=[_stream_device()]),
                patch("spade65.cli.send_feature_report", side_effect=_short),
                patch("spade65.cli.send_output_report", side_effect=_full) as output,
                redirect_stdout(io.StringIO()),
                redirect_stderr(error),
            ):
                self.assertEqual(
                    main(["stream-rgb", str(path), "--confirm"]), 1
                )
        self.assertIn("short streaming activation: 7/8", error.getvalue())
        output.assert_not_called()

    def test_cli_stream_output_aborts_on_the_third_chunk(self) -> None:
        results = [64, 64, 63, 64, 64]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            profile = profile_template()
            profile["colors"] = _colors()
            path.write_text(json.dumps(profile), encoding="utf-8")
            error = io.StringIO()
            with (
                patch("spade65.cli.discover_devices", return_value=[_stream_device()]),
                patch("spade65.cli.send_feature_report", side_effect=_full),
                patch(
                    "spade65.cli.send_output_report", side_effect=results
                ) as output,
                redirect_stdout(io.StringIO()),
                redirect_stderr(error),
            ):
                self.assertEqual(
                    main(["stream-rgb", str(path), "--confirm"]), 1
                )
        self.assertIn("short streaming output chunk 3/5: 63/64", error.getvalue())
        self.assertEqual(output.call_count, 3)

    def test_gui_stream_activation_aborts_with_byte_counts(self) -> None:
        profile = profile_template()
        profile["colors"] = _colors()
        with (
            patch("spade65.gui.discover_devices", return_value=[_stream_device()]),
            patch("spade65.gui.send_feature_report", side_effect=_short),
            patch("spade65.gui.send_output_report", side_effect=_full) as output,
        ):
            with self.assertRaisesRegex(RuntimeError, "short streaming activation: 7/8"):
                execute_action("stream", {"profile": profile})
        output.assert_not_called()

    def test_gui_stream_output_aborts_on_the_second_chunk(self) -> None:
        profile = profile_template()
        profile["colors"] = _colors()
        with (
            patch("spade65.gui.discover_devices", return_value=[_stream_device()]),
            patch("spade65.gui.send_feature_report", side_effect=_full),
            patch(
                "spade65.gui.send_output_report", side_effect=[64, 63, 64, 64, 64]
            ) as output,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "short streaming output chunk 2/5: 63/64"
            ):
                execute_action("stream", {"profile": profile})
        self.assertEqual(output.call_count, 2)

    def test_service_stream_activation_aborts_with_byte_counts(self) -> None:
        with (
            patch("spade65.service.discover_devices", return_value=[_stream_device()]),
            patch("spade65.service.send_feature_report", side_effect=_short),
            patch("spade65.service.send_output_report", side_effect=_full) as output,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "short background streaming activation: 7/8"
            ):
                stream_colors(_colors())
        output.assert_not_called()

    def test_service_stream_output_aborts_on_the_fourth_chunk(self) -> None:
        with (
            patch("spade65.service.discover_devices", return_value=[_stream_device()]),
            patch("spade65.service.send_feature_report", side_effect=_full),
            patch(
                "spade65.service.send_output_report", side_effect=[64, 64, 64, 63, 64]
            ) as output,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "short background streaming output chunk 4/5: 63/64"
            ):
                stream_colors(_colors())
        self.assertEqual(output.call_count, 4)


if __name__ == "__main__":
    unittest.main()
