"""The rendered bottom row must match the keyboard in front of the operator.

Verified on the wired 0603:0351 unit with evtest on the boot-keyboard node:
pressing the spacebar reports usage 0x2c, the next key to its right reports
nothing at all because Fn is resolved inside the firmware, and the key after
that reports MSC_SCAN 0x700e6 — usage 0xe6, Right Alt. There is no Right Ctrl
key on this board, so drawing one puts every label to the right of the
spacebar over the wrong physical key.
"""

import re
import unittest
from pathlib import Path

from spade65.effects import KEY_ROWS
from spade65.keymap import BUTTON_TO_SLOT, DEFAULT_USAGES, MATRIX_KEY_NAMES

APP_JS = Path(__file__).resolve().parents[1] / "spade65" / "web" / "app.js"


def _positions(source: str, name: str) -> list[tuple[int, int]]:
    body = re.search(rf"{name}\s*=\s*\[(.*?)\n\]", source, re.S).group(1)
    entries = re.findall(r"\[([^\[\]]*)\]", body)
    return [
        (int(parts[0]), int(parts[2]))
        for parts in (
            [value.strip() for value in entry.split(",")] for entry in entries
        )
    ]


def _split_overrides(source: str, family: str) -> dict[int, tuple[int, int]]:
    blob = re.search(r"splitPositions\s*=\s*\{(.*?)\n\}", source, re.S).group(1)
    section = re.search(rf"{family}\s*:\s*\{{(.*?)\}}", blob, re.S).group(1)
    result = {}
    for index, values in re.findall(r"(\d+)\s*:\s*\[([^\]]*)\]", section):
        parts = [value.strip() for value in values.split(",")]
        result[int(index)] = (int(parts[0]), int(parts[2]))
    return result


def visible_bottom_row(variant: str) -> list[str]:
    """Return the bottom-row keys the GUI actually draws for a variant."""

    source = APP_JS.read_text(encoding="utf-8")
    names = re.findall(
        r"'([^']+)'", re.search(r"const rows = \[(.*?)\n\];", source, re.S).group(1)
    )
    family = "iso" if variant.startswith("iso") else "ansi"
    base = _positions(source, "isoPositions" if family == "iso" else "ansiPositions")
    if variant.endswith("split"):
        for index, value in _split_overrides(source, family).items():
            base[index] = value
    bottom = len(names) - 12
    # buildKeyboard positions every key absolutely, so what the operator sees
    # left to right is the x order, not the order of the rows array.
    drawn = [
        (base[index][0], name)
        for index, name in enumerate(names)
        if index >= bottom and base[index][1] > 0
    ]
    return [name for _, name in sorted(drawn)]


