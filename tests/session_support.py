"""Test doubles for persistent feature-report transactions."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from spade65.device import Device


FeatureEffect = Callable[[Device, bytes], int]


class FeatureSessionRecorder:
    """Record reports while modelling one sender per opened HID interface."""

    def __init__(self, effect: FeatureEffect | None = None) -> None:
        self.effect = effect or (lambda _device, report: len(report))
        self.calls: list[tuple[Device, bytes]] = []
        self.opened: list[Device] = []
        self.closed: list[Device] = []
        self.events: list[tuple[str, object]] = []

    @contextmanager
    def session(self, device: Device) -> Iterator[Callable[[bytes], int]]:
        self.opened.append(device)
        self.events.append(("open", device.path))

        def send(report: bytes) -> int:
            payload = bytes(report)
            self.calls.append((device, payload))
            self.events.append(
                ("send", (device.path, payload[0], payload[1]))
            )
            return self.effect(device, payload)

        try:
            yield send
        finally:
            self.closed.append(device)
            self.events.append(("close", device.path))

    @property
    def opcodes(self) -> list[int]:
        return [report[1] for _device, report in self.calls]

    @property
    def frames(self) -> list[tuple[Path, int, int]]:
        return [
            (device.path, report[0], report[1])
            for device, report in self.calls
        ]
