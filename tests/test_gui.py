import unittest
from unittest.mock import patch

from spade65.gui import (
    SAFE_ACTIONS,
    _send_features,
    execute_action,
    gui_metadata,
)
from spade65.device import Device, ReportShape
from spade65.keymap import profile_template


class GuiTests(unittest.TestCase):
    def test_metadata_exposes_safe_scope_and_no_firmware(self) -> None:
        with patch("spade65.gui.discover_devices", return_value=[]):
            metadata = gui_metadata()
        self.assertFalse(metadata["firmware_update"])
        self.assertEqual(set(metadata["safe_actions"]), set(SAFE_ACTIONS))
        self.assertNotIn("firmware", metadata["safe_actions"])
        self.assertIn("Mouse", metadata["usage_groups"])
        self.assertIn("mouse-left", metadata["usage_groups"]["Mouse"])

    def test_validate_compiles_without_device_write(self) -> None:
        result = execute_action("validate", {"profile": profile_template()})
        self.assertEqual(result["keymap_bytes"], 620)

    def test_unknown_and_firmware_actions_are_rejected(self) -> None:
        for action in ("firmware", "flash", "bootloader", "raw-write"):
            with self.subTest(action=action), self.assertRaises(ValueError):
                execute_action(action, {})

    def test_reset_requires_exact_confirmation_before_discovery(self) -> None:
        with patch("spade65.gui.discover_devices") as discover:
            with self.assertRaisesRegex(RuntimeError, "RESET SPADE65"):
                execute_action("reset", {"confirmation": "yes"})
        discover.assert_not_called()

    def test_profile_requires_exact_confirmation_before_discovery(self) -> None:
        with patch("spade65.gui.discover_devices") as discover:
            with self.assertRaisesRegex(RuntimeError, "APPLY PROFILE"):
                execute_action("profile", {"profile": profile_template()})
        discover.assert_not_called()

    def test_every_feature_write_is_descriptor_gated(self) -> None:
        device = Device(
            path="/dev/hidraw-test",  # type: ignore[arg-type]
            vendor_id=0x0603,
            product_id=0x0351,
            reports=[ReportShape("feature", 7, 619 * 8)],
        )
        with patch("spade65.gui.send_feature_report") as send:
            with self.assertRaisesRegex(RuntimeError, "report 0x08 mismatch"):
                _send_features(device, [bytes([8]) + bytes(7)])
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
