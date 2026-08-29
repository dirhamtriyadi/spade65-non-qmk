"""Offline conversion of JSON files exported by the original Spade65 app."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .keymap import HID_USAGES, UI_KEY_NAMES, compile_profile, profile_template


# SupportData.AllFunctionMapping from Spade65_SETUP_20240403.exe.  The vendor
# stores KCode strings in KeyAssign exports rather than USB usages.
KCODE_TO_USAGE = {
    "K50": 0xB4, "K51": 0xB5, "K52": 0xB6, "K53": 0xB7, "K54": 0xB8,
    "K153": 0x04, "K170": 0x05, "K168": 0x06, "K155": 0x07,
    "K138": 0x08, "K156": 0x09, "K157": 0x0A, "K158": 0x0B,
    "K143": 0x0C, "K159": 0x0D, "K160": 0x0E, "K161": 0x0F,
    "K172": 0x10, "K171": 0x11, "K144": 0x12, "K145": 0x13,
    "K136": 0x14, "K139": 0x15, "K154": 0x16, "K140": 0x17,
    "K142": 0x18, "K169": 0x19, "K137": 0x1A, "K167": 0x1B,
    "K141": 0x1C, "K166": 0x1D,
    "K128": 0x27, "K119": 0x1E, "K120": 0x1F, "K121": 0x20,
    "K122": 0x21, "K123": 0x22, "K124": 0x23, "K125": 0x24,
    "K126": 0x25, "K127": 0x26,
    "K131": 0x2A, "K135": 0x2B, "K164": 0x28, "K117": 0x48,
    "K152": 0x39, "K11": 0x29, "K181": 0x2C, "K134": 0x4B,
    "K151": 0x4E, "K150": 0x4D, "K133": 0x4A, "K186": 0x50,
    "K177": 0x52, "K188": 0x4F, "K187": 0x51, "K115": 0x46,
    "K132": 0x49, "K149": 0x4C,
    "K179": 0xE3, "K183": 0xE7, "K165": 0xE1, "K178": 0xE0,
    "K180": 0xE2, "K176": 0xE5, "K185": 0xE4, "K182": 0xE6,
    "K184": 0x65,
    **{f"K{12 + number}": 0x39 + number for number in range(1, 8)},
    "K110": 0x41, "K111": 0x42, "K112": 0x43, "K113": 0x44,
    "K114": 0x45, "K116": 0x47,
    "K162": 0x33, "K130": 0x2E, "K173": 0x36, "K129": 0x2D,
    "K174": 0x37, "K175": 0x38, "K118": 0x35, "K146": 0x2F,
    "K147": 0x30, "K163": 0x34, "K148": 0x31,
    "K21": 0x53, "K211": 0x59, "K212": 0x5A, "K213": 0x5B,
    "K29": 0x5C, "K218": 0x5D, "K210": 0x5E, "K25": 0x5F,
    "K26": 0x60, "K27": 0x61, "K22": 0x54, "K23": 0x55,
    "K24": 0x56, "K28": 0x57, "K217": 0x58, "K215": 0x62,
    "K216": 0x63,
    "K31": 0xA0, "K32": 0xA1, "K33": 0xA5, "K34": 0xA6,
    "K35": 0xA7, "K36": 0xA3, "K37": 0xA4, "K38": 0xA2,
    "K41": 0xAB, "K42": 0xAC, "K43": 0xA9, "K44": 0xAD,
    "K45": 0xA8, "K46": 0xB1, "K47": 0xAF, "K48": 0xD7,
    "K49": 0xD6, "K71": 0xB2, "K72": 0xB3, "K189": 0xFE,
    "K190": 0xFF,
}

KEYCODE_TO_USAGE = {
    **{str(code): 0x04 + code - 65 for code in range(65, 91)},
    **{str(code): (0x27 if code == 48 else 0x1D + code - 48) for code in range(48, 58)},
    **{str(code): 0x3A + code - 112 for code in range(112, 124)},
    "8": 0x2A, "9": 0x2B, "13": 0x28, "19": 0x48, "20": 0x39,
    "27": 0x29, "32": 0x2C, "33": 0x4B, "34": 0x4E, "35": 0x4D,
    "36": 0x4A, "37": 0x50, "38": 0x52, "39": 0x4F, "40": 0x51,
    "42": 0x46, "45": 0x49, "46": 0x4C, "91": 0xE3, "92": 0xE7,
    "16": 0xE1, "17": 0xE0, "18": 0xE2, "93": 0x65, "145": 0x47,
    "186": 0x33, "187": 0x2E, "188": 0x36, "189": 0x2D,
    "190": 0x37, "191": 0x38, "192": 0x35, "219": 0x2F,
    "220": 0x31, "221": 0x30, "222": 0x34, "144": 0x53,
    **{str(code): 0x59 + code - 97 for code in range(97, 106)},
    "106": 0x55, "107": 0x57, "109": 0x56, "110": 0x63,
    "111": 0x54, "96": 0x62,
}

VALUE_TO_USAGE = {name.lower(): usage for name, usage in HID_USAGES.items()}
VALUE_TO_USAGE.update({
    "escape": 0x29, "back": 0x29, "pageup": 0x4B, "pagedown": 0x4E,
    "capslock": 0x39, "numdot": 0x63, "win": 0xE3, "left win": 0xE3,
    "right win": 0xE7, "rctrl": 0xE4, "rshift": 0xE5, "ralt": 0xE6,
    "(+ )": 0x57, "(+)": 0x57, "(-)": 0x56, "(*)": 0x55, "(/)": 0x54,
})


def _unwrap(document: dict[str, Any]) -> dict[str, Any]:
    value = document.get("value", document)
    if not isinstance(value, dict):
        raise ValueError("vendor export value must be an object")
    return value


def _usage_from_value(value: object) -> int | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in VALUE_TO_USAGE:
        return VALUE_TO_USAGE[normalized]
    if len(normalized) == 1 and normalized in HID_USAGES:
        return HID_USAGES[normalized]
    return None


def _combination(value: object) -> object | None:
    if not isinstance(value, str):
        return None
    parts = [part.strip() for part in value.split("+") if part.strip()]
    modifiers = 0
    usage = None
    for part in parts:
        lowered = part.lower()
        if lowered == "ctrl":
            modifiers |= 1
        elif lowered == "shift":
            modifiers |= 2
        elif lowered == "alt":
            modifiers |= 4
        elif lowered in {"win", "gui"}:
            modifiers |= 8
        else:
            usage = _usage_from_value(part)
    if usage is None:
        return None
    return {"usage": usage, "modifiers": modifiers} if modifiers else usage


def _assignment(item: object) -> object | None:
    if not isinstance(item, dict):
        return None
    types = item.get("keyAssignType", ["", "", ""])
    kind = types[2] if isinstance(types, list) and len(types) > 2 else ""
    if kind == "K12":
        return 0
    if kind == "KMacro":
        return {"macro": int(item.get("macroCode", 0))}
    if kind == "KCombination":
        return _combination(item.get("value"))
    if isinstance(kind, str) and kind in KCODE_TO_USAGE:
        return KCODE_TO_USAGE[kind]
    return _usage_from_value(item.get("value"))


def _convert_keyboard(value: dict[str, Any], profile: dict[str, Any]) -> bool:
    exported = value.get("Keyboard_Export")
    if not isinstance(exported, dict):
        return False
    keyboards = exported.get("KeyBoardArray")
    keyboard = keyboards[0] if isinstance(keyboards, list) and keyboards else exported
    if not isinstance(keyboard, dict):
        raise ValueError("Keyboard_Export has no keyboard data")
    sources = [
        keyboard.get("assignedKeyboardKeys", []),
        *(keyboard.get("assignedFnKeyboardKeys", [[], []])[:2]),
    ]
    for layer_name, source in zip(("normal", "fn1", "fn2"), sources):
        if not isinstance(source, list):
            continue
        converted: dict[str, object] = {}
        for button, item in zip(UI_KEY_NAMES, source):
            assignment = _assignment(item)
            if assignment is not None:
                converted[button] = assignment
        profile["layers"][layer_name].update(converted)
    profile["fn_mode_index"] = int(keyboard.get("fnModeindex", 0))
    settings = profile.setdefault("settings", {})
    settings["win_lock"] = bool(keyboard.get("winLock", False))
    settings["wasd_arrows"] = bool(keyboard.get("directionSwitch", False))
    return True


def _macro_items(exported: object) -> list[dict[str, Any]]:
    if not isinstance(exported, dict):
        return []
    if isinstance(exported.get("MacroFiletItem"), list):
        return [item for item in exported["MacroFiletItem"] if isinstance(item, dict)]
    result = []
    for group in exported.get("macroClassItem", []):
        if isinstance(group, dict):
            result.extend(_macro_items(group))
    return result


def _convert_macros(value: dict[str, Any], profile: dict[str, Any]) -> bool:
    if "Macro_Export" not in value:
        return False
    items = _macro_items(value["Macro_Export"])
    macros = []
    for fallback_index, item in enumerate(items[:10]):
        index = int(item.get("IndexCode", fallback_index))
        if not 0 <= index <= 9:
            index = fallback_index
        events = []
        for event in item.get("Data", [])[:84]:
            if not isinstance(event, dict):
                continue
            usage = KEYCODE_TO_USAGE.get(str(event.get("byKeyCode", "")))
            if usage is None:
                continue
            events.append({
                "delay_ms": max(20, int(event.get("byDelay", 20))),
                "usage": usage,
                "pressed": bool(event.get("bKeyDown", False)),
            })
        macros.append({
            "index": index,
            "name": str(item.get("name", f"Macro {index}"))[:40],
            "repeat": min(65535, max(0, int(item.get("RepeatTime", 1)))),
            "events": events,
        })
    profile["macros"] = macros
    return True


def _parameter(items: object, field: str, default: object) -> object:
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and item.get("field") == field:
                return item.get("setValue", default)
    return default


def _convert_ap_mode(value: dict[str, Any], profile: dict[str, Any]) -> bool:
    exported = value.get("Light_Export")
    if not isinstance(exported, list):
        return False
    name_map = {"conicband": "conic", "linearwave": "linear-wave", "breathing": "breathe"}
    layers = []
    for source in exported[:10]:
        if not isinstance(source, dict):
            continue
        numbers = source.get("ParameterNumberList")
        booleans = source.get("ParameterBoolList")
        raw_name = str(source.get("name", "wave")).lower()
        keys = [
            button for button, enabled in zip(UI_KEY_NAMES, source.get("frame_selection_range", []))
            if enabled
        ]
        colors = [color for color in source.get("colors", []) if isinstance(color, str) and len(color) == 7]
        layers.append({
            "mode": name_map.get(raw_name, raw_name),
            "enabled": bool(source.get("check", True)),
            "speed": int(_parameter(numbers, "speed", 5)),
            "opacity": int(_parameter(numbers, "opacity", 50)),
            "bandwidth": int(_parameter(numbers, "bandwidth", 200)),
            "angle": int(_parameter(numbers, "angle", 0)),
            "number": int(_parameter(numbers, "number", 5)),
            "gap": int(_parameter(numbers, "gap", 0)),
            "fire": int(_parameter(numbers, "fire", 1)),
            "center_x": int(source.get("coordinateX", 0)),
            "center_y": int(source.get("coordinateY", 0)),
            "gradient": bool(_parameter(booleans, "gradient", True)),
            "reverse": bool(_parameter(booleans, "direction", False)),
            "bump": bool(_parameter(booleans, "bump", False)),
            "bidirectional": bool(_parameter(booleans, "bidirectional", False)),
            "audio": source.get("audioSync", -1) == 1,
            "colors": colors[:20] or ["#ff0000"],
            "keys": keys if len(keys) != len(UI_KEY_NAMES) else [],
        })
    if layers:
        profile.setdefault("settings", {})["app_effects"] = layers
    return True


def convert_vendor_document(
    document: dict[str, Any], *, base_profile: dict[str, Any] | None = None
) -> tuple[dict[str, Any], list[str]]:
    """Convert one vendor JSON export and return profile plus imported sections."""

    if not isinstance(document, dict):
        raise ValueError("vendor export root must be an object")
    value = _unwrap(document)
    profile = copy.deepcopy(base_profile or profile_template())
    imported = []
    if _convert_keyboard(value, profile):
        imported.append("KeyAssign")
    if _convert_macros(value, profile):
        imported.append("Macro")
    if _convert_ap_mode(value, profile):
        imported.append("APMode")
    if not imported:
        raise ValueError("no Keyboard_Export, Macro_Export, or Light_Export found")
    compile_profile(profile)
    return profile, imported


def convert_vendor_file(
    path: Path, *, base_profile: dict[str, Any] | None = None
) -> tuple[dict[str, Any], list[str]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid vendor JSON: {error}") from error
    return convert_vendor_document(document, base_profile=base_profile)
