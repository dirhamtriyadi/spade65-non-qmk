"""Operating-system-neutral HID descriptor model and device selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


HID_BUS_BLUETOOTH = 0x0005


@dataclass(frozen=True)
class ReportShape:
    kind: str
    report_id: int
    bits: int

    @property
    def byte_length(self) -> int:
        return (self.bits + 7) // 8 + (1 if self.report_id else 0)


@dataclass
class Device:
    path: Path
    vendor_id: int
    product_id: int
    name: str = ""
    unique: str = ""
    usages: set[tuple[int, int]] = field(default_factory=set)
    reports: list[ReportShape] = field(default_factory=list)
    descriptor: bytes = b""
    sysfs_path: Path | None = None
    bus_type: int = 0
    backend: str = "hidraw"
    hidapi_path: bytes | str | None = None
    release_number: int = 0
    manufacturer: str = ""
    interface_number: int = -1

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
        if item_type == 1:
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
        elif item_type == 2 and tag == 0:
            if size > 2:
                usages.add(((value >> 16) & 0xFFFF, value & 0xFFFF))
            else:
                local_usages.append(value)
                usages.add((globals_state["usage_page"], value))
        elif item_type == 0:
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


def choose_device(
    devices: Iterable[Device], *, vendor_id: int, product_ids: set[int],
    usage: tuple[int, int], explicit_path: Path | None = None,
) -> Device:
    matches = [
        device for device in devices
        if device.vendor_id == vendor_id
        and device.product_id in product_ids
        and usage in device.usages
        and (explicit_path is None or device.path == explicit_path)
    ]
    if not matches:
        path_hint = f" at {explicit_path}" if explicit_path else ""
        raise RuntimeError(
            f"no matching HID interface{path_hint} for usage "
            f"{usage[0]:04x}:{usage[1]:04x}"
        )
    if len(matches) > 1:
        paths = ", ".join(str(device.path) for device in matches)
        raise RuntimeError(f"multiple matching interfaces ({paths}); use --device")
    return matches[0]


def choose_companion_feature_device(
    devices: Iterable[Device],
    *,
    primary: Device,
    usage: tuple[int, int],
    report_id: int,
    report_length: int,
) -> Device:
    """Select a fail-closed feature-report companion for ``primary``.

    Some operating systems expose the main and short Spade65 reports on one
    HID collection, while others may enumerate separate collections.  Reuse a
    combined collection when possible.  Otherwise accept only one companion
    with the same VID/PID and the same serial/unique identity (including both
    identities being empty).  Never guess between multiple physical keyboards.
    """

    def compatible(device: Device) -> bool:
        return (
            device.vendor_id == primary.vendor_id
            and device.product_id == primary.product_id
            and usage in device.usages
            and device.report_length("feature", report_id) == report_length
        )

    if compatible(primary):
        return primary

    candidates = [device for device in devices if compatible(device)]
    # An absent serial is identity information too: never pair an anonymous
    # main collection with a short collection that explicitly belongs to some
    # other serial-numbered device.
    candidates = [
        device for device in candidates if device.unique == primary.unique
    ]
    if not candidates:
        raise RuntimeError(
            "no matching companion HID interface for usage "
            f"{usage[0]:04x}:{usage[1]:04x}, feature report "
            f"0x{report_id:02x}/{report_length} bytes"
        )
    if len(candidates) > 1:
        paths = ", ".join(str(device.path) for device in candidates)
        raise RuntimeError(
            f"multiple matching companion interfaces ({paths}); "
            "disconnect the other keyboard before applying a profile"
        )
    return candidates[0]
