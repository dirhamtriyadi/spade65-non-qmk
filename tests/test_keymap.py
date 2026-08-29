import unittest

from spade65.keymap import (
    BUTTON_TO_SLOT,
    DEFAULT_USAGES,
    MATRIX_KEY_NAMES,
    UI_KEY_NAMES,
    default_keymap_report,
    export_default,
)


class KeymapTests(unittest.TestCase):
    def test_wired_matrix_shape_and_known_slots(self) -> None:
        self.assertEqual(len(MATRIX_KEY_NAMES), 102)
        self.assertEqual(len(DEFAULT_USAGES), 102)
        self.assertEqual(len(UI_KEY_NAMES), 70)
        self.assertEqual(BUTTON_TO_SLOT["esc"], 17)
        self.assertEqual(BUTTON_TO_SLOT["a"], 52)
        self.assertEqual(BUTTON_TO_SLOT["fn"], 95)
        self.assertEqual(DEFAULT_USAGES[52], 0x04)

    def test_default_frame_contains_three_complete_layers(self) -> None:
        report = default_keymap_report()
        self.assertEqual(report[:3], bytes((0x07, 0x03, 0x01)))
        expected_layer = b"".join(bytes((0, usage)) for usage in DEFAULT_USAGES)
        self.assertEqual(report[8 : 8 + 204], expected_layer)
        self.assertEqual(report[8 + 204 : 8 + 408], expected_layer)
        self.assertEqual(report[8 + 408 :], expected_layer)

    def test_export_is_json_serializable_shape(self) -> None:
        exported = export_default()
        self.assertEqual(exported["device"], "0603:0351")
        self.assertEqual(len(exported["matrix"]), 102)
        self.assertEqual(exported["report"]["length"], 620)


if __name__ == "__main__":
    unittest.main()
