import unittest

from spade65.keymap import (
    BUTTON_TO_SLOT,
    UI_KEY_NAMES,
    VENDOR_UI_KEY_NAMES,
    compile_profile,
)
from spade65.vendor import KCODE_TO_USAGE, convert_vendor_document


class VendorImportTests(unittest.TestCase):
    def test_converts_combined_keyboard_macro_and_ap_export(self) -> None:
        normal = [{"keyAssignType": ["", "", ""], "value": ""} for _ in UI_KEY_NAMES]
        fn1 = [{"keyAssignType": ["", "", ""], "value": ""} for _ in UI_KEY_NAMES]
        fn2 = [{"keyAssignType": ["", "", ""], "value": ""} for _ in UI_KEY_NAMES]
        normal[UI_KEY_NAMES.index("q")] = {
            "keyAssignType": ["", "", "K153"], "value": "A"
        }
        normal[UI_KEY_NAMES.index("pageup")] = {
            "keyAssignType": ["", "", "KMacro"], "macroCode": 0,
        }
        document = {
            "filename": "0x06030x0351_Profile",
            "value": {
                "Keyboard_Export": {
                    "assignedKeyboardKeys": normal,
                    "assignedFnKeyboardKeys": [fn1, fn2],
                    "fnModeindex": 1,
                },
                "Macro_Export": {
                    "MacroFiletItem": [{
                        "IndexCode": 0, "name": "Test", "RepeatTime": 2,
                        "Data": [
                            {"byDelay": 10, "byKeyCode": "65", "bKeyDown": True},
                            {"byDelay": 30, "byKeyCode": "65", "bKeyDown": False},
                        ],
                    }]
                },
                "Light_Export": [{
                    "name": "ConicBand", "check": True,
                    "colors": ["#ff0000", "#00ff00"],
                    "frame_selection_range": [True] * len(UI_KEY_NAMES),
                    "ParameterNumberList": [
                        {"field": "speed", "setValue": 7},
                        {"field": "opacity", "setValue": 80},
                    ],
                    "ParameterBoolList": [{"field": "gradient", "setValue": True}],
                }],
            },
        }
        profile, imported = convert_vendor_document(document)
        self.assertEqual(imported, ["KeyAssign", "Macro", "APMode"])
        self.assertEqual(profile["layers"]["normal"]["q"], 0x04)
        self.assertEqual(profile["layers"]["normal"]["pageup"], {"macro": 0})
        self.assertEqual(profile["macros"][0]["events"][0]["delay_ms"], 20)
        self.assertEqual(profile["settings"]["app_effects"][0]["mode"], "conic")
        self.assertEqual(len(compile_profile(profile)["keymap"]), 620)

    def test_mapping_covers_every_unique_vendor_assignment_usage(self) -> None:
        self.assertEqual(len(set(KCODE_TO_USAGE.values())), 130)

    def test_variant_positions_import_to_distinct_canonical_modifiers(self) -> None:
        normal = [
            {"keyAssignType": ["", "", ""], "value": ""}
            for _ in VENDOR_UI_KEY_NAMES
        ]
        # Original exports are positional: raw index 62 is the legacy vendor
        # RAlt position and raw index 66 is the physical RALT-variant key.
        normal[62] = {"keyAssignType": ["", "", "K170"], "value": "B"}
        normal[66] = {"keyAssignType": ["", "", "K153"], "value": "A"}
        profile, imported = convert_vendor_document({
            "value": {"Keyboard_Export": {"assignedKeyboardKeys": normal}}
        })

        self.assertEqual(imported, ["KeyAssign"])
        self.assertEqual(profile["layers"]["normal"]["rctrl"], 0x05)
        self.assertEqual(profile["layers"]["normal"]["ralt"], 0x04)
        compiled = compile_profile(profile)["keymap"]
        self.assertEqual(BUTTON_TO_SLOT["rctrl"], 89)
        self.assertEqual(BUTTON_TO_SLOT["ralt"], 96)
        self.assertEqual(compiled[8 + 2 * 89 : 8 + 2 * 89 + 2], b"\x80\x05")
        self.assertEqual(compiled[8 + 2 * 96 : 8 + 2 * 96 + 2], b"\x80\x04")

    def test_ap_selection_uses_canonical_variant_positions(self) -> None:
        selected = [False] * len(VENDOR_UI_KEY_NAMES)
        selected[62] = True
        selected[66] = True
        profile, imported = convert_vendor_document({
            "value": {
                "Light_Export": [{
                    "name": "wave",
                    "frame_selection_range": selected,
                    "colors": ["#123456"],
                }]
            }
        })

        self.assertEqual(imported, ["APMode"])
        self.assertEqual(
            profile["settings"]["app_effects"][0]["keys"],
            ["rctrl", "ralt"],
        )

    def test_rejects_unrelated_json(self) -> None:
        with self.assertRaisesRegex(ValueError, "no Keyboard_Export"):
            convert_vendor_document({"value": {"unrelated": True}})


if __name__ == "__main__":
    unittest.main()
