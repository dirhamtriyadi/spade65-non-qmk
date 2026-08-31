"""Packets recovered from the official Spade65 Windows application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


VENDOR_ID = 0x0603
PRODUCT_IDS = {
    0x0351: "USB",
    0x0356: "Dongle",
}
# PID 0352 is the USB identity observed for the physical 2.4 GHz receiver. Its
# descriptor does not expose either verified configuration collection, so it is
# discoverable for diagnostics only and deliberately absent from PRODUCT_IDS.
# Keep PRODUCT_IDS as the allowlist used by every configuration write path.
READ_ONLY_PRODUCT_IDS = {
    0x0352: "2.4 GHz receiver",
}
OBSERVED_PRODUCT_IDS = {**PRODUCT_IDS, **READ_ONLY_PRODUCT_IDS}


# Streaming RGB is only verified on the wired interface, so it narrows the
# write allowlist rather than repeating a literal at each call site.
STREAMING_PRODUCT_IDS = {0x0351}
# The original backend gates the light-off/hibernate frame on BaseInfo.StateID
# and returns before building it when StateID is 0, the wired identity, so the
# timer is only ever addressed to the dongle. This reproduces that gate.
WIRELESS_TIMER_PRODUCT_IDS = {0x0356}

assert WIRELESS_TIMER_PRODUCT_IDS <= PRODUCT_IDS.keys(), (
    "a wireless timer target must also be a configuration target"
)

assert STREAMING_PRODUCT_IDS <= PRODUCT_IDS.keys(), (
    "a streaming target must also be a configuration target"
)
assert not (PRODUCT_IDS.keys() & READ_ONLY_PRODUCT_IDS.keys()), (
    "a product ID cannot be both a write target and read-only"
)


def configuration_status(product_id: int) -> str:
    """Report whether a product ID may be configured by this application.

    Derived from the write allowlist rather than the read-only table, so an
    identity in neither table fails closed instead of inheriting the label
    that permits writes.
    """

    if product_id in PRODUCT_IDS:
        return "descriptor-gated"
    return "unsupported-read-only"


MAIN_USAGE = (0xFF02, 0x0001)
SHORT_USAGE = (0xFF03, 0x0001)
OUTPUT_USAGE = (0xFF55, 0x0202)

MAIN_REPORT_ID = 0x07
SHORT_REPORT_ID = 0x08
MAIN_REPORT_LENGTH = 0x26C  # Includes the report ID.
SHORT_REPORT_LENGTH = 8  # Includes the report ID.

EFFECTS = {
    "neon-stream": 0x00,
    "fixed": 0x01,
    "breathe": 0x02,
    "ripples-shining": 0x03,
    "rainbow-wheel": 0x04,
    "ripple-band-up-down": 0x05,
    "reaction": 0x06,
    "two-block": 0x07,
    "random-color": 0x08,
    "double-wave": 0x09,
    "retro-snake": 0x0A,
    "double-spiral": 0x0B,
    "ripple-band": 0x0C,
    "kamehameha": 0x0D,
    "wave-90": 0x0E,
    "intersect": 0x0F,
    "shadow-disappear": 0x10,
    "follow": 0x11,
    "snake-up-down": 0x12,
    "custom": 0x13,
}

LIGHT_OFF_MINUTES = (1, 2, 5, 10, 15, 20, 25, 30)
HIBERNATE_MINUTES = (3, 5, 10, 15, 20, 25, 30, 60)


@dataclass(frozen=True)
class KeyAssignment:
    """One explicit USB keyboard assignment in a matrix slot."""

    modifiers: int
    usage: int

    def __post_init__(self) -> None:
        if not 0 <= self.modifiers <= 0x0F:
            raise ValueError("key modifiers must be between 0x00 and 0x0f")
        if not 0 <= self.usage <= 0xFF:
            raise ValueError("key usage must be between 0x00 and 0xff")


@dataclass(frozen=True)
class MacroReference:
    """Reference one of the ten macro reports from a keymap slot."""

    index: int

    def __post_init__(self) -> None:
        if not 0 <= self.index <= 9:
            raise ValueError("macro index must be between 0 and 9")


@dataclass(frozen=True)
class MacroEvent:
    delay_ms: int
    usage: int
    pressed: bool

    def __post_init__(self) -> None:
        if not 0 <= self.delay_ms <= 0x7FFF:
            raise ValueError("macro delay must be between 0 and 32767 ms")
        if not 0 <= self.usage <= 0xFF:
            raise ValueError("macro usage must be between 0x00 and 0xff")


def rgb_effect_report(
    effect: str,
    *,
    brightness: int = 4,
    speed: int = 5,
    color_index: int = 0,
    multicolor: bool = False,
) -> bytes:
    if effect not in EFFECTS:
        raise ValueError(f"unknown RGB effect: {effect}")
    if not 0 <= brightness <= 4:
        raise ValueError("brightness must be between 0 and 4")
    if not 1 <= speed <= 5:
        raise ValueError("speed must be between 1 and 5")
    if not 0 <= color_index <= 7:
        raise ValueError("color index must be between 0 and 7")

    report = bytearray(MAIN_REPORT_LENGTH)
    report[0:3] = bytes((MAIN_REPORT_ID, 0x02, 0x01))
    report[9] = EFFECTS[effect]
    report[10] = brightness
    report[11] = speed

    palette = 7 if multicolor and effect != "fixed" else color_index
    report[12 : 12 + len(EFFECTS)] = bytes((palette,)) * len(EFFECTS)
    return bytes(report)


def keymap_report(
    layers: Sequence[Sequence[KeyAssignment | MacroReference | None]],
    *,
    default_usages: Sequence[int],
    fn_mode_index: int = 0,
) -> bytes:
    """Build opcode 0x03 without sending it to a device.

    ``None`` preserves a slot's default usage and leaves its status byte clear.
    An explicit assignment uses the vendor's 0x80 status bit plus the four
    standard left-modifier bits.
    """

    if len(layers) != 3:
        raise ValueError("keymap must contain exactly three layers")
    if not 0 <= fn_mode_index <= 2:
        raise ValueError("fn mode index must be between 0 and 2")
    if len(default_usages) != 102:
        raise ValueError("Spade65 keymap must contain exactly 102 matrix slots")
    if any(not 0 <= usage <= 0xFF for usage in default_usages):
        raise ValueError("default usages must be bytes")
    if any(len(layer) != len(default_usages) for layer in layers):
        raise ValueError("every keymap layer must contain 102 matrix slots")

    report = bytearray(MAIN_REPORT_LENGTH)
    report[0:3] = bytes((MAIN_REPORT_ID, 0x03, fn_mode_index + 1))
    offset = 8
    for layer in layers:
        for slot, assignment in enumerate(layer):
            if assignment is None:
                report[offset + 1] = default_usages[slot]
            elif isinstance(assignment, MacroReference):
                report[offset] = 0x80
                report[offset + 1] = 0xF0 + assignment.index
            else:
                report[offset] = 0x80 | assignment.modifiers
                report[offset + 1] = assignment.usage
            offset += 2
    return bytes(report)


def macro_report(
    index: int,
    events: Sequence[MacroEvent],
    *,
    repeat: int = 1,
) -> bytes:
    if not 0 <= index <= 9:
        raise ValueError("macro index must be between 0 and 9")
    if not 0 <= repeat <= 0xFFFF:
        raise ValueError("macro repeat must be between 0 and 65535")
    if len(events) > 84:
        raise ValueError("macro supports at most 84 events")

    data = bytearray(256)
    data[0:2] = repeat.to_bytes(2, "big")
    for event_index, event in enumerate(events):
        delay = max(20, event.delay_ms)
        offset = 2 + event_index * 3
        data[offset] = (delay >> 8) | (0x80 if event.pressed else 0)
        data[offset + 1] = delay & 0xFF
        data[offset + 2] = event.usage

    report = bytearray(MAIN_REPORT_LENGTH)
    report[0:4] = bytes((MAIN_REPORT_ID, 0x05, 0x01, index))
    report[8:264] = data
    return bytes(report)


def custom_rgb_report(colors: Sequence[tuple[int, int, int]]) -> bytes:
    if len(colors) != 102:
        raise ValueError("custom RGB must contain exactly 102 matrix slots")
    report = bytearray(MAIN_REPORT_LENGTH)
    report[0:2] = bytes((MAIN_REPORT_ID, 0x07))
    for slot, color in enumerate(colors):
        if len(color) != 3 or any(not 0 <= channel <= 0xFF for channel in color):
            raise ValueError(f"invalid RGB color at matrix slot {slot}")
        report[8 + slot * 3 : 11 + slot * 3] = bytes(color)
    return bytes(report)


def streaming_activation_report() -> bytes:
    report = bytearray(SHORT_REPORT_LENGTH)
    report[0:2] = bytes((SHORT_REPORT_ID, 0x06))
    return bytes(report)


def streaming_rgb_reports(
    colors: Sequence[tuple[int, int, int]],
) -> tuple[bytes, ...]:
    if len(colors) != 102:
        raise ValueError("streaming RGB must contain exactly 102 matrix slots")
    data = bytearray(310)
    for slot, color in enumerate(colors):
        if len(color) != 3 or any(not 0 <= channel <= 0xFF for channel in color):
            raise ValueError(f"invalid RGB color at matrix slot {slot}")
        data[slot * 3 : slot * 3 + 3] = bytes(color)
    reports = []
    for chunk in range(5):
        report = bytearray(64)
        report[0:2] = bytes((0x06, chunk + 1))
        report[2:] = data[chunk * 62 : (chunk + 1) * 62]
        reports.append(bytes(report))
    return tuple(reports)


def debounce_report(milliseconds: int) -> bytes:
    if not 1 <= milliseconds <= 255:
        raise ValueError("debounce must be between 1 and 255 ms")
    report = bytearray(SHORT_REPORT_LENGTH)
    report[0:3] = bytes((SHORT_REPORT_ID, 0x09, milliseconds))
    return bytes(report)


def sleep_report(*, light_off_minutes: int, hibernate_minutes: int) -> bytes:
    try:
        light_index = LIGHT_OFF_MINUTES.index(light_off_minutes)
    except ValueError as error:
        raise ValueError(
            f"light-off must be one of: {', '.join(map(str, LIGHT_OFF_MINUTES))}"
        ) from error
    try:
        hibernate_index = HIBERNATE_MINUTES.index(hibernate_minutes)
    except ValueError as error:
        raise ValueError(
            f"hibernate must be one of: {', '.join(map(str, HIBERNATE_MINUTES))}"
        ) from error

    report = bytearray(SHORT_REPORT_LENGTH)
    report[0:4] = bytes((SHORT_REPORT_ID, 0x0B, light_index + 1, hibernate_index + 1))
    return bytes(report)


def reset_report() -> bytes:
    report = bytearray(SHORT_REPORT_LENGTH)
    report[0:2] = bytes((SHORT_REPORT_ID, 0x08))
    return bytes(report)
