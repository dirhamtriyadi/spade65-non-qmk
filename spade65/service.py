"""Opt-in Linux application association and background RGB service."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from .effects import render_app_effects, timeline_frames
from .hidraw import (
    HidrawDevice,
    choose_device,
    discover_hidraw,
    send_feature_report,
    send_output_report,
)
from .keymap import compile_profile, load_profile
from .protocol import (
    MAIN_REPORT_ID,
    MAIN_REPORT_LENGTH,
    MAIN_USAGE,
    OUTPUT_USAGE,
    SHORT_REPORT_ID,
    SHORT_REPORT_LENGTH,
    VENDOR_ID,
    rgb_effect_report,
    streaming_activation_report,
    streaming_rgb_reports,
)


SERVICE_FORMAT = "spade65-service-v1"


def service_template() -> dict[str, object]:
    return {
        "format": SERVICE_FORMAT,
        "poll_seconds": 1.0,
        "fps": 10,
        "background_profile": None,
        "associations": [
            {"process": "example-app", "profile": "/path/to/profile.json"}
        ],
        "allow_profile_writes": False,
    }


def load_service_config(path: Path) -> dict[str, Any]:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid service JSON: {error}") from error
    if not isinstance(config, dict) or config.get("format") != SERVICE_FORMAT:
        raise ValueError(f"service config format must be {SERVICE_FORMAT}")
    associations = config.get("associations", [])
    if not isinstance(associations, list):
        raise ValueError("service associations must be an array")
    for rule in associations:
        if not isinstance(rule, dict) or not isinstance(rule.get("process"), str) or not isinstance(rule.get("profile"), str):
            raise ValueError("each association requires process and profile strings")
    fps = int(config.get("fps", 10))
    if not 1 <= fps <= 30:
        raise ValueError("service fps must be between 1 and 30")
    poll = float(config.get("poll_seconds", 1))
    if not 0.2 <= poll <= 60:
        raise ValueError("poll_seconds must be between 0.2 and 60")
    return config


def _process_name(pid: int) -> str | None:
    try:
        return (Path("/proc") / str(pid) / "comm").read_text().strip() or None
    except OSError:
        return None


def active_process_name() -> str | None:
    """Return the X11 foreground process; None on unsupported desktops."""

    if not os.environ.get("DISPLAY"):
        return None
    try:
        root = subprocess.run(
            ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
            check=True, capture_output=True, text=True, timeout=1,
        ).stdout
        window = root.rsplit(" ", 1)[-1].strip()
        if window == "0x0":
            return None
        detail = subprocess.run(
            ["xprop", "-id", window, "_NET_WM_PID"],
            check=True, capture_output=True, text=True, timeout=1,
        ).stdout
        pid = int(detail.rsplit(" ", 1)[-1])
    except (FileNotFoundError, subprocess.SubprocessError, ValueError):
        return None
    return _process_name(pid)


def running_process_names(proc_root: Path = Path("/proc")) -> set[str]:
    names = set()
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            name = (entry / "comm").read_text().strip()
        except OSError:
            continue
        if name:
            names.add(name.casefold())
    return names


def matching_rule(config: dict[str, Any]) -> dict[str, str] | None:
    foreground = active_process_name()
    associations = config.get("associations", [])
    if foreground:
        for rule in associations:
            if Path(rule["process"]).name.casefold() == foreground.casefold():
                return rule
        return None
    # Wayland has no portable active-window API. A running-process fallback is
    # deterministic and documented; rule order resolves multiple matches.
    running = running_process_names()
    for rule in associations:
        if Path(rule["process"]).name.casefold() in running:
            return rule
    return None


def _choose_main(path: Path | None) -> HidrawDevice:
    device = choose_device(
        discover_hidraw(), vendor_id=VENDOR_ID, product_ids={0x0351, 0x0356},
        usage=MAIN_USAGE, explicit_path=path,
    )
    if device.report_length("feature", MAIN_REPORT_ID) != MAIN_REPORT_LENGTH:
        raise RuntimeError("main feature descriptor does not match")
    return device


def apply_profile(profile: dict[str, Any], *, path: Path | None = None) -> None:
    compiled = compile_profile(profile)
    reports = [compiled["keymap"], *compiled["macros"]]
    if profile.get("colors"):
        reports.extend((rgb_effect_report("custom"), compiled["colors"]))
    device = _choose_main(path)
    for index, report in enumerate(reports):
        result = send_feature_report(device.path, report)
        if result != len(report):
            raise RuntimeError(f"short background profile write: {result}/{len(report)}")
        if index + 1 < len(reports):
            time.sleep(0.1)


def stream_colors(colors: dict[str, object], *, path: Path | None = None) -> None:
    profile = {
        "format": "spade65-profile-v1", "device": "0603:0351", "fn_mode_index": 0,
        "layers": {"normal": {}, "fn1": {}, "fn2": {}}, "macros": [], "colors": colors,
    }
    compiled = compile_profile(profile)
    device = choose_device(
        discover_hidraw(), vendor_id=VENDOR_ID, product_ids={0x0351},
        usage=OUTPUT_USAGE, explicit_path=path,
    )
    if device.report_length("feature", SHORT_REPORT_ID) != SHORT_REPORT_LENGTH:
        raise RuntimeError("stream activation descriptor does not match")
    if device.report_length("output", 0x06) != 64:
        raise RuntimeError("stream output descriptor does not match")
    activation = streaming_activation_report()
    if send_feature_report(device.path, activation) != len(activation):
        raise RuntimeError("short background streaming activation")
    for report in streaming_rgb_reports(compiled["matrix_colors"]):
        if send_output_report(device.path, report) != len(report):
            raise RuntimeError("short background streaming write")


class BackgroundService:
    def __init__(
        self, config_path: Path, *, allow_profile_writes: bool = False,
        device: Path | None = None, clock: Callable[[], float] = time.monotonic,
    ):
        self.config_path = config_path
        self.config = load_service_config(config_path)
        self.allow_profile_writes = allow_profile_writes
        self.device = device
        self.clock = clock
        self._active_profile_path: Path | None = None
        self._profile: dict[str, Any] | None = None
        self._timeline_index = 0
        self._timeline_deadline = 0.0
        self._phase = 0.0

    def _resolve(self, value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else self.config_path.parent / path

    def _select_profile(self) -> Path | None:
        rule = matching_rule(self.config)
        selected = rule.get("profile") if rule else self.config.get("background_profile")
        return self._resolve(selected) if isinstance(selected, str) and selected else None

    def step(self) -> str:
        selected = self._select_profile()
        if selected is None:
            self._profile = None
            self._active_profile_path = None
            return "idle"
        if selected != self._active_profile_path:
            profile = load_profile(selected)
            compile_profile(profile)
            if self.config.get("allow_profile_writes"):
                if not self.allow_profile_writes:
                    raise RuntimeError(
                        "config requests profile writes; start with --allow-profile-writes"
                    )
                apply_profile(profile, path=self.device)
            self._profile = profile
            self._active_profile_path = selected
            self._timeline_index = 0
            self._timeline_deadline = 0
            self._phase = 0
        assert self._profile is not None
        frames = timeline_frames(self._profile)
        if frames:
            now = self.clock()
            if now >= self._timeline_deadline:
                frame = frames[self._timeline_index]
                stream_colors(frame["colors"], path=self.device)
                self._timeline_deadline = now + frame["duration_ms"] / 1000
                self._timeline_index = (self._timeline_index + 1) % len(frames)
            return f"timeline:{selected.name}"
        effects = self._profile.get("settings", {}).get("app_effects", [])
        if effects:
            stream_colors(render_app_effects(self._profile, self._phase), path=self.device)
            self._phase += 1
            return f"effects:{selected.name}"
        return f"profile:{selected.name}"

    def run(self, *, once: bool = False) -> None:
        fps = int(self.config.get("fps", 10))
        poll_seconds = float(self.config.get("poll_seconds", 1))
        while True:
            status = self.step()
            if once:
                return
            streaming = status.startswith(("timeline:", "effects:"))
            time.sleep(1 / fps if streaming else poll_seconds)
