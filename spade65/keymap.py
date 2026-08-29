"""Original, documented Spade65 matrix data derived from interoperability work."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .protocol import (
    KeyAssignment,
    MacroEvent,
    MacroReference,
    custom_rgb_report,
    keymap_report,
    macro_report,
)


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

LAYER_NAMES = ("normal", "fn1", "fn2")

HID_USAGES = {
    **{chr(ord("a") + index): 0x04 + index for index in range(26)},
    **{str(number): 0x1D + number for number in range(1, 10)},
    "0": 0x27,
    **{f"f{number}": 0x39 + number for number in range(1, 13)},
    "enter": 0x28,
    "esc": 0x29,
    "backspace": 0x2A,
    "tab": 0x2B,
    "space": 0x2C,
    "minus": 0x2D,
    "equal": 0x2E,
    "left-bracket": 0x2F,
    "right-bracket": 0x30,
    "backslash": 0x31,
    "semicolon": 0x33,
    "quote": 0x34,
    "grave": 0x35,
    "comma": 0x36,
    "dot": 0x37,
    "slash": 0x38,
    "caps-lock": 0x39,
    "print-screen": 0x46,
    "scroll-lock": 0x47,
    "pause": 0x48,
    "insert": 0x49,
    "home": 0x4A,
    "page-up": 0x4B,
    "delete": 0x4C,
    "end": 0x4D,
    "page-down": 0x4E,
    "right": 0x4F,
    "left": 0x50,
    "down": 0x51,
    "up": 0x52,
    "menu": 0x65,
    "mute": 0xA2,
    "left-ctrl": 0xE0,
    "left-shift": 0xE1,
    "left-alt": 0xE2,
    "left-gui": 0xE3,
    "right-ctrl": 0xE4,
    "right-shift": 0xE5,
    "right-alt": 0xE6,
    "right-gui": 0xE7,
    "fn": 0xFE,
    "fn2": 0xFF,
    "disabled": 0x00,
    "num-lock": 0x53,
    "num-divide": 0x54,
    "num-multiply": 0x55,
    "num-minus": 0x56,
    "num-plus": 0x57,
    "num-enter": 0x58,
    **{f"num-{number}": 0x62 if number == 0 else 0x58 + number for number in range(10)},
    "num-dot": 0x63,
    # The vendor firmware uses private one-byte function codes for these
    # assignments. Names and values mirror SupportData.AllFunctionMapping.
    "media-player": 0xA0,
    "play-pause": 0xA1,
    "mute": 0xA2,
    "volume-up": 0xA3,
    "volume-down": 0xA4,
    "media-stop": 0xA5,
    "previous-track": 0xA6,
    "next-track": 0xA7,
    "browser-home": 0xA8,
    "browser-refresh": 0xA9,
    "browser-back": 0xAB,
    "browser-forward": 0xAC,
    "browser-favorites": 0xAD,
    "my-computer": 0xAF,
    "email": 0xB1,
    "profile-next": 0xB2,
    "profile-previous": 0xB3,
    "mouse-left": 0xB4,
    "mouse-right": 0xB5,
    "mouse-middle": 0xB6,
    "mouse-back": 0xB7,
    "mouse-forward": 0xB8,
    "copy": 0xD6,
    "paste": 0xD7,
}

USAGE_GROUPS = {
    "Keyboard": tuple(
        [*(chr(ord("a") + index) for index in range(26))]
        + [*(str(number) for number in range(10))]
        + [*(f"f{number}" for number in range(1, 13))]
        + [
            "enter", "esc", "backspace", "tab", "space", "minus", "equal",
            "left-bracket", "right-bracket", "backslash", "semicolon", "quote",
            "grave", "comma", "dot", "slash", "caps-lock", "print-screen",
            "scroll-lock", "pause", "insert", "home", "page-up", "delete",
            "end", "page-down", "right", "left", "down", "up", "menu",
            "left-ctrl", "left-shift", "left-alt", "left-gui", "right-ctrl",
            "right-shift", "right-alt", "right-gui",
        ]
    ),
    "Numpad": tuple(
        ["num-lock", "num-divide", "num-multiply", "num-minus", "num-plus", "num-enter"]
        + [*(f"num-{number}" for number in range(10))]
        + ["num-dot"]
    ),
    "Media": (
        "media-player", "play-pause", "media-stop", "previous-track",
        "next-track", "volume-up", "volume-down", "mute",
    ),
    "Browser/System": (
        "browser-back", "browser-forward", "browser-refresh", "browser-favorites",
        "browser-home", "email", "my-computer", "copy", "paste",
    ),
    "Mouse": ("mouse-left", "mouse-right", "mouse-middle", "mouse-back", "mouse-forward"),
    "Keyboard control": ("profile-next", "profile-previous", "fn", "fn2", "disabled"),
}


def parse_usage(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean is not a HID usage")
    if isinstance(value, int):
        usage = value
    elif isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in HID_USAGES:
            usage = HID_USAGES[normalized]
        else:
            try:
                usage = int(normalized, 0)
            except ValueError as error:
                raise ValueError(f"unknown HID usage name: {value}") from error
    else:
        raise ValueError(f"invalid HID usage: {value!r}")
    if not 0 <= usage <= 0xFF:
        raise ValueError("HID usage must be between 0x00 and 0xff")
    return usage


def profile_template() -> dict[str, object]:
    return {
        "format": "spade65-profile-v1",
        "device": "0603:0351",
        "fn_mode_index": 0,
        "layers": {name: {} for name in LAYER_NAMES},
        "macros": [],
        "colors": {},
        "settings": {"win_lock": False, "wasd_arrows": False},
    }


def load_profile(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid profile JSON: {error}") from error
    if not isinstance(data, dict):
        raise ValueError("profile root must be a JSON object")
    return data


def _assignment(value: object) -> KeyAssignment | MacroReference:
    if isinstance(value, dict):
        if "macro" in value:
            if set(value) != {"macro"}:
                raise ValueError("macro assignment only accepts the macro field")
            return MacroReference(int(value["macro"]))
        if "usage" not in value:
            raise ValueError("key assignment object requires usage")
        unknown = set(value) - {"usage", "modifiers"}
        if unknown:
            raise ValueError(f"unknown key assignment fields: {sorted(unknown)}")
        return KeyAssignment(
            modifiers=int(value.get("modifiers", 0)),
            usage=parse_usage(value["usage"]),
        )
    return KeyAssignment(modifiers=0, usage=parse_usage(value))


def _color(value: object) -> tuple[int, int, int]:
    if isinstance(value, str):
        encoded = value.removeprefix("#")
        if len(encoded) != 6:
            raise ValueError(f"RGB color must use RRGGBB: {value}")
        try:
            return tuple(bytes.fromhex(encoded))  # type: ignore[return-value]
        except ValueError as error:
            raise ValueError(f"invalid RGB color: {value}") from error
    if isinstance(value, list) and len(value) == 3:
        color = tuple(int(channel) for channel in value)
        if all(0 <= channel <= 255 for channel in color):
            return color  # type: ignore[return-value]
    raise ValueError(f"invalid RGB color: {value!r}")


def compile_profile(data: dict[str, Any]) -> dict[str, object]:
    if data.get("format") != "spade65-profile-v1":
        raise ValueError("unsupported profile format")
    if data.get("device") != "0603:0351":
        raise ValueError("profile device must be 0603:0351")
    layers_data = data.get("layers")
    if not isinstance(layers_data, dict) or set(layers_data) != set(LAYER_NAMES):
        raise ValueError("profile layers must contain normal, fn1, and fn2")

    layers: list[list[KeyAssignment | MacroReference | None]] = []
    referenced_macros: set[int] = set()
    for layer_name in LAYER_NAMES:
        assignments = layers_data[layer_name]
        if not isinstance(assignments, dict):
            raise ValueError(f"layer {layer_name} must be an object")
        layer: list[KeyAssignment | MacroReference | None] = [None] * MATRIX_LENGTH
        for button, value in assignments.items():
            if button not in BUTTON_TO_SLOT:
                raise ValueError(f"unknown Spade65 button: {button}")
            assignment = _assignment(value)
            layer[BUTTON_TO_SLOT[button]] = assignment
            if isinstance(assignment, MacroReference):
                referenced_macros.add(assignment.index)
        layers.append(layer)

    macros_data = data.get("macros", [])
    if not isinstance(macros_data, list):
        raise ValueError("profile macros must be an array")
    macro_reports: list[bytes] = []
    seen_macro_indexes: set[int] = set()
    for macro in macros_data:
        if not isinstance(macro, dict):
            raise ValueError("each macro must be an object")
        index = int(macro.get("index", -1))
        if index in seen_macro_indexes:
            raise ValueError(f"duplicate macro index: {index}")
        seen_macro_indexes.add(index)
        events_data = macro.get("events", [])
        if not isinstance(events_data, list):
            raise ValueError("macro events must be an array")
        events = []
        for event in events_data:
            if not isinstance(event, dict):
                raise ValueError("each macro event must be an object")
            if not isinstance(event.get("pressed"), bool):
                raise ValueError("macro event pressed must be true or false")
            events.append(
                MacroEvent(
                    delay_ms=int(event.get("delay_ms", 20)),
                    usage=parse_usage(event.get("usage")),
                    pressed=bool(event.get("pressed")),
                )
            )
        macro_reports.append(
            macro_report(index, events, repeat=int(macro.get("repeat", 1)))
        )
    missing_macros = referenced_macros - seen_macro_indexes
    if missing_macros:
        raise ValueError(f"keymap references undefined macros: {sorted(missing_macros)}")

    colors_data = data.get("colors", {})
    if not isinstance(colors_data, dict):
        raise ValueError("profile colors must be an object")
    colors = [(0, 0, 0)] * MATRIX_LENGTH
    for button, value in colors_data.items():
        if button not in BUTTON_TO_SLOT:
            raise ValueError(f"unknown Spade65 color button: {button}")
        colors[BUTTON_TO_SLOT[button]] = _color(value)

    return {
        "keymap": keymap_report(
            layers,
            default_usages=DEFAULT_USAGES,
            fn_mode_index=int(data.get("fn_mode_index", 0)),
        ),
        "macros": tuple(macro_reports),
        "colors": custom_rgb_report(colors),
        "matrix_colors": tuple(colors),
    }


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
