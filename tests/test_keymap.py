import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from spade65.keymap import (
    parse_usage,
    HID_USAGES,
    BUTTON_TO_SLOT,
    DEFAULT_USAGES,
    MATRIX_KEY_NAMES,
    UI_KEY_NAMES,
    USAGE_GROUPS,
    VENDOR_DEFAULT_USAGES,
    VENDOR_MATRIX_KEY_NAMES,
    VENDOR_UI_KEY_NAMES,
    compile_profile,
    default_keymap_report,
    export_default,
    profile_template,
)
from spade65.protocol import (
    EFFECTS,
    MacroEvent,
    debounce_report,
    macro_report,
    rgb_effect_report,
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

    def test_raw_vendor_variant_data_is_preserved(self) -> None:
        self.assertEqual(VENDOR_MATRIX_KEY_NAMES[89], "ralt")
        self.assertEqual(VENDOR_DEFAULT_USAGES[89], 0xE6)
        self.assertEqual(VENDOR_MATRIX_KEY_NAMES[96], "rctrl")
        self.assertEqual(VENDOR_DEFAULT_USAGES[96], 0xE4)
        self.assertEqual(VENDOR_UI_KEY_NAMES[62], "ralt")
        self.assertEqual(VENDOR_UI_KEY_NAMES[66], "rctrl")

    def test_ralt_variant_has_distinct_canonical_modifier_slots(self) -> None:
        self.assertEqual(MATRIX_KEY_NAMES[89], "rctrl")
        self.assertEqual(DEFAULT_USAGES[89], 0xE4)
        self.assertEqual(MATRIX_KEY_NAMES[96], "ralt")
        self.assertEqual(DEFAULT_USAGES[96], 0xE6)
        self.assertEqual(UI_KEY_NAMES[62], "rctrl")
        self.assertEqual(UI_KEY_NAMES[66], "ralt")
        self.assertEqual(BUTTON_TO_SLOT["rctrl"], 89)
        self.assertEqual(BUTTON_TO_SLOT["ralt"], 96)
        self.assertNotEqual(BUTTON_TO_SLOT["rctrl"], BUTTON_TO_SLOT["ralt"])

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

    def test_balanced_macro_allows_modifier_around_another_usage(self) -> None:
        profile = profile_template()
        profile["macros"] = [
            {
                "index": 0,
                "repeat": 1,
                "events": [
                    {"delay_ms": 20, "usage": "left-ctrl", "pressed": True},
                    {"delay_ms": 20, "usage": "c", "pressed": True},
                    {"delay_ms": 20, "usage": "c", "pressed": False},
                    {"delay_ms": 20, "usage": "left-ctrl", "pressed": False},
                ],
            }
        ]

        compiled = compile_profile(profile)

        self.assertEqual(len(compiled["macros"]), 1)

    def test_macro_rejects_key_up_before_key_down(self) -> None:
        profile = profile_template()
        profile["macros"] = [
            {
                "index": 0,
                "events": [
                    {"delay_ms": 20, "usage": "a", "pressed": False},
                ],
            }
        ]

        with self.assertRaisesRegex(
            ValueError, r"macro 0 event 1 has key-up before key-down.*0x04"
        ):
            compile_profile(profile)

    def test_macro_rejects_duplicate_key_down(self) -> None:
        profile = profile_template()
        profile["macros"] = [
            {
                "index": 0,
                "events": [
                    {"delay_ms": 20, "usage": "a", "pressed": True},
                    {"delay_ms": 20, "usage": "a", "pressed": True},
                    {"delay_ms": 20, "usage": "a", "pressed": False},
                ],
            }
        ]

        with self.assertRaisesRegex(
            ValueError, r"macro 0 event 2 has duplicate key-down.*0x04"
        ):
            compile_profile(profile)

    def test_macro_rejects_usage_still_held_at_end(self) -> None:
        profile = profile_template()
        profile["macros"] = [
            {
                "index": 0,
                "events": [
                    {"delay_ms": 20, "usage": "a", "pressed": True},
                ],
            }
        ]

        with self.assertRaisesRegex(
            ValueError, r"macro 0 ends with usages still held: 0x04"
        ):
            compile_profile(profile)

    def test_profile_template_compiles_the_vendor_tail_debounce(self) -> None:
        profile = profile_template()

        self.assertEqual(profile["settings"]["debounce_ms"], 5)
        self.assertEqual(compile_profile(profile)["debounce"], debounce_report(5))

    def test_legacy_profile_without_debounce_uses_five_milliseconds(self) -> None:
        profile = profile_template()
        profile["settings"].pop("debounce_ms")

        self.assertEqual(compile_profile(profile)["debounce"], debounce_report(5))

    def test_profile_debounce_compiles_the_selected_value(self) -> None:
        profile = profile_template()
        profile["settings"]["debounce_ms"] = 17

        compiled = compile_profile(profile)
        self.assertEqual(compiled["debounce_ms"], 17)
        self.assertEqual(compiled["debounce"], debounce_report(17))

    def test_invalid_profile_debounce_is_rejected(self) -> None:
        for value in (True, False, 0, 256, "5", None):
            with self.subTest(value=value):
                profile = profile_template()
                profile["settings"]["debounce_ms"] = value
                with self.assertRaisesRegex(ValueError, "debounce"):
                    compile_profile(profile)

    def test_compiles_right_modifiers_without_alias_collision(self) -> None:
        profile = profile_template()
        profile["layers"]["normal"].update({"rctrl": "b", "ralt": "a"})
        profile["colors"].update({"rctrl": "#112233", "ralt": "#aabbcc"})
        compiled = compile_profile(profile)
        report = compiled["keymap"]
        self.assertEqual(report[8 + 2 * 89 : 8 + 2 * 89 + 2], b"\x80\x05")
        self.assertEqual(report[8 + 2 * 96 : 8 + 2 * 96 + 2], b"\x80\x04")
        self.assertEqual(compiled["matrix_colors"][89], (0x11, 0x22, 0x33))
        self.assertEqual(compiled["matrix_colors"][96], (0xAA, 0xBB, 0xCC))

    def test_default_report_keeps_ralt_at_physical_variant_slot(self) -> None:
        report = default_keymap_report()
        self.assertEqual(report[8 + 2 * 89 : 8 + 2 * 89 + 2], b"\x00\xe4")
        self.assertEqual(report[8 + 2 * 96 : 8 + 2 * 96 + 2], b"\x00\xe6")

    def test_rejects_reference_to_undefined_macro(self) -> None:
        profile = profile_template()
        profile["layers"]["normal"]["a"] = {"macro": 4}
        with self.assertRaisesRegex(ValueError, "undefined macros"):
            compile_profile(profile)


class WebUsageNameTests(unittest.TestCase):
    """The recorder writes these names straight into a profile."""

    def _producible(self) -> set[str]:
        """Ask the mapper itself what it can emit.

        Deriving the generated families here instead would only restate an
        assumption: the leak that made profiles unappliable was in the function
        key pattern, not in the table, so a hardcoded f1..f12 would have missed
        it entirely.
        """

        if shutil.which("node") is None:
            self.skipTest("node is required to enumerate the web usage mapper")
        module = (
            Path(__file__).resolve().parents[1] / "spade65" / "web" / "key-events.js"
        )
        script = f"""
        const keys = require({str(module)!r});
        const codes = [];
        for (let c = 65; c <= 90; c += 1) codes.push("Key" + String.fromCharCode(c));
        for (let d = 0; d <= 9; d += 1) codes.push("Digit" + d);
        for (let f = 1; f <= 24; f += 1) codes.push("F" + f);
        codes.push(...Object.keys(keys.USAGES));
        const out = new Set();
        for (const code of codes) {{
          const usage = keys.usageForCode(code);
          if (usage !== null) out.add(usage);
        }}
        console.log(JSON.stringify([...out]));
        """
        result = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True, timeout=60
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return set(json.loads(result.stdout))

    def test_every_name_the_recorder_can_emit_compiles(self) -> None:
        # A browser code that produced a name HID_USAGES does not know made the
        # recorded profile unappliable. F13..F24, which this keyboard
        # advertises, used to leak through as "f13".
        unknown = sorted(name for name in self._producible() if name not in HID_USAGES)
        self.assertEqual(unknown, [])

    def test_each_name_survives_the_profile_compiler(self) -> None:
        for name in sorted(self._producible()):
            with self.subTest(usage=name):
                self.assertIsInstance(parse_usage(name), int)


class WebMacroLimitTests(unittest.TestCase):
    """The recorder must stop where the protocol stops accepting."""

    def test_the_recorder_limit_matches_the_one_the_protocol_enforces(self) -> None:
        # A recorder that let one more event through would build a macro
        # macro_reports refuses, and the user would only find out on Apply.
        if shutil.which("node") is None:
            self.skipTest("node is required to read the web macro limit")
        module = (
            Path(__file__).resolve().parents[1] / "spade65" / "web" / "macro-rules.js"
        )
        script = f"console.log(require({str(module)!r}).MAX_EVENTS)"
        result = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True, timeout=60
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        limit = int(result.stdout.strip())

        events = [MacroEvent(delay_ms=0, usage=4, pressed=True)] * limit
        macro_report(0, events)
        with self.assertRaisesRegex(ValueError, "at most"):
            macro_report(0, events + events[:1])


class WebLightingBoundsTests(unittest.TestCase):
    """The editor must refuse what rgb_effect_report would refuse."""

    def _bounds(self) -> dict[str, list[int]]:
        if shutil.which("node") is None:
            self.skipTest("node is required to read the web lighting bounds")
        module = (
            Path(__file__).resolve().parents[1] / "spade65" / "web" / "live-effects.js"
        )
        script = (
            f"console.log(JSON.stringify(require({str(module)!r}).LIGHTING_BOUNDS))"
        )
        result = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True, timeout=60
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_each_bound_is_exactly_where_the_protocol_starts_refusing(self) -> None:
        # A snapshot the page accepts but the protocol rejects would only fail
        # on Apply, after the user thought the setting was saved.
        effect = next(iter(EFFECTS))
        for field, (low, high) in self._bounds().items():
            with self.subTest(field=field):
                rgb_effect_report(effect, **{field: low})
                rgb_effect_report(effect, **{field: high})
                for outside in (low - 1, high + 1):
                    with self.assertRaises(ValueError):
                        rgb_effect_report(effect, **{field: outside})


if __name__ == "__main__":
    unittest.main()
