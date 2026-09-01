import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from spade65.device import Device, ReportShape
from spade65.profile_apply import send_profile_transaction
from spade65.transport import (
    backend_name,
    discover_hidapi,
    feature_report_session,
    readonly_device_info,
    send_feature_report,
    send_output_report,
)


MAIN_DESCRIPTOR = bytes.fromhex(
    "06 02 ff 09 01 a1 01 85 07 75 08 96 6b 02 b1 02 c0"
)


class FakeHandle:
    def __init__(self, descriptor=MAIN_DESCRIPTOR, *, open_error=None):
        self.descriptor = descriptor
        self.open_error = open_error
        self.opened = None
        self.feature = None
        self.features = []
        self.output = None
        self.closed = False

    def open_path(self, path):
        self.opened = path
        if self.open_error is not None:
            raise self.open_error

    def get_report_descriptor(self):
        return list(self.descriptor)

    def send_feature_report(self, report):
        self.feature = bytes(report)
        self.features.append(self.feature)
        return len(report)

    def write(self, report):
        self.output = bytes(report)
        return len(report)

    def close(self):
        self.closed = True


class FakeHid:
    def __init__(self, *, fail_open_indexes=()):
        self.handles = []
        self.fail_open_indexes = set(fail_open_indexes)

    def enumerate(self, vendor_id, product_id):
        self.enumerated = (vendor_id, product_id)
        return [{
            "path": b"spade-main", "vendor_id": 0x0603,
            "product_id": 0x0351, "product_string": "JP Spade65",
            "serial_number": "test", "usage_page": 0xFF02,
            "usage": 1, "release_number": 0x0100,
            "manufacturer_string": "Noir", "interface_number": 2,
        }]

    def device(self):
        index = len(self.handles)
        error = OSError("open failed") if index in self.fail_open_indexes else None
        handle = FakeHandle(open_error=error)
        self.handles.append(handle)
        return handle


class TransportTests(unittest.TestCase):
    def test_backend_selection_is_native_on_linux_and_hidapi_elsewhere(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(backend_name("linux"), "hidraw")
            self.assertEqual(backend_name("win32"), "hidapi")
            self.assertEqual(backend_name("darwin"), "hidapi")

    def test_hidapi_discovery_parses_real_report_descriptor(self):
        hid = FakeHid()
        devices = discover_hidapi(hid)  # type: ignore[arg-type]
        self.assertEqual(hid.enumerated, (0x0603, 0))
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].backend, "hidapi")
        self.assertEqual(devices[0].report_length("feature", 7), 620)
        self.assertIn((0xFF02, 1), devices[0].usages)
        self.assertEqual(readonly_device_info(devices[0])["usb_revision"], "01.00")

    def test_hidapi_feature_and_output_writes_use_opened_collection(self):
        hid = FakeHid()
        device = Device(
            path=Path("spade-main"), vendor_id=0x0603, product_id=0x0351,
            backend="hidapi", hidapi_path=b"spade-main",
            reports=[ReportShape("feature", 8, 7 * 8), ReportShape("output", 6, 63 * 8)],
        )
        with patch("spade65.transport._load_hidapi", return_value=hid):
            self.assertEqual(send_feature_report(device, bytes([8]) + bytes(7)), 8)
            self.assertEqual(send_output_report(device, bytes([6]) + bytes(63)), 64)
        self.assertEqual(hid.handles[0].feature, bytes([8]) + bytes(7))
        self.assertEqual(hid.handles[1].output, bytes([6]) + bytes(63))
        self.assertTrue(all(handle.closed for handle in hid.handles))

    def test_hidapi_feature_session_reuses_one_handle_for_multiple_reports(self):
        hid = FakeHid()
        device = Device(
            path=Path("spade-main"),
            vendor_id=0x0603,
            product_id=0x0351,
            backend="hidapi",
            hidapi_path=b"spade-main",
        )
        reports = (bytes((8, 1)) + bytes(6), bytes((8, 9, 5)) + bytes(5))

        with patch("spade65.transport._load_hidapi", return_value=hid):
            with feature_report_session(device) as send:
                self.assertEqual(send(reports[0]), 8)
                self.assertEqual(send(reports[1]), 8)
                self.assertEqual(len(hid.handles), 1)
                self.assertFalse(hid.handles[0].closed)

        self.assertEqual(hid.handles[0].features, list(reports))
        self.assertTrue(hid.handles[0].closed)

    def test_second_hidapi_session_open_failure_closes_both_without_writes(self):
        hid = FakeHid(fail_open_indexes={1})
        main = Device(
            path=Path("spade-main"),
            vendor_id=0x0603,
            product_id=0x0351,
            backend="hidapi",
            hidapi_path=b"spade-main",
            reports=[ReportShape("feature", 7, 619 * 8)],
        )
        short = Device(
            path=Path("spade-short"),
            vendor_id=0x0603,
            product_id=0x0351,
            backend="hidapi",
            hidapi_path=b"spade-short",
            reports=[ReportShape("feature", 8, 7 * 8)],
        )
        keymap = bytes((7, 3)) + bytes(618)
        debounce = bytes((8, 9, 5)) + bytes(5)

        with patch("spade65.transport._load_hidapi", return_value=hid):
            with self.assertRaisesRegex(OSError, "open failed"):
                send_profile_transaction(
                    main,
                    short,
                    [keymap],
                    debounce,
                    feature_session=feature_report_session,
                    sleep=lambda _seconds: None,
                )

        self.assertEqual(len(hid.handles), 2)
        self.assertTrue(all(handle.closed for handle in hid.handles))
        self.assertEqual([handle.features for handle in hid.handles], [[], []])


if __name__ == "__main__":
    unittest.main()
