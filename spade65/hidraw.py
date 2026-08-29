"""Dependency-free Linux hidraw discovery and feature-report transport."""

from __future__ import annotations

import fcntl
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ReportShape:
    kind: str
    report_id: int
    bits: int

    @property
    def byte_length(self) -> int:
        return (self.bits + 7) // 8 + (1 if self.report_id else 0)


@dataclass
class HidrawDevice:
    path: Path
    vendor_id: int
    product_id: int
    name: str = ""
    unique: str = ""
    usages: set[tuple[int, int]] = field(default_factory=set)
    reports: list[ReportShape] = field(default_factory=list)
    descriptor: bytes = b""

    def report_length(self, kind: str, report_id: int) -> int | None:
        matches = [
            report.byte_length
            for report in self.reports
            if report.kind == kind and report.report_id == report_id
        ]
        return max(matches) if matches else None


def _unsigned(data: bytes) -> int:
    return int.from_bytes(data, "little", signed=False)


def parse_report_descriptor(
    descriptor: bytes,
) -> tuple[set[tuple[int, int]], list[ReportShape]]:
    usages: set[tuple[int, int]] = set()
    report_bits: dict[tuple[str, int], int] = {}
    globals_state = {
        "usage_page": 0,
        "report_size": 0,
        "report_count": 0,
        "report_id": 0,
    }
    globals_stack: list[dict[str, int]] = []
    local_usages: list[int] = []
    offset = 0

    while offset < len(descriptor):
        prefix = descriptor[offset]
        offset += 1
        if prefix == 0xFE:
            if offset + 2 > len(descriptor):
                break
            size = descriptor[offset]
            offset += 2 + size
            continue

        size_code = prefix & 0x03
        size = 4 if size_code == 3 else size_code
        item_type = (prefix >> 2) & 0x03
        tag = (prefix >> 4) & 0x0F
        data = descriptor[offset : offset + size]
        offset += size
        value = _unsigned(data)

        if item_type == 1:  # Global item.
            if tag == 0:
                globals_state["usage_page"] = value
            elif tag == 7:
                globals_state["report_size"] = value
            elif tag == 8:
                globals_state["report_id"] = value
            elif tag == 9:
                globals_state["report_count"] = value
            elif tag == 10:
                globals_stack.append(globals_state.copy())
            elif tag == 11 and globals_stack:
                globals_state = globals_stack.pop()
        elif item_type == 2:  # Local item.
            if tag == 0:
                if size > 2:
                    usages.add(((value >> 16) & 0xFFFF, value & 0xFFFF))
                else:
                    local_usages.append(value)
                    usages.add((globals_state["usage_page"], value))
        elif item_type == 0:  # Main item.
            kind = {8: "input", 9: "output", 11: "feature"}.get(tag)
            if kind:
                key = (kind, globals_state["report_id"])
                bits = globals_state["report_size"] * globals_state["report_count"]
                report_bits[key] = report_bits.get(key, 0) + bits
            local_usages.clear()

    reports = [
        ReportShape(kind=kind, report_id=report_id, bits=bits)
        for (kind, report_id), bits in sorted(report_bits.items())
    ]
    return usages, reports


def _parse_uevent(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return values
    for line in lines:
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    return values


def discover_hidraw(sys_class: Path = Path("/sys/class/hidraw")) -> list[HidrawDevice]:
    devices: list[HidrawDevice] = []
    if not sys_class.exists():
        return devices
    for entry in sorted(sys_class.glob("hidraw*")):
        device_path = entry / "device"
        uevent = _parse_uevent(device_path / "uevent")
        hid_id = uevent.get("HID_ID", "").split(":")
        if len(hid_id) != 3:
            continue
        try:
            vendor_id = int(hid_id[1], 16)
            product_id = int(hid_id[2], 16)
        except ValueError:
            continue
        try:
            descriptor = (device_path / "report_descriptor").read_bytes()
        except OSError:
            descriptor = b""
        usages, reports = parse_report_descriptor(descriptor)
        devices.append(
            HidrawDevice(
                path=Path("/dev") / entry.name,
                vendor_id=vendor_id,
                product_id=product_id,
                name=uevent.get("HID_NAME", ""),
                unique=uevent.get("HID_UNIQ", ""),
                usages=usages,
                reports=reports,
                descriptor=descriptor,
            )
        )
    return devices


def choose_device(
    devices: Iterable[HidrawDevice],
    *,
    vendor_id: int,
    product_ids: set[int],
    usage: tuple[int, int],
    explicit_path: Path | None = None,
) -> HidrawDevice:
    matches = [
        device
        for device in devices
        if device.vendor_id == vendor_id
        and device.product_id in product_ids
        and usage in device.usages
        and (explicit_path is None or device.path == explicit_path)
    ]
    if not matches:
        path_hint = f" at {explicit_path}" if explicit_path else ""
        raise RuntimeError(
            f"no matching hidraw interface{path_hint} for usage "
            f"{usage[0]:04x}:{usage[1]:04x}"
        )
    if len(matches) > 1:
        paths = ", ".join(str(device.path) for device in matches)
        raise RuntimeError(f"multiple matching interfaces ({paths}); use --device")
    return matches[0]


def _ioc(direction: int, ioctl_type: int, number: int, size: int) -> int:
    return (direction << 30) | (ioctl_type << 8) | number | (size << 16)


def hid_iocsfeature(length: int) -> int:
    if not 1 <= length < (1 << 14):
        raise ValueError("invalid HID feature report length")
    return _ioc(3, ord("H"), 0x06, length)


def send_feature_report(path: Path, report: bytes) -> int:
    if not report:
        raise ValueError("feature report cannot be empty")
    mutable_report = bytearray(report)
    descriptor = os.open(path, os.O_RDWR | os.O_CLOEXEC)
    try:
        result = fcntl.ioctl(
            descriptor,
            hid_iocsfeature(len(mutable_report)),
            mutable_report,
            True,
        )
    finally:
        os.close(descriptor)
    return int(result)


def send_output_report(path: Path, report: bytes) -> int:
    if not report:
        raise ValueError("output report cannot be empty")
    descriptor = os.open(path, os.O_WRONLY | os.O_CLOEXEC)
    try:
        result = os.write(descriptor, report)
    finally:
        os.close(descriptor)
    return result
