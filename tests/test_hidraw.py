import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from spade65.device import (
    Device,
    ReportShape,
    choose_companion_feature_device,
    choose_device,
    parse_report_descriptor,
)
from spade65.protocol import SHORT_REPORT_ID, SHORT_REPORT_LENGTH, SHORT_USAGE

if sys.platform.startswith("linux"):
    from spade65.hidraw import (
        discover_hidraw,
        readonly_device_info,
        send_output_report,
    )


class HidrawTests(unittest.TestCase):
    @staticmethod
    def _short_device(
        path: str, *, unique: str = "", length: int = SHORT_REPORT_LENGTH
    ) -> Device:
        return Device(
            path=Path(path),
            vendor_id=0x0603,
            product_id=0x0351,
            unique=unique,
            usages={SHORT_USAGE},
            reports=[
                ReportShape(
                    "feature", SHORT_REPORT_ID, (length - 1) * 8
                )
            ],
        )

    def test_companion_selection_reuses_a_combined_collection(self) -> None:
        primary = self._short_device("/dev/hidraw-combined")
        selected = choose_companion_feature_device(
            [primary],
            primary=primary,
            usage=SHORT_USAGE,
            report_id=SHORT_REPORT_ID,
            report_length=SHORT_REPORT_LENGTH,
        )
        self.assertIs(selected, primary)

    def test_companion_selection_matches_a_separate_collection_by_serial(self) -> None:
        primary = Device(
            path=Path("/dev/hidraw-main"),
            vendor_id=0x0603,
            product_id=0x0351,
            unique="keyboard-a",
        )
        expected = self._short_device(
            "/dev/hidraw-short-a", unique="keyboard-a"
        )
        other = self._short_device(
            "/dev/hidraw-short-b", unique="keyboard-b"
        )
        selected = choose_companion_feature_device(
            [primary, expected, other],
            primary=primary,
            usage=SHORT_USAGE,
            report_id=SHORT_REPORT_ID,
            report_length=SHORT_REPORT_LENGTH,
        )
        self.assertIs(selected, expected)

    def test_companion_selection_refuses_ambiguous_or_wrong_shapes(self) -> None:
        primary = Device(
            path=Path("/dev/hidraw-main"),
            vendor_id=0x0603,
            product_id=0x0351,
        )
        candidates = [
            self._short_device("/dev/hidraw-short-a"),
            self._short_device("/dev/hidraw-short-b"),
        ]
        with self.assertRaisesRegex(RuntimeError, "multiple matching companion"):
            choose_companion_feature_device(
                [primary, *candidates],
                primary=primary,
                usage=SHORT_USAGE,
                report_id=SHORT_REPORT_ID,
                report_length=SHORT_REPORT_LENGTH,
            )
        with self.assertRaisesRegex(RuntimeError, "no matching companion"):
            choose_companion_feature_device(
                [primary, self._short_device("/dev/hidraw-short", length=7)],
                primary=primary,
                usage=SHORT_USAGE,
                report_id=SHORT_REPORT_ID,
                report_length=SHORT_REPORT_LENGTH,
            )
        with self.assertRaisesRegex(RuntimeError, "no matching companion"):
            choose_companion_feature_device(
                [
                    primary,
                    self._short_device(
                        "/dev/hidraw-other", unique="another-keyboard"
                    ),
                ],
                primary=primary,
                usage=SHORT_USAGE,
                report_id=SHORT_REPORT_ID,
                report_length=SHORT_REPORT_LENGTH,
            )

    def test_parses_vendor_usage_and_feature_length(self) -> None:
        descriptor = bytes.fromhex(
            "06 02 ff "  # Usage Page ff02
            "09 01 "  # Usage 0001
            "a1 01 "  # Application Collection
            "85 07 "  # Report ID 7
            "75 08 "  # Report Size 8
            "96 6b 02 "  # Report Count 619
            "b1 02 "  # Feature
            "c0"
        )
        usages, reports = parse_report_descriptor(descriptor)
        self.assertIn((0xFF02, 0x0001), usages)
        self.assertEqual(reports[0].kind, "feature")
        self.assertEqual(reports[0].report_id, 7)
        self.assertEqual(reports[0].byte_length, 620)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux hidraw backend")
    def test_discovers_a_synthetic_hidraw_device(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            device = root / "hidraw3" / "device"
            device.mkdir(parents=True)
            (device / "uevent").write_text(
                "HID_ID=0003:00000603:00000351\n"
                "HID_NAME=Noir SPADE65\n"
                "HID_UNIQ=test\n"
            )
            (device / "report_descriptor").write_bytes(
                bytes.fromhex("06 03 ff 09 01 a1 01 85 08 75 08 95 07 b1 02 c0")
            )
            devices = discover_hidraw(root)
            self.assertEqual(len(devices), 1)
            self.assertEqual(devices[0].path, Path("/dev/hidraw3"))
            self.assertEqual(devices[0].bus_type, 0x0003)
            self.assertEqual(devices[0].report_length("feature", 8), 8)
            selected = choose_device(
                devices,
                vendor_id=0x0603,
                product_ids={0x0351},
                usage=(0xFF03, 1),
            )
            self.assertEqual(selected.name, "Noir SPADE65")

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux sysfs metadata")
    def test_readonly_info_does_not_claim_usb_revision_is_firmware(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            usb = Path(directory) / "1-2"
            interface = usb / "1-2:1.2" / "0003:0603:0351.0001"
            interface.mkdir(parents=True)
            (usb / "idVendor").write_text("0603\n")
            (usb / "idProduct").write_text("0351\n")
            (usb / "bcdDevice").write_text("0100\n")
            info = readonly_device_info(Device(
                path=Path("/dev/hidraw4"), vendor_id=0x0603,
                product_id=0x0351, sysfs_path=interface,
            ))
            self.assertEqual(info["usb_revision"], "01.00")
            self.assertIsNone(info["firmware_version"])

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux hidraw backend")
    @patch("spade65.hidraw.os.close")
    @patch("spade65.hidraw.os.write", return_value=64)
    @patch("spade65.hidraw.os.open", return_value=12)
    def test_sends_output_report(self, open_mock, write_mock, close_mock) -> None:
        report = bytes((6, 1)) + bytes(62)
        self.assertEqual(send_output_report(Path("/dev/hidraw4"), report), 64)
        write_mock.assert_called_once_with(12, report)
        close_mock.assert_called_once_with(12)


if __name__ == "__main__":
    unittest.main()
