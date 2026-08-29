import unittest

from spade65.keymap import (
    BUTTON_TO_SLOT,
    DEFAULT_USAGES,
    MATRIX_KEY_NAMES,
    UI_KEY_NAMES,
    USAGE_GROUPS,
    compile_profile,
    default_keymap_report,
    export_default,
    profile_template,
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

    def test_vendor_assignment_categories_are_named(self) -> None:
        profile = profile_template()
        profile["layers"]["normal"]["a"] = "play-pause"
        profile["layers"]["normal"]["b"] = "mouse-left"
        profile["layers"]["normal"]["c"] = "profile-next"
        profile["layers"]["normal"]["d"] = "disabled"
        compiled = compile_profile(profile)["keymap"]
        self.assertEqual(compiled[8 + 2 * BUTTON_TO_SLOT["a"] + 1], 0xA1)
        self.assertEqual(compiled[8 + 2 * BUTTON_TO_SLOT["b"] + 1], 0xB4)
        self.assertEqual(compiled[8 + 2 * BUTTON_TO_SLOT["c"] + 1], 0xB2)
        self.assertEqual(compiled[8 + 2 * BUTTON_TO_SLOT["d"] + 1], 0x00)
        self.assertIn("Media", USAGE_GROUPS)

    def test_compiles_complete_profile(self) -> None:
        profile = profile_template()
        profile["layers"]["normal"]["a"] = "b"
        profile["layers"]["fn1"]["esc"] = {"macro": 0}
        profile["macros"] = [
            {
                "index": 0,
                "repeat": 1,
                "events": [
                    {"delay_ms": 20, "usage": "a", "pressed": True},
                    {"delay_ms": 20, "usage": "a", "pressed": False},
                ],
            }
        ]
        profile["colors"] = {"esc": "#123456"}
        compiled = compile_profile(profile)
        self.assertEqual(len(compiled["keymap"]), 620)
        self.assertEqual(len(compiled["macros"]), 1)
        self.assertEqual(compiled["matrix_colors"][17], (0x12, 0x34, 0x56))

    def test_rejects_reference_to_undefined_macro(self) -> None:
        profile = profile_template()
        profile["layers"]["normal"]["a"] = {"macro": 4}
        with self.assertRaisesRegex(ValueError, "undefined macros"):
            compile_profile(profile)


if __name__ == "__main__":
    unittest.main()
