import unittest

from spade65.effects import render_app_effects, timeline_frames
from spade65.keymap import profile_template


class EffectTests(unittest.TestCase):
    def test_renders_all_visible_keys_deterministically(self) -> None:
        profile = profile_template()
        profile["settings"]["app_effects"] = [{
            "mode": "wave", "opacity": 100, "speed": 5,
            "gradient": True, "colors": ["#ff0000", "#0000ff"],
        }]
        first = render_app_effects(profile, 1.5)
        second = render_app_effects(profile, 1.5)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 70)
        self.assertRegex(first["esc"], r"^#[0-9a-f]{6}$")

    def test_timeline_is_bounded_and_normalized(self) -> None:
        profile = profile_template()
        profile["settings"]["custom_timeline"] = {
            "frames": [{"duration_ms": 1, "colors": {"esc": "#ff0000"}}]
        }
        frames = timeline_frames(profile)
        self.assertEqual(frames[0]["duration_ms"], 20)

    def test_master_brightness_scales_final_layer_mix(self) -> None:
        profile = profile_template()
        profile["settings"]["app_effects"] = [{
            "mode": "cycle", "opacity": 100, "speed": 1,
            "gradient": False, "colors": ["#ff8040"],
        }]
        full = render_app_effects(profile, 0)
        profile["settings"]["live_effects"] = {"master_brightness": 50}
        half = render_app_effects(profile, 0)
        profile["settings"]["live_effects"] = {"master_brightness": 0}
        off = render_app_effects(profile, 0)

        self.assertEqual(full["esc"], "#ff8040")
        self.assertEqual(half["esc"], "#804020")
        self.assertTrue(all(color == "#000000" for color in off.values()))


if __name__ == "__main__":
    unittest.main()
