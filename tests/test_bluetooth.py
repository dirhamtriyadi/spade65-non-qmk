import hashlib
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from spade65.cli import main
from spade65.device import HID_BUS_BLUETOOTH, Device, parse_report_descriptor
from spade65.gui import execute_action, gui_metadata
from spade65.keymap import profile_template
from spade65.transport import (
    BLUETOOTH_DESCRIPTOR_SHA256,
    BLUETOOTH_TRANSPORT,
    device_configuration_status,
    is_observed_bluetooth,
    is_observed_device,
    observed_transport,
)

if sys.platform.startswith("linux"):
    from spade65.hidraw import _BLUEZ_BATTERY_CACHE, readonly_device_info


BLUETOOTH_DESCRIPTOR = bytes.fromhex(
    "05010906a1018501050719e029e71500250175019508810295017508810395057501"
    "050819012905910295017503910395067508150025ff0507190029658100c005010906"
    "a101850275019508050795787501150025010507190029788102c0050c0901a1018503"
    "19002a00041500260004950175108100c005010980a101850405011981298315002501"
    "950375018102950175058101c005010902a10185050901a10005091500250119012905"
    "75019505810295038101050116008026ff7f093009317510950281061581257f093875"
    "0895018106050c0a380295018106c0c00655ff0a0202a10185067508953f150026ff00"
    "0902810009029100c0"
)


def measured_bluetooth() -> Device:
    usages, reports = parse_report_descriptor(BLUETOOTH_DESCRIPTOR)
    return Device(
        path=Path("/dev/hidraw-bluetooth"),
        vendor_id=0,
        product_id=0,
        bus_type=HID_BUS_BLUETOOTH,
        name="Spade65",
        unique="AA:BB:CC:DD:EE:FF",
        usages=usages,
        reports=reports,
        descriptor=BLUETOOTH_DESCRIPTOR,
    )


class BluetoothTests(unittest.TestCase):
    def test_measured_descriptor_is_recognized_read_only(self) -> None:
        device = measured_bluetooth()
        self.assertEqual(len(device.descriptor), 253)
        self.assertEqual(
            hashlib.sha256(device.descriptor).hexdigest(),
            BLUETOOTH_DESCRIPTOR_SHA256,
        )
        self.assertTrue(is_observed_bluetooth(device))
        self.assertTrue(is_observed_device(device))
        self.assertEqual(observed_transport(device), BLUETOOTH_TRANSPORT)
        self.assertEqual(
            device_configuration_status(device), "unsupported-read-only"
        )
        self.assertFalse(any(report.kind == "feature" for report in device.reports))
        self.assertEqual(device.report_length("output", 6), 64)

    def test_generic_bluetooth_devices_do_not_match(self) -> None:
        device = measured_bluetooth()
        near_matches = (
            replace(device, name="Generic Keyboard"),
            replace(device, bus_type=0x0003),
            replace(device, descriptor=device.descriptor + b"\x00"),
            replace(device, backend="hidapi"),
        )
        for candidate in near_matches:
            with self.subTest(candidate=candidate):
                self.assertFalse(is_observed_bluetooth(candidate))
                self.assertFalse(is_observed_device(candidate))

    def test_cli_and_gui_report_bluetooth_without_exposing_it_to_writes(self) -> None:
        device = measured_bluetooth()
        with (
            patch("spade65.gui.discover_devices", return_value=[device]),
            patch(
                "spade65.gui.readonly_device_info",
                return_value={
                    "battery_percent": 87,
                    "battery_source": "BlueZ Battery1",
                },
            ),
        ):
            summary = gui_metadata()["devices"][0]
        self.assertEqual(summary["bus"], "0005")
        self.assertEqual(summary["vid"], "0000")
        self.assertEqual(summary["pid"], "0000")
        self.assertEqual(summary["transport"], "Bluetooth LE")
        self.assertEqual(summary["configuration_status"], "unsupported-read-only")
        self.assertEqual(summary["readonly"]["battery_percent"], 87)

        output = io.StringIO()
        with (
            patch("spade65.cli.discover_devices", return_value=[device]),
            redirect_stdout(output),
        ):
            self.assertEqual(main(["probe", "--json"]), 0)
        probe = json.loads(output.getvalue())[0]
        self.assertEqual(probe["transport"], "Bluetooth LE")
        self.assertEqual(probe["configuration_status"], "unsupported-read-only")
        self.assertNotIn("unique", probe)

        with (
            patch("spade65.gui.discover_devices", return_value=[device]),
            patch("spade65.gui.send_feature_report") as feature_write,
            patch("spade65.gui.send_output_report") as output_write,
        ):
            with self.assertRaisesRegex(RuntimeError, "no matching HID interface"):
                execute_action("stream", {"profile": profile_template()})
        feature_write.assert_not_called()
        output_write.assert_not_called()

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux BlueZ metadata")
    def test_battery_comes_from_bluez_and_is_cached(self) -> None:
        device = measured_bluetooth()
        completed = SimpleNamespace(
            returncode=0,
            stdout="\tBattery Percentage: 0x57 (87)\n",
        )
        with (
            patch.dict(_BLUEZ_BATTERY_CACHE, {}, clear=True),
            patch(
                "spade65.hidraw.shutil.which",
                return_value="/usr/bin/bluetoothctl",
            ),
            patch("spade65.hidraw.subprocess.run", return_value=completed) as run,
        ):
            first = readonly_device_info(device)
            second = readonly_device_info(device)
        self.assertEqual(first["battery_percent"], 87)
        self.assertEqual(first["battery_source"], "BlueZ Battery1")
        self.assertEqual(first["battery_status"], "reported by BlueZ Battery1")
        self.assertEqual(second["battery_percent"], 87)
        run.assert_called_once()
        self.assertEqual(
            run.call_args.args[0],
            ["/usr/bin/bluetoothctl", "--timeout", "2", "info", device.unique],
        )


if __name__ == "__main__":
    unittest.main()
