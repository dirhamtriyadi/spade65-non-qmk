"""Original, documented Spade65 matrix data derived from interoperability work."""

from __future__ import annotations

from .protocol import keymap_report


MATRIX_LENGTH = 102

# Names are indexed by the firmware matrix slot, not physical/UI order. Empty
# strings are real unused slots and must not be removed.
MATRIX_KEY_NAMES = (
    "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",
    "esc", "n1", "n2", "n3", "n4", "n5", "n6", "n7", "n8", "n9", "n0",
    "minus", "plus", "", "bksp", "", "", "tab", "q", "w", "e", "r", "t",
    "y", "u", "i", "o", "p", "lqu", "rqu", "k29", "delete", "", "", "caps",
    "a", "s", "d", "f", "g", "h", "j", "k", "l", "sem", "quo", "k42",
    "enter", "pageup", "", "", "lshift", "", "z", "x", "c", "v", "b", "n",
    "m", "comma", "dot", "qmark", "rshift", "up", "pagedown", "", "", "lctrl",
    "win", "lalt", "lspace", "ralt", "", "mspace", "rspace", "mute", "rspace",
    "fn", "rctrl", "left", "down", "right", "", "",
)

# USB HID usages stored in the official default profile, in matrix-slot order.
DEFAULT_USAGES = bytes.fromhex(
    "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
    "29 1e 1f 20 21 22 23 24 25 26 27 2d 2e 00 2a 00 00 "
    "2b 14 1a 08 15 17 1c 18 0c 12 13 2f 30 31 4c 00 00 "
    "39 04 16 07 09 0a 0b 0d 0e 0f 33 34 31 28 4b 00 00 "
    "e1 00 1d 1b 06 19 05 11 10 36 37 38 e5 52 4e 00 00 "
    "e0 e3 e2 2c e6 00 2c 00 a2 2c fe e4 50 51 4f 00 00"
)

# The UI exposes these 70 names. Mapping uses the first matching matrix slot,
# mirroring the vendor application while retaining all 102 firmware slots.
UI_KEY_NAMES = (
    "esc", "n1", "n2", "n3", "n4", "n5", "n6", "n7", "n8", "n9", "n0",
    "minus", "plus", "bksp", "tab", "q", "w", "e", "r", "t", "y", "u", "i",
    "o", "p", "lqu", "rqu", "k29", "delete", "caps", "a", "s", "d", "f", "g",
    "h", "j", "k", "l", "sem", "quo", "k42", "enter", "pageup", "lshift", "z",
    "x", "c", "v", "b", "n", "m", "comma", "dot", "qmark", "rshift", "up",
    "pagedown", "lctrl", "win", "lalt", "lspace", "ralt", "mspace", "rspace", "fn",
    "rctrl", "left", "down", "right",
)

BUTTON_TO_SLOT = {name: MATRIX_KEY_NAMES.index(name) for name in UI_KEY_NAMES}


def default_keymap_report(*, fn_mode_index: int = 0) -> bytes:
    """Return the vendor-default three-layer frame for offline inspection."""

    empty_layer = (None,) * MATRIX_LENGTH
    return keymap_report(
        (empty_layer, empty_layer, empty_layer),
        default_usages=DEFAULT_USAGES,
        fn_mode_index=fn_mode_index,
    )


def export_default() -> dict[str, object]:
    """Return a JSON-serializable description and the complete offline frame."""

    report = default_keymap_report()
    return {
        "device": "0603:0351",
        "matrix_length": MATRIX_LENGTH,
        "ui_key_count": len(UI_KEY_NAMES),
        "fn_mode_index": 0,
        "buttons": [
            {
                "name": name,
                "slot": BUTTON_TO_SLOT[name],
                "default_usage": DEFAULT_USAGES[BUTTON_TO_SLOT[name]],
            }
            for name in UI_KEY_NAMES
        ],
        "matrix": [
            {
                "slot": slot,
                "name": name or None,
                "default_usage": DEFAULT_USAGES[slot],
            }
            for slot, name in enumerate(MATRIX_KEY_NAMES)
        ],
        "report": {
            "id": report[0],
            "opcode": report[1],
            "length": len(report),
            "hex": report.hex(),
        },
    }
