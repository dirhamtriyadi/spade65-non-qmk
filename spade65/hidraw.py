"""Dependency-free Linux hidraw discovery and feature-report transport."""

from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from .device import (
    HID_BUS_BLUETOOTH,
    Device,
    ReportShape,
    choose_device,
    parse_report_descriptor,
)


HidrawDevice = Device

_BLUEZ_BATTERY_CACHE_SECONDS = 30.0
_BLUEZ_BATTERY_CACHE: dict[str, tuple[float, int | None]] = {}
_BLUEZ_BATTERY_LOCK = threading.Lock()
_BLUETOOTH_ADDRESS = re.compile(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}")


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
            bus_type = int(hid_id[0], 16)
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
                bus_type=bus_type,
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


def _clean_environment() -> dict[str, str]:
    """Environment for a host tool: the host's libraries and a stable locale.

    An AppImage puts its own libraries on LD_LIBRARY_PATH, which makes host
    binaries fail to start, so restore what the launcher saved. The C locale
    keeps any text output parseable.
    """

    environment = dict(os.environ)
    original_library_path = environment.pop("LD_LIBRARY_PATH_ORIG", None)
    if original_library_path:
        environment["LD_LIBRARY_PATH"] = original_library_path
    else:
        environment.pop("LD_LIBRARY_PATH", None)
    environment["LC_ALL"] = "C"
    environment["LANG"] = "C"
    return environment


def _bluez_battery_percent(address: str) -> int | None:
    """Read BlueZ Battery1 through its standard CLI, with a short-lived cache."""

    if _BLUETOOTH_ADDRESS.fullmatch(address) is None:
        return None
    normalized = address.upper()
    now = time.monotonic()
    with _BLUEZ_BATTERY_LOCK:
        cached = _BLUEZ_BATTERY_CACHE.get(normalized)
        if cached is not None and now - cached[0] < _BLUEZ_BATTERY_CACHE_SECONDS:
            return cached[1]

        environment = _clean_environment()
        executable = shutil.which("bluetoothctl", path=environment.get("PATH"))
        battery = None
        if executable is not None:
            try:
                result = subprocess.run(
                    [executable, "--timeout", "2", "info", normalized],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=3,
                    env=environment,
                )
                match = re.search(
                    r"(?m)^\s*Battery Percentage:\s+0x[0-9a-fA-F]+\s+"
                    r"\(([0-9]{1,3})\)\s*$",
                    result.stdout,
                )
                if match is not None:
                    measured = int(match.group(1))
                    if 0 <= measured <= 100:
                        battery = measured
            except (OSError, subprocess.SubprocessError):
                pass
        _BLUEZ_BATTERY_CACHE[normalized] = (now, battery)
        return battery


# Assigned number 0x2A19, the standard Bluetooth Battery Level characteristic.
BATTERY_LEVEL_UUID = "00002a19-0000-1000-8000-00805f9b34fb"


def _busctl(arguments: list[str]) -> str | None:
    """Run one busctl call and return stdout, or None if it did not succeed."""

    environment = _clean_environment()
    executable = shutil.which("busctl", path=environment.get("PATH"))
    if executable is None:
        return None
    try:
        result = subprocess.run(
            [executable, "--system", *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout if result.returncode == 0 else None


def _busctl_json(arguments: list[str]) -> object | None:
    output = _busctl(["--json=short", *arguments])
    if not output:
        return None
    try:
        return json.loads(output)
    except ValueError:
        return None


def _percentage(value: object) -> int | None:
    return value if isinstance(value, int) and 0 <= value <= 100 else None


def bluez_battery_probe(address: str | None) -> dict[str, object | None]:
    """Compare the battery level BlueZ has cached against a fresh read.

    BlueZ publishes org.bluez.Battery1.Percentage from the last value the
    keyboard notified, so a keyboard that never notifies leaves it frozen at
    whatever it reported when the link came up. Reading the GATT
    characteristic asks the keyboard for the value now. Both are reads; this
    never writes to the device.

    The shapes used here are the ones busctl was observed to emit: `tree
    --list` prints one object path per line, and `--json=short` wraps a value
    as {"type": ..., "data": ...}.
    """

    result: dict[str, object | None] = {
        "device_path": None,
        "characteristic": None,
        "cached_percent": None,
        "fresh_percent": None,
        "differs": False,
        "note": None,
    }
    if not address or _BLUETOOTH_ADDRESS.fullmatch(address) is None:
        result["note"] = "no usable Bluetooth address to look up"
        return result

    tree = _busctl(["tree", "--list", "org.bluez"])
    if tree is None:
        result["note"] = "busctl is unavailable or org.bluez is not running"
        return result

    wanted = "dev_" + address.strip().upper().replace(":", "_")
    paths = [line.strip() for line in tree.splitlines() if line.strip()]
    devices = [path for path in paths if path.rsplit("/", 1)[-1] == wanted]
    if not devices:
        result["note"] = f"no BlueZ device object for {address}"
        return result
    device_path = devices[0]
    result["device_path"] = device_path

    cached = _busctl_json(
        ["get-property", "org.bluez", device_path, "org.bluez.Battery1", "Percentage"]
    )
    if isinstance(cached, dict):
        result["cached_percent"] = _percentage(cached.get("data"))

    prefix = device_path + "/"
    for path in paths:
        if not path.startswith(prefix):
            continue
        uuid = _busctl_json(
            [
                "get-property",
                "org.bluez",
                path,
                "org.bluez.GattCharacteristic1",
                "UUID",
            ]
        )
        if not isinstance(uuid, dict):
            continue
        if str(uuid.get("data", "")).lower() != BATTERY_LEVEL_UUID:
            continue
        result["characteristic"] = path
        # ReadValue takes an options dictionary; an empty one is the plain
        # read. Nothing in this project ever calls WriteValue.
        value = _busctl_json(
            [
                "call",
                "org.bluez",
                path,
                "org.bluez.GattCharacteristic1",
                "ReadValue",
                "a{sv}",
                "0",
            ]
        )
        if isinstance(value, dict):
            data = value.get("data")
            # A byte array arrives as a list; some builds nest it one deeper.
            while isinstance(data, list) and len(data) == 1 and isinstance(data[0], list):
                data = data[0]
            if isinstance(data, list) and data:
                result["fresh_percent"] = _percentage(data[0])
        break

    if result["characteristic"] is None:
        result["note"] = "the device exposes no battery level characteristic"
    cached_percent, fresh_percent = result["cached_percent"], result["fresh_percent"]
    result["differs"] = (
        isinstance(cached_percent, int)
        and isinstance(fresh_percent, int)
        and cached_percent != fresh_percent
    )
    return result


def readonly_device_info(device: HidrawDevice) -> dict[str, object | None]:
    """Read host metadata and available battery data without sending HID data."""

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
    if battery is None and device.bus_type == HID_BUS_BLUETOOTH:
        battery = _bluez_battery_percent(device.unique)
        if battery is not None:
            battery_source = "BlueZ Battery1"
    return {
        "usb_revision": revision,
        # The vendor calls a closed native GetFWVersion function. bcdDevice is
        # exposed separately and is deliberately not mislabeled as firmware.
        "firmware_version": None,
        "firmware_status": "native vendor read method is not verified",
        "battery_percent": battery,
        "battery_source": battery_source,
        "battery_status": (
            (
                "reported by BlueZ Battery1"
                if battery_source == "BlueZ Battery1"
                else "reported by Linux power_supply"
            )
            if battery is not None
            else "not exposed by the current transport/kernel"
        ),
    }
