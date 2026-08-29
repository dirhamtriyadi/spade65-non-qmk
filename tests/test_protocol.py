import unittest

from spade65.protocol import (
    EFFECTS,
    KeyAssignment,
    MAIN_REPORT_LENGTH,
    SHORT_REPORT_LENGTH,
    debounce_report,
    keymap_report,
    reset_report,
    rgb_effect_report,
    sleep_report,
)


class ProtocolTests(unittest.TestCase):
    def test_rgb_effect_report(self) -> None:
        report = rgb_effect_report(
            "rainbow-wheel", brightness=3, speed=2, color_index=4
        )
        self.assertEqual(len(report), MAIN_REPORT_LENGTH)
        self.assertEqual(report[:3], bytes((0x07, 0x02, 0x01)))
        self.assertEqual(report[9:12], bytes((0x04, 0x03, 0x02)))
        self.assertEqual(report[12 : 12 + len(EFFECTS)], bytes((4,)) * len(EFFECTS))
        self.assertFalse(any(report[12 + len(EFFECTS) :]))

    def test_multicolor_is_palette_seven_except_fixed(self) -> None:
        rainbow = rgb_effect_report("rainbow-wheel", multicolor=True)
        fixed = rgb_effect_report("fixed", color_index=2, multicolor=True)
        self.assertEqual(rainbow[12 : 12 + len(EFFECTS)], bytes((7,)) * len(EFFECTS))
        self.assertEqual(fixed[12 : 12 + len(EFFECTS)], bytes((2,)) * len(EFFECTS))

    def test_debounce_report(self) -> None:
        report = debounce_report(5)
        self.assertEqual(len(report), SHORT_REPORT_LENGTH)
        self.assertEqual(report, bytes((0x08, 0x09, 0x05, 0, 0, 0, 0, 0)))

    def test_keymap_report_preserves_defaults_and_encodes_assignment(self) -> None:
        defaults = bytes(range(102))
        layers = [[None] * 102 for _ in range(3)]
        layers[1][17] = KeyAssignment(modifiers=0x03, usage=0x05)
        report = keymap_report(layers, default_usages=defaults, fn_mode_index=1)
        self.assertEqual(len(report), MAIN_REPORT_LENGTH)
        self.assertEqual(report[:3], bytes((0x07, 0x03, 0x02)))
        self.assertEqual(report[8:12], bytes((0, 0, 0, 1)))
        layer_one_offset = 8 + 2 * 102
        self.assertEqual(
            report[layer_one_offset + 34 : layer_one_offset + 36],
            bytes((0x83, 0x05)),
        )
        self.assertEqual(report[-2:], bytes((0, 101)))

    def test_keymap_report_validates_shape(self) -> None:
        with self.assertRaises(ValueError):
            keymap_report([[None] * 102], default_usages=bytes(102))
        with self.assertRaises(ValueError):
            KeyAssignment(modifiers=0x10, usage=4)

    def test_sleep_report_uses_one_based_indices(self) -> None:
        report = sleep_report(light_off_minutes=10, hibernate_minutes=30)
        self.assertEqual(report, bytes((0x08, 0x0B, 0x04, 0x07, 0, 0, 0, 0)))

    def test_reset_report(self) -> None:
        self.assertEqual(reset_report(), bytes((0x08, 0x08, 0, 0, 0, 0, 0, 0)))

    def test_protocol_ranges_are_checked(self) -> None:
        with self.assertRaises(ValueError):
            rgb_effect_report("fixed", brightness=5)
        with self.assertRaises(ValueError):
            debounce_report(0)
        with self.assertRaises(ValueError):
            sleep_report(light_off_minutes=3, hibernate_minutes=30)


if __name__ == "__main__":
    unittest.main()