class BottomRowTests(unittest.TestCase):
    VERIFIED = [
        "lctrl", "win", "lalt", "mspace", "fn", "ralt", "left", "down", "right",
    ]

    def test_standard_layouts_draw_the_verified_physical_bottom_row(self) -> None:
        for variant in ("ansi-standard", "iso-standard"):
            with self.subTest(variant=variant):
                self.assertEqual(visible_bottom_row(variant), self.VERIFIED)

    def test_standard_layouts_do_not_draw_a_key_the_board_lacks(self) -> None:
        # 0xe4 Right Ctrl never appeared on this hardware.
        for variant in ("ansi-standard", "iso-standard"):
            with self.subTest(variant=variant):
                self.assertNotIn("rctrl", visible_bottom_row(variant))

    SPLIT = [
        "lctrl", "win", "lalt", "lspace", "mspace", "rspace", "fn", "ralt",
        "left", "down", "right",
    ]

    def test_split_layouts_put_the_same_slot_to_the_right_of_fn(self) -> None:
        # The matrix belongs to the PCB, and the RALT-variant key at canonical
        # slot 96 remains right of Fn. Splitting the spacebar changes only
        # which caps cover the space slots.
        for variant in ("ansi-split", "iso-split"):
            with self.subTest(variant=variant):
                self.assertEqual(visible_bottom_row(variant), self.SPLIT)

    def test_no_layout_draws_the_absent_right_ctrl(self) -> None:
        for variant in ("ansi-standard", "iso-standard", "ansi-split", "iso-split"):
            with self.subTest(variant=variant):
                self.assertNotIn("rctrl", visible_bottom_row(variant))

    def test_each_split_space_segment_addresses_a_distinct_slot(self) -> None:
        segments = [BUTTON_TO_SLOT[name] for name in ("lspace", "mspace", "rspace")]
        self.assertEqual(len(set(segments)), 3)

    def test_the_drawn_right_modifier_addresses_the_slot_that_sends_0xe6(self) -> None:
        self.assertEqual(BUTTON_TO_SLOT["ralt"], 96)
        self.assertEqual(DEFAULT_USAGES[BUTTON_TO_SLOT["ralt"]], 0xE6)
        self.assertEqual(BUTTON_TO_SLOT["rctrl"], 89)
        self.assertEqual(DEFAULT_USAGES[BUTTON_TO_SLOT["rctrl"]], 0xE4)
        self.assertNotEqual(BUTTON_TO_SLOT["ralt"], BUTTON_TO_SLOT["rctrl"])

    def test_host_effect_geometry_uses_the_same_ralt_position(self) -> None:
        self.assertEqual(
            KEY_ROWS[-1],
            (
                "lctrl", "win", "lalt", "lspace", "rctrl", "mspace",
                "rspace", "fn", "ralt", "left", "down", "right",
            ),
        )

    def test_the_spacebar_this_board_has_types_a_space(self) -> None:
        # Only mspace is drawn on a standard board, and it is the one key of the
        # three that this hardware could confirm. lspace and rspace belong to
        # split boards; see the rspace ambiguity pinned below.
        self.assertEqual(DEFAULT_USAGES[BUTTON_TO_SLOT["mspace"]], 0x2C)

    def test_the_unresolved_rspace_slot_ambiguity_is_recorded(self) -> None:
        """Pin a known ambiguity so it is a decision, not an accident.

        Two matrix slots are named ``rspace``. ``BUTTON_TO_SLOT`` builds from
        ``MATRIX_KEY_NAMES.index``, so the name resolves to whichever comes
        first, and nobody chose that. Their factory defaults disagree: slot 92
        is 0x00, which is what unused slot 90 also holds, while slot 94 is
        0x2c, the space a key called "right space" should type. That makes
        slot 94 the likelier candidate, but likelier is not verified.

        Only a split spacebar can settle it, and this hardware has one solid
        bar, so there is no right-hand segment to press. The same shape of
        argument -- a default usage that matches an observed function -- is
        what wrongly suggested slot 93 drove the volume knob, and a write test
        refuted that. So the table stays as transcribed.

        rspace is drawn only by the split layouts, so nothing on a standard
        board reaches this slot. If this test fails, the naming changed:
        establish which slot the hardware uses before adjusting the mapping.
        """

        duplicates = [
            index
            for index, name in enumerate(MATRIX_KEY_NAMES)
            if name == "rspace"
        ]
        self.assertEqual(duplicates, [92, 94])
        self.assertEqual(BUTTON_TO_SLOT["rspace"], 92)
        self.assertEqual(DEFAULT_USAGES[92], 0x00)
        self.assertEqual(DEFAULT_USAGES[94], 0x2C)
        # Slot 90 is unnamed and also 0x00, the pattern slot 92 follows.
        self.assertEqual(MATRIX_KEY_NAMES[90], "")
        self.assertEqual(DEFAULT_USAGES[90], 0x00)

        for variant in ("ansi-standard", "iso-standard"):
            with self.subTest(variant=variant):
                self.assertNotIn("rspace", visible_bottom_row(variant))
        for variant in ("ansi-split", "iso-split"):
            with self.subTest(variant=variant):
                self.assertIn("rspace", visible_bottom_row(variant))


if __name__ == "__main__":
    unittest.main()
