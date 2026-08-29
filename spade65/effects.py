"""Host-side AP effects and custom timeline rendering."""

from __future__ import annotations

import math
import random
from typing import Any


KEY_ROWS = (
    ("esc", "n1", "n2", "n3", "n4", "n5", "n6", "n7", "n8", "n9", "n0", "minus", "plus", "bksp"),
    ("tab", "q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "lqu", "rqu", "k29", "delete"),
    ("caps", "a", "s", "d", "f", "g", "h", "j", "k", "l", "sem", "quo", "k42", "enter", "pageup"),
    ("lshift", "z", "x", "c", "v", "b", "n", "m", "comma", "dot", "qmark", "rshift", "up", "pagedown"),
    ("lctrl", "win", "lalt", "lspace", "ralt", "mspace", "rspace", "fn", "rctrl", "left", "down", "right"),
)


def _rgb(value: str) -> tuple[int, int, int]:
    encoded = value.removeprefix("#")
    if len(encoded) != 6:
        return (0, 0, 0)
    try:
        return tuple(bytes.fromhex(encoded))  # type: ignore[return-value]
    except ValueError:
        return (0, 0, 0)


def _palette(colors: object, position: float, gradient: bool) -> tuple[int, int, int]:
    palette = [_rgb(value) for value in colors if isinstance(value, str)] if isinstance(colors, list) else []
    if not palette:
        palette = [(255, 0, 0)]
    if not gradient or len(palette) == 1:
        return palette[0]
    scaled = (position % 1.0) * (len(palette) - 1)
    index = int(scaled)
    amount = scaled - index
    following = min(index + 1, len(palette) - 1)
    return tuple(
        round(value + (palette[following][channel] - value) * amount)
        for channel, value in enumerate(palette[index])
    )  # type: ignore[return-value]


def _blend(
    base: tuple[int, int, int], top: tuple[int, int, int], alpha: float
) -> tuple[int, int, int]:
    alpha = max(0.0, min(1.0, alpha))
    return tuple(round(value * (1 - alpha) + top[index] * alpha) for index, value in enumerate(base))  # type: ignore[return-value]


def _layer_pixel(
    layer: dict[str, Any], key: str, x: int, y: int, index: int, phase: float,
    *, audio_level: float, randomizer: random.Random,
) -> tuple[tuple[int, int, int], float] | None:
    keys = layer.get("keys", [])
    if layer.get("enabled", True) is False or (isinstance(keys, list) and keys and key not in keys):
        return None
    speed = float(layer.get("speed", 5))
    motion = phase * speed
    direction = -1 if layer.get("reverse") else 1
    if layer.get("bidirectional") and y % 2:
        direction *= -1
    dx = x - 6.5 - float(layer.get("center_x", 0))
    dy = y - 2 - float(layer.get("center_y", 0))
    angle = (math.degrees(math.atan2(dy, dx)) + 360 + float(layer.get("angle", 0))) % 360
    distance = math.hypot(dx, dy)
    band = 200 / max(50, float(layer.get("bandwidth", 200)))
    gap = float(layer.get("gap", 0)) / 100
    density = max(1, float(layer.get("number", 5)))
    mode = str(layer.get("mode", "wave"))
    position = 0.95
    light = 1.0
    if mode == "wave":
        position = (math.sin(x * band + direction * motion / 8 + gap) + 1) / 2
    elif mode == "conic":
        position = ((angle + direction * motion * 2) % 360) / 360
    elif mode == "spiral":
        position = ((angle + distance * 35 * band + direction * motion * 2) % 360) / 360
    elif mode == "cycle":
        position = (index / 70 + direction * motion / 120) % 1
    elif mode == "linear-wave":
        position = (x * band / 8 + y / 14 + float(layer.get("angle", 0)) / 360 + direction * motion / 100 + gap) % 1
    elif mode == "ripple":
        position = (distance * band / 5 - direction * motion / 80 + gap) % 1
    elif mode == "breathe":
        position = 0
        light = 0.25 + 0.75 * (1 + math.sin(motion / 18)) / 2
    elif mode == "rain":
        position = 0.55
        light = 1 if (x * 19 + y * 37 + direction * motion * density) % 100 > 100 - density * 6 else 0.08
    elif mode == "fire":
        position = randomizer.random() * 0.14
        light = 0.25 + randomizer.random() * 0.06 * max(1, float(layer.get("fire", 1)))
    elif mode == "trigger":
        position = 0.95
        light = 1 if (index * 31 + motion * 3) % 97 > 90 else 0.08
    if layer.get("bump"):
        light *= 1 - abs((position % 1) * 2 - 1)
    if layer.get("audio"):
        light *= min(1, audio_level * 4)
    color = _palette(layer.get("colors"), position, bool(layer.get("gradient", True)))
    alpha = float(layer.get("opacity", 100)) / 100 * light
    return color, alpha


def render_app_effects(
    profile: dict[str, Any], phase: float, *, audio_level: float = 0
) -> dict[str, str]:
    """Render one deterministic RGB frame from profile.settings.app_effects."""

    settings = profile.get("settings", {})
    layers = settings.get("app_effects", []) if isinstance(settings, dict) else []
    if not isinstance(layers, list):
        layers = []
    output: dict[str, str] = {}
    index = 0
    randomizer = random.Random(round(phase * 1000))
    for y, row in enumerate(KEY_ROWS):
        for x, key in enumerate(row):
            color = (0, 0, 0)
            for layer in layers[:10]:
                if not isinstance(layer, dict):
                    continue
                pixel = _layer_pixel(
                    layer, key, x, y, index, phase,
                    audio_level=audio_level, randomizer=randomizer,
                )
                if pixel:
                    color = _blend(color, pixel[0], pixel[1])
            output[key] = "#" + "".join(f"{channel:02x}" for channel in color)
            index += 1
    return output


def timeline_frames(profile: dict[str, Any]) -> list[dict[str, Any]]:
    settings = profile.get("settings", {})
    timeline = settings.get("custom_timeline", {}) if isinstance(settings, dict) else {}
    frames = timeline.get("frames", []) if isinstance(timeline, dict) else []
    result = []
    for frame in frames[:200] if isinstance(frames, list) else []:
        if not isinstance(frame, dict) or not isinstance(frame.get("colors"), dict):
            continue
        result.append({
            "duration_ms": min(60_000, max(20, int(frame.get("duration_ms", 100)))),
            "colors": frame["colors"],
        })
    return result
