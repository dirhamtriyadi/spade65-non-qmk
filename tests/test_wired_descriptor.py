import hashlib
import unittest

from spade65.device import parse_report_descriptor
from spade65.protocol import (
    MAIN_REPORT_ID,
    MAIN_REPORT_LENGTH,
    SHORT_REPORT_ID,
    SHORT_REPORT_LENGTH,
)

# Measured on the wired interface (0603:0351) after flashing the official
# Spade65_3M_20240325B(RALT) firmware on 8 September 2026.
#
# This is a record, not a gate. Wired devices are recognised by VID/PID, and
# other units may legitimately carry a different descriptor. Pinning what was
# measured makes a future firmware change visible instead of silent, which is
# what the Bluetooth descriptor already does for its own transport.
WIRED_DESCRIPTOR = bytes.fromhex(
    "05010906a101850275019508050795787501150025010507190029788102c0050c09"
    "01a101850319002a00041500260004950175108100c00601ff0901a1018504150026"
    "ff00093075089508810209319102c005010902a10185050901a10005091500250119"
    "01290575019505810295038101050116008026ff7f09300931751095028106158125"
    "7f0938750895018106050c0a380295018106c0c00655ff0a0202a10185067508953f"
    "150026ff000902810009029100c00602ff0901a1018507150025ff19012902750896"
    "6b02b102c00603ff0901a1018508150025ff1901290275089507b102c0"
)
WIRED_DESCRIPTOR_SHA256 = (
    "ca30078174971548b7a3c853a9f1472b7b04819bade4f45e6b9139af441ca7a8"
)


class WiredDescriptorTests(unittest.TestCase):
    def test_the_measurement_is_the_one_recorded(self) -> None:
        self.assertEqual(len(WIRED_DESCRIPTOR), 233)
        self.assertEqual(
            hashlib.sha256(WIRED_DESCRIPTOR).hexdigest(), WIRED_DESCRIPTOR_SHA256
        )

    def test_it_still_carries_the_reports_every_write_path_needs(self) -> None:
        # Losing any of these to a firmware update would break configuration
        # entirely, and the failure would otherwise appear only on Apply.
        _usages, reports = parse_report_descriptor(WIRED_DESCRIPTOR)
        shapes = {
            (report.kind, report.report_id): report.byte_length for report in reports
        }
        self.assertEqual(shapes[("feature", MAIN_REPORT_ID)], MAIN_REPORT_LENGTH)
        self.assertEqual(shapes[("feature", SHORT_REPORT_ID)], SHORT_REPORT_LENGTH)
        self.assertEqual(shapes[("output", 6)], 64)
        self.assertEqual(shapes[("input", 6)], 64)

    def test_it_still_advertises_the_configuration_usages(self) -> None:
        # ff02:0001 selects the interface writes target; ff03:0001 carries the
        # short report that activates streaming.
        usages, _reports = parse_report_descriptor(WIRED_DESCRIPTOR)
        self.assertIn((0xFF02, 0x0001), usages)
        self.assertIn((0xFF03, 0x0001), usages)


if __name__ == "__main__":
    unittest.main()
