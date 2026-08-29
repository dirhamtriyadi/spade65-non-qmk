import unittest

from spade65.keymap import UI_KEY_NAMES, compile_profile
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

    def test_rejects_unrelated_json(self) -> None:
        with self.assertRaisesRegex(ValueError, "no Keyboard_Export"):
            convert_vendor_document({"value": {"unrelated": True}})


if __name__ == "__main__":
    unittest.main()
