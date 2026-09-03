"""Safe cross-platform HID discovery and transport selection."""

from __future__ import annotations

import hashlib
import importlib
import os
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType

from .device import HID_BUS_BLUETOOTH, Device, choose_device, parse_report_descriptor
from .protocol import (
    OBSERVED_PRODUCT_IDS,
    VENDOR_ID,
    configuration_status,
)


BLUETOOTH_DESCRIPTOR_SHA256 = (
    "571f74c48018a34a853786c72a0a9bfe24023ffae639b2cd6b207cbd88d0d334"
)
BLUETOOTH_TRANSPORT = "Bluetooth LE"


def is_observed_bluetooth(device: Device) -> bool:
    """Match only the measured Linux Bluetooth identity, read-only."""

    return (
        device.backend == "hidraw"
        and device.bus_type == HID_BUS_BLUETOOTH
        and device.vendor_id == 0
        and device.product_id == 0
        and device.name.strip().casefold() == "spade65"
        and hashlib.sha256(device.descriptor).hexdigest()
        == BLUETOOTH_DESCRIPTOR_SHA256
    )


def observed_transport(device: Device) -> str | None:
    if (
        device.vendor_id == VENDOR_ID
        and device.product_id in OBSERVED_PRODUCT_IDS
    ):
        return OBSERVED_PRODUCT_IDS[device.product_id]
    if is_observed_bluetooth(device):
        return BLUETOOTH_TRANSPORT
    return None


def is_observed_device(device: Device) -> bool:
    return observed_transport(device) is not None


def device_configuration_status(device: Device) -> str:
    if is_observed_bluetooth(device):
        return "unsupported-read-only"
    return configuration_status(device.product_id)


def backend_name(platform: str | None = None) -> str:
    """Return the selected backend without importing optional dependencies."""

    override = os.environ.get("SPADE65_HID_BACKEND", "").strip().casefold()
    if override:
        if override not in {"hidraw", "hidapi"}:
            raise RuntimeError("SPADE65_HID_BACKEND must be hidraw or hidapi")
        return override
    return "hidraw" if (platform or sys.platform).startswith("linux") else "hidapi"


def _load_hidapi() -> ModuleType:
    try:
        return importlib.import_module("hid")
    except ImportError as error:
        raise RuntimeError(
            "HIDAPI backend is required on Windows/macOS; install with "
            "'pip install spade65-non-qmk[cross-platform]' or 'pip install hidapi'"
        ) from error


def _open_hidapi(device: Device, hid: ModuleType | None = None):
    module = hid or _load_hidapi()
    if sys.platform == "darwin" and hasattr(module, "hid_darwin_set_open_exclusive"):
        module.hid_darwin_set_open_exclusive(0)
    handle = module.device()
    path = device.hidapi_path if device.hidapi_path is not None else os.fsencode(device.path)
    try:
        handle.open_path(path)
    except BaseException:
        try:
            handle.close()
        except Exception:
            pass
        raise
    return handle


def _hidapi_descriptor(path: bytes | str, hid: ModuleType) -> bytes:
    handle = hid.device()
    try:
        handle.open_path(path)
        getter = getattr(handle, "get_report_descriptor", None)
        if getter is None:
            raise RuntimeError("installed hidapi does not expose report descriptors")
        return bytes(getter())
    finally:
        handle.close()


def discover_hidapi(hid: ModuleType | None = None) -> list[Device]:
    """Enumerate HID collections and read their descriptors through HIDAPI."""

    module = hid or _load_hidapi()
    if sys.platform == "darwin" and hasattr(module, "hid_darwin_set_open_exclusive"):
        module.hid_darwin_set_open_exclusive(0)
    devices: list[Device] = []
    for item in module.enumerate(VENDOR_ID, 0):
        try:
            vendor_id = int(item.get("vendor_id", 0))
            product_id = int(item.get("product_id", 0))
        except (TypeError, ValueError):
            continue
        if vendor_id != VENDOR_ID or product_id not in OBSERVED_PRODUCT_IDS:
            continue
        raw_path = item.get("path")
        if not raw_path:
            continue
        open_path = raw_path if isinstance(raw_path, bytes) else os.fsencode(raw_path)
        descriptor = b""
        try:
            descriptor = _hidapi_descriptor(open_path, module)
        except (OSError, RuntimeError, ValueError):
            # Read-only probe still lists an inaccessible collection. It has no
            # report shapes, so every attempted write remains descriptor-gated.
            pass
        usages, reports = parse_report_descriptor(descriptor)
        usage_page = int(item.get("usage_page", 0) or 0)
        usage = int(item.get("usage", 0) or 0)
        if usage_page or usage:
            usages.add((usage_page, usage))
        display_path = os.fsdecode(raw_path) if isinstance(raw_path, bytes) else str(raw_path)
        device = Device(
            path=Path(display_path),
            vendor_id=vendor_id,
            product_id=product_id,
            name=str(item.get("product_string") or ""),
            unique=str(item.get("serial_number") or ""),
            usages=usages,
            reports=reports,
            descriptor=descriptor,
            backend="hidapi",
            hidapi_path=open_path,
            release_number=int(item.get("release_number", 0) or 0),
            manufacturer=str(item.get("manufacturer_string") or ""),
            interface_number=int(item.get("interface_number", -1) or -1),
        )
        devices.append(device)
    return devices


def discover_devices() -> list[Device]:
    if backend_name() == "hidraw":
        from .hidraw import discover_hidraw

        return discover_hidraw()
    return discover_hidapi()


@contextmanager
def feature_report_session(
    device: Device,
) -> Iterator[Callable[[bytes], int]]:
    """Open one feature-report handle for the lifetime of a transaction."""

    if device.backend == "hidraw":
        from .hidraw import feature_report_session as hidraw_feature_session

        with hidraw_feature_session(device.path) as send:
            yield send
        return
    handle = _open_hidapi(device)
    try:
        def send(report: bytes) -> int:
            if not report:
                raise ValueError("feature report cannot be empty")
            return int(handle.send_feature_report(report))

        yield send
    finally:
        handle.close()


def send_feature_report(device: Device, report: bytes) -> int:
    with feature_report_session(device) as send:
        return send(report)


def send_output_report(device: Device, report: bytes) -> int:
    if device.backend == "hidraw":
        from .hidraw import send_output_report as hidraw_send_output_report

        return hidraw_send_output_report(device.path, report)
    handle = _open_hidapi(device)
    try:
        return int(handle.write(report))
    finally:
        handle.close()


def readonly_device_info(device: Device) -> dict[str, object | None]:
    if device.backend == "hidraw":
        from .hidraw import readonly_device_info as linux_readonly_device_info

        return linux_readonly_device_info(device)
    revision = device.release_number
    formatted_revision = (
        f"{revision >> 8:02x}.{revision & 0xff:02x}" if revision else None
    )
    return {
        "usb_revision": formatted_revision,
        "firmware_version": None,
        "firmware_status": "native vendor read method is not verified",
        "battery_percent": None,
        "battery_source": None,
        "battery_status": "not exposed by the verified read-only transport",
        "manufacturer": device.manufacturer or None,
        "interface_number": device.interface_number,
    }


__all__ = [
    "BLUETOOTH_DESCRIPTOR_SHA256", "BLUETOOTH_TRANSPORT", "Device",
    "backend_name", "choose_device", "device_configuration_status",
    "discover_devices", "discover_hidapi", "feature_report_session",
    "is_observed_bluetooth", "is_observed_device", "observed_transport",
    "readonly_device_info",
    "send_feature_report", "send_output_report",
]
