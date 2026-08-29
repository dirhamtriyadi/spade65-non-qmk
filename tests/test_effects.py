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


if __name__ == "__main__":
    unittest.main()
