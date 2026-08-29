"""Safe cross-platform HID discovery and transport selection."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from types import ModuleType

from .device import Device, choose_device, parse_report_descriptor
from .protocol import PRODUCT_IDS, VENDOR_ID


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
    handle.open_path(path)
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
        if vendor_id != VENDOR_ID or product_id not in PRODUCT_IDS:
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


def send_feature_report(device: Device, report: bytes) -> int:
    if device.backend == "hidraw":
        from .hidraw import send_feature_report as hidraw_send_feature_report

        return hidraw_send_feature_report(device.path, report)
    handle = _open_hidapi(device)
    try:
        return int(handle.send_feature_report(report))
    finally:
        handle.close()


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
    "Device", "backend_name", "choose_device", "discover_devices",
    "discover_hidapi", "readonly_device_info", "send_feature_report",
    "send_output_report",
]
