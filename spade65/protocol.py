"""Packets recovered from the official Spade65 Windows application."""

from __future__ import annotations


VENDOR_ID = 0x0603
PRODUCT_IDS = {
    0x0351: "USB",
    0x0356: "Dongle",
}

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
