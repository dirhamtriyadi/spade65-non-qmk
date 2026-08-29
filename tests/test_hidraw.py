import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from spade65.hidraw import (
    choose_device,
    discover_hidraw,
    parse_report_descriptor,
    send_output_report,
)


class HidrawTests(unittest.TestCase):
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
            self.assertEqual(devices[0].report_length("feature", 8), 8)
            selected = choose_device(
                devices,
                vendor_id=0x0603,
                product_ids={0x0351},
                usage=(0xFF03, 1),
            )
            self.assertEqual(selected.name, "Noir SPADE65")

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
