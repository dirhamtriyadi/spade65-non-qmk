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
                    "debounceTime": 7,
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
        self.assertEqual(profile["settings"]["debounce_ms"], 7)
        self.assertEqual(profile["settings"]["app_effects"][0]["mode"], "conic")
        self.assertEqual(len(compile_profile(profile)["keymap"]), 620)

    def test_mapping_covers_every_unique_vendor_assignment_usage(self) -> None:
        self.assertEqual(len(set(KCODE_TO_USAGE.values())), 130)

    def test_imports_built_in_vendor_lighting_snapshot(self) -> None:
        profile, imported = convert_vendor_document({
            "value": {
                "Keyboard_Export": {
                    "lightData": {
                        "translate": "Fixed_on",
                        "currentColorsIndex": 6,
                        "ParameterNumberList": [
                            {"field": "brightness", "setValue": 3},
                            {"field": "speed", "setValue": 2},
                        ],
                        "ParameterBoolList": [
                            {"field": "multicolor", "setValue": False},
                        ],
                    }
                }
            }
        })

        self.assertEqual(imported, ["KeyAssign"])
        self.assertEqual(profile["lighting"], {
            "effect": "fixed",
            "brightness": 3,
            "speed": 2,
            "color_index": 6,
            "multicolor": False,
        })
        lighting_report = compile_profile(profile)["lighting"][0]
        self.assertEqual(lighting_report[9:12], bytes((0x01, 3, 2)))
        self.assertEqual(lighting_report[12], 6)

    def test_imports_customize_lighting_and_per_key_colors(self) -> None:
        custom_colors = [[0, 0, 0] for _ in VENDOR_UI_KEY_NAMES]
        custom_colors[0] = [0x12, 0x34, 0x56]
        custom_colors[62] = [0x11, 0x22, 0x33]
        custom_colors[66] = [0xAA, 0xBB, 0xCC]
        profile, imported = convert_vendor_document({
            "value": {
                "Keyboard_Export": {
                    "lightData": {
                        "translate": "Customize",
                        "currentColorsIndex": 0,
                        "ParameterNumberList": [
                            {"field": "brightness", "setValue": 2},
                            {"field": "speed", "setValue": 4},
                        ],
                        "ParameterBoolList": [
                            {"field": "multicolor", "setValue": False},
                        ],
                        "CustomizeColors": custom_colors,
                    }
                }
            }
        })

        self.assertEqual(imported, ["KeyAssign"])
        self.assertEqual(
            {
                key: value
                for key, value in profile["lighting"].items()
                if key != "colors"
            },
            {
                "effect": "custom",
                "brightness": 2,
                "speed": 4,
                "color_index": 0,
                "multicolor": False,
            },
        )
        self.assertEqual(profile["colors"]["esc"], "#123456")
        self.assertEqual(profile["colors"]["rctrl"], "#112233")
        self.assertEqual(profile["colors"]["ralt"], "#aabbcc")
        self.assertEqual(profile["lighting"]["colors"], profile["colors"])
        self.assertIsNot(profile["lighting"]["colors"], profile["colors"])

        compiled = compile_profile(profile)
        self.assertEqual(
            compiled["matrix_colors"][BUTTON_TO_SLOT["rctrl"]],
            (0x11, 0x22, 0x33),
        )
        self.assertEqual(
            compiled["matrix_colors"][BUTTON_TO_SLOT["ralt"]],
            (0xAA, 0xBB, 0xCC),
        )
        self.assertEqual(
            [report[1] for report in compiled["lighting"]],
            [0x02, 0x07],
        )

    def test_rejects_an_incomplete_or_malformed_custom_palette(self) -> None:
        valid = [[0, 0, 0] for _ in VENDOR_UI_KEY_NAMES]
        cases = (
            (valid[:-1], "exactly 70 RGB entries"),
            ([*valid[:-1], [0, 0]], "entry 69 .* three RGB bytes"),
            ([*valid[:-1], [0, 0, 256]], "entry 69 .* three RGB bytes"),
            ([*valid[:-1], [0, 0, True]], "entry 69 .* three RGB bytes"),
        )
        for colors, message in cases:
            with self.subTest(colors=colors[-1]):
                with self.assertRaisesRegex(ValueError, message):
                    convert_vendor_document({
                        "value": {
                            "Keyboard_Export": {
                                "lightData": {
                                    "translate": "Customize",
                                    "CustomizeColors": colors,
                                }
                            }
                        }
                    })

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
