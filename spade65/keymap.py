"""Original, documented Spade65 matrix data derived from interoperability work."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .protocol import (
    KeyAssignment,
    MacroEvent,
    MacroReference,
    custom_rgb_report,
    debounce_report,
    keymap_report,
    macro_report,
    rgb_effect_report,
)


MATRIX_LENGTH = 102

# Raw names from the vendor's generic ``0x06030x0351`` SKLocation record.  Keep
# this table entry-for-entry in matrix order: it is still needed to explain and
# convert exports from the original application.  Empty strings are real
# unused slots and must not be removed.
VENDOR_MATRIX_KEY_NAMES = (
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

# Raw usages from the same vendor record, in matrix-slot order.
VENDOR_DEFAULT_USAGES = bytes.fromhex(
    "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
    "29 1e 1f 20 21 22 23 24 25 26 27 2d 2e 00 2a 00 00 "
    "2b 14 1a 08 15 17 1c 18 0c 12 13 2f 30 31 4c 00 00 "
    "39 04 16 07 09 0a 0b 0d 0e 0f 33 34 31 28 4b 00 00 "
    "e1 00 1d 1b 06 19 05 11 10 36 37 38 e5 52 4e 00 00 "
    "e0 e3 e2 2c e6 00 2c 00 a2 2c fe e4 50 51 4f 00 00"
)

# Raw order of the 70 assignment records stored by the original application.
VENDOR_UI_KEY_NAMES = (
    "esc", "n1", "n2", "n3", "n4", "n5", "n6", "n7", "n8", "n9", "n0",
    "minus", "plus", "bksp", "tab", "q", "w", "e", "r", "t", "y", "u", "i",
    "o", "p", "lqu", "rqu", "k29", "delete", "caps", "a", "s", "d", "f", "g",
    "h", "j", "k", "l", "sem", "quo", "k42", "enter", "pageup", "lshift", "z",
    "x", "c", "v", "b", "n", "m", "comma", "dot", "qmark", "rshift", "up",
    "pagedown", "lctrl", "win", "lalt", "lspace", "ralt", "mspace", "rspace", "fn",
    "rctrl", "left", "down", "right",
)

# The physically verified keyboard/firmware is the RALT variant.  Its key at
# the vendor's index 66 / matrix slot 96 is labelled and reports Right Alt; the
# generic vendor data calls that position Right Ctrl.  Vendor index 62 / slot
# 89 is hidden on the standard layouts.  Swap the two semantics in the
# canonical model while preserving the raw source tables above for auditing and
# vendor-profile conversion.
_VENDOR_RALT_SLOT = VENDOR_MATRIX_KEY_NAMES.index("ralt")
_RALT_VARIANT_SLOT = VENDOR_MATRIX_KEY_NAMES.index("rctrl")
_VENDOR_RALT_INDEX = VENDOR_UI_KEY_NAMES.index("ralt")
_VENDOR_RCTRL_INDEX = VENDOR_UI_KEY_NAMES.index("rctrl")

_matrix_key_names = list(VENDOR_MATRIX_KEY_NAMES)
_matrix_key_names[_VENDOR_RALT_SLOT], _matrix_key_names[_RALT_VARIANT_SLOT] = (
    _matrix_key_names[_RALT_VARIANT_SLOT],
    _matrix_key_names[_VENDOR_RALT_SLOT],
)
MATRIX_KEY_NAMES = tuple(_matrix_key_names)

_default_usages = bytearray(VENDOR_DEFAULT_USAGES)
_default_usages[_VENDOR_RALT_SLOT], _default_usages[_RALT_VARIANT_SLOT] = (
    _default_usages[_RALT_VARIANT_SLOT],
    _default_usages[_VENDOR_RALT_SLOT],
)
DEFAULT_USAGES = bytes(_default_usages)

# This remains a 70-entry positional list so ``vendor.py`` can zip it directly
# with KeyAssign/APMode arrays.  At the two variant positions it canonicalizes
# vendor index 66 to ``ralt`` and the hidden vendor index 62 to legacy
# ``rctrl``.
_ui_key_names = list(VENDOR_UI_KEY_NAMES)
_ui_key_names[_VENDOR_RALT_INDEX], _ui_key_names[_VENDOR_RCTRL_INDEX] = (
    _ui_key_names[_VENDOR_RCTRL_INDEX],
    _ui_key_names[_VENDOR_RALT_INDEX],
)
UI_KEY_NAMES = tuple(_ui_key_names)

BUTTON_TO_SLOT = {name: MATRIX_KEY_NAMES.index(name) for name in UI_KEY_NAMES}

LAYER_NAMES = ("normal", "fn1", "fn2")

# ``lightData`` in every fresh profile from the official application. Keep a
# host-side snapshot because this firmware exposes no lighting readback and
# clears lighting while accepting a keymap report.
DEFAULT_LIGHTING = {
    "effect": "neon-stream",
    "brightness": 4,
    "speed": 5,
    "color_index": 0,
    "multicolor": True,
}

# The GUI has historically exposed 5 ms as its initial value and the physical
# wired unit has accepted that value.  Keep it as the legacy/profile migration
# default even though a fresh profile in the vendor application starts at 1 ms.
DEFAULT_DEBOUNCE_MS = 5

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
        "lighting": dict(DEFAULT_LIGHTING),
        "settings": {
            "win_lock": False,
            "wasd_arrows": False,
            "debounce_ms": DEFAULT_DEBOUNCE_MS,
        },
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


def _color_table(
    value: object,
    *,
    label: str,
) -> tuple[tuple[tuple[int, int, int], ...], bytes]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    colors = [(0, 0, 0)] * MATRIX_LENGTH
    for button, color in value.items():
        if button not in BUTTON_TO_SLOT:
            raise ValueError(f"unknown Spade65 color button: {button}")
        colors[BUTTON_TO_SLOT[button]] = _color(color)
    matrix = tuple(colors)
    return matrix, custom_rgb_report(matrix)


def _lighting_reports(value: object) -> tuple[bytes, ...]:
    """Compile a trusted, host-cached lighting snapshot.

    Spade65 firmware clears its lighting while accepting a keymap frame and
    offers no verified report for reading the active effect back. A complete
    snapshot is therefore required before it can be restored. ``None`` uses
    the same Neon Stream default as the official software; pre-snapshot custom
    profiles are migrated by ``_profile_lighting`` before this compiler runs.
    """

    if value is None:
        value = DEFAULT_LIGHTING
    if not isinstance(value, dict):
        raise ValueError("profile lighting must be an object or null")

    base_fields = {"effect", "brightness", "speed", "color_index", "multicolor"}
    missing = sorted(base_fields - set(value))
    if missing:
        raise ValueError(f"profile lighting is missing fields: {', '.join(missing)}")

    effect = value["effect"]
    if not isinstance(effect, str):
        raise ValueError("profile lighting effect must be a string")
    fields = base_fields | ({"colors"} if effect == "custom" else set())
    missing = sorted(fields - set(value))
    if missing:
        raise ValueError(f"profile lighting is missing fields: {', '.join(missing)}")
    unknown = sorted(set(value) - fields)
    if unknown:
        raise ValueError(f"unknown profile lighting fields: {', '.join(unknown)}")
    for field in ("brightness", "speed", "color_index"):
        if isinstance(value[field], bool) or not isinstance(value[field], int):
            raise ValueError(f"profile lighting {field} must be an integer")
    if not isinstance(value["multicolor"], bool):
        raise ValueError("profile lighting multicolor must be true or false")

    effect_report = rgb_effect_report(
        effect,
        brightness=value["brightness"],
        speed=value["speed"],
        color_index=value["color_index"],
        multicolor=value["multicolor"],
    )
    if effect == "custom":
        _matrix, colors_report = _color_table(
            value["colors"], label="profile lighting colors"
        )
        return effect_report, colors_report
    return (effect_report,)


def _profile_lighting(data: dict[str, Any]) -> object:
    """Resolve the cached lighting snapshot for old and current profiles.

    The top-level ``colors`` table has always been an editable per-key draft;
    it does not prove that the custom effect was the last lighting state sent
    to the keyboard.  Profiles created before ``lighting`` existed therefore
    use the documented vendor default instead of silently activating that
    possibly sparse (and mostly black) draft.  An explicit custom snapshot is
    still preserved exactly.
    """

    if "lighting" in data:
        return data["lighting"]
    return None


def _validate_macro_sequence(index: int, events: Sequence[MacroEvent]) -> None:
    """Reject macro event streams that can leave a HID usage held."""

    held: set[int] = set()
    for event_index, event in enumerate(events, start=1):
        if event.pressed:
            if event.usage in held:
                raise ValueError(
                    f"macro {index} event {event_index} has duplicate key-down "
                    f"for usage 0x{event.usage:02x}"
                )
            held.add(event.usage)
            continue
        if event.usage not in held:
            raise ValueError(
                f"macro {index} event {event_index} has key-up before key-down "
                f"for usage 0x{event.usage:02x}"
            )
        held.remove(event.usage)

    if held:
        usages = ", ".join(f"0x{usage:02x}" for usage in sorted(held))
        raise ValueError(f"macro {index} ends with usages still held: {usages}")


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
    macro_reports_by_index: dict[int, bytes] = {}
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
        _validate_macro_sequence(index, events)
        report = macro_report(
            index, events, repeat=int(macro.get("repeat", 1))
        )
        macro_reports.append(report)
        macro_reports_by_index[index] = report
    missing_macros = referenced_macros - seen_macro_indexes
    if missing_macros:
        raise ValueError(f"keymap references undefined macros: {sorted(missing_macros)}")

    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        raise ValueError("profile settings must be an object")
    debounce_ms = settings.get("debounce_ms", DEFAULT_DEBOUNCE_MS)
    if isinstance(debounce_ms, bool) or not isinstance(debounce_ms, int):
        raise ValueError("profile debounce_ms must be an integer")
    debounce = debounce_report(debounce_ms)

    colors, colors_report = _color_table(
        data.get("colors", {}), label="profile colors"
    )
    lighting = _lighting_reports(_profile_lighting(data))

    return {
        "keymap": keymap_report(
            layers,
            default_usages=DEFAULT_USAGES,
            fn_mode_index=int(data.get("fn_mode_index", 0)),
        ),
        "macros": tuple(macro_reports),
        "macro_reports_by_index": macro_reports_by_index,
        "colors": colors_report,
        "lighting": lighting,
        "debounce": debounce,
        "debounce_ms": debounce_ms,
        "matrix_colors": colors,
        "referenced_macros": frozenset(referenced_macros),
    }


PROFILE_SCOPES = ("keymap", "macros", "colors")


def profile_reports(
    data: dict[str, Any],
    compiled: dict[str, object],
    scopes: Sequence[str] | None = None,
) -> tuple[bytes, ...]:
    """Return the reports an apply should send for the requested scopes.

    ``None`` means the whole profile. Scoping exists because the keyboard has
    no configuration readback: writing more than the operator asked for cannot
    be inspected afterwards. The ``colors`` compatibility scope means the
    profile's cached active lighting, never its mutable top-level colour draft.
    Keymap writes are followed by that same snapshot because the firmware
    clears lighting while accepting opcode ``0x03``; this mirrors the vendor
    write order and is a compensating write rather than a selected colour
    change.  This helper remains main-report-only; callers that include the
    keymap must finish the transaction with ``compiled["debounce"]`` on the
    short-report usage.
    """

    if scopes is None:
        selected = set(PROFILE_SCOPES)
    else:
        selected = set(scopes)
        unknown = sorted(selected - set(PROFILE_SCOPES))
        if unknown:
            raise ValueError(
                f"unknown profile scope: {', '.join(unknown)}; "
                f"choose from {', '.join(PROFILE_SCOPES)}"
            )
        if not selected:
            raise ValueError("select at least one profile scope to apply")

    bound = compiled.get("referenced_macros") or frozenset()
    if "keymap" in selected and bound and "macros" not in selected:
        raise ValueError(
            "the keymap binds "
            + ", ".join(f"macro {index}" for index in sorted(bound))
            + ", so the macros scope has to be applied with it; the keyboard "
            "offers no readback, so the bound keys would otherwise run "
            "whichever macros the device still holds"
        )

    reports: list[bytes] = []
    if "keymap" in selected:
        reports.append(compiled["keymap"])  # type: ignore[arg-type]
    if "macros" in selected:
        if "keymap" in selected:
            reports_by_index = compiled["macro_reports_by_index"]
            reports.extend(
                report
                for index, report in reports_by_index.items()  # type: ignore[union-attr]
                if index in bound
            )
        else:
            # The vendor UI has no independent macro-only device action. Keep
            # this project's explicit scope useful by writing every definition
            # when no keymap accompanies it.
            reports.extend(compiled["macros"])  # type: ignore[arg-type]
    if "keymap" in selected or "colors" in selected:
        lighting_reports = compiled["lighting"]
        if not lighting_reports:
            raise ValueError(
                "profile has no trusted lighting snapshot; successfully apply "
                "a built-in effect or per-key lighting once before applying "
                "a keymap"
            )
        reports.extend(lighting_reports)  # type: ignore[arg-type]
    return tuple(reports)


def profile_lighting_recovery_reports(
    reports: Sequence[bytes],
    cached_lighting: Sequence[bytes],
) -> tuple[bytes, ...]:
    """Return cached lighting for best-effort configuration error recovery.

    A failed multi-report transaction may occur after opcode ``0x03`` has
    already cleared lighting, or between a new custom-effect ``0x02`` and its
    palette ``0x07``. Retrying the whole operation would enlarge the failure
    window, so callers retry only the pre-transaction lighting snapshot before
    surfacing the original error. This is deliberately not the planned colour
    suffix: an explicit new palette must not become active after its enclosing
    transaction failed.
    """

    recovery_opcodes = {0x02, 0x03, 0x07}
    if not any(
        len(report) > 1 and report[1] in recovery_opcodes
        for report in reports
    ):
        return ()
    return tuple(cached_lighting)


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
