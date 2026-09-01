"""Dependency-free Linux hidraw discovery and feature-report transport."""

from __future__ import annotations

import fcntl
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from .device import Device, ReportShape, choose_device, parse_report_descriptor


HidrawDevice = Device


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
                sysfs_path=device_path.resolve(),
            )
        )
    return devices


def _ioc(direction: int, ioctl_type: int, number: int, size: int) -> int:
    return (direction << 30) | (ioctl_type << 8) | number | (size << 16)


def hid_iocsfeature(length: int) -> int:
    if not 1 <= length < (1 << 14):
        raise ValueError("invalid HID feature report length")
    return _ioc(3, ord("H"), 0x06, length)


@contextmanager
def feature_report_session(path: Path) -> Iterator[Callable[[bytes], int]]:
    """Keep one hidraw descriptor open for a multi-report transaction."""

    descriptor = os.open(path, os.O_RDWR | os.O_CLOEXEC)
    try:
        def send(report: bytes) -> int:
            if not report:
                raise ValueError("feature report cannot be empty")
            mutable_report = bytearray(report)
            return int(
                fcntl.ioctl(
                    descriptor,
                    hid_iocsfeature(len(mutable_report)),
                    mutable_report,
                    True,
                )
            )

        yield send
    finally:
        os.close(descriptor)


def send_feature_report(path: Path, report: bytes) -> int:
    with feature_report_session(path) as send:
        return send(report)


def send_output_report(path: Path, report: bytes) -> int:
    if not report:
        raise ValueError("output report cannot be empty")
    descriptor = os.open(path, os.O_WRONLY | os.O_CLOEXEC)
    try:
        result = os.write(descriptor, report)
    finally:
        os.close(descriptor)
    return result


def _read_text(path: Path) -> str | None:
    try:
        value = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    return value or None


def readonly_device_info(device: HidrawDevice) -> dict[str, object | None]:
    """Read USB metadata and a kernel-exported battery without sending HID data."""

    usb_parent = None
    current = device.sysfs_path
    while current is not None and current != current.parent:
        if _read_text(current / "idVendor") and _read_text(current / "idProduct"):
            usb_parent = current
            break
        current = current.parent
    revision = _read_text(usb_parent / "bcdDevice") if usb_parent else None
    if revision and len(revision) == 4:
        revision = f"{revision[:2]}.{revision[2:]}"

    battery = None
    battery_source = None
    power_supply = Path("/sys/class/power_supply")
    if usb_parent and power_supply.exists():
        for candidate in power_supply.iterdir():
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            if usb_parent in resolved.parents:
                capacity = _read_text(candidate / "capacity")
                if capacity and capacity.isdigit():
                    battery = int(capacity)
                    battery_source = candidate.name
                    break
    return {
        "usb_revision": revision,
        # The vendor calls a closed native GetFWVersion function. bcdDevice is
        # exposed separately and is deliberately not mislabeled as firmware.
        "firmware_version": None,
        "firmware_status": "native vendor read method is not verified",
        "battery_percent": battery,
        "battery_source": battery_source,
        "battery_status": (
            "reported by Linux power_supply" if battery is not None
            else "not exposed by the current transport/kernel"
        ),
    }
