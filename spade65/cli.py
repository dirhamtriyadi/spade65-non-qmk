"""Command-line interface for Spade65 Linux configuration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .hidraw import HidrawDevice, choose_device, discover_hidraw, send_feature_report
from .protocol import (
    EFFECTS,
    HIBERNATE_MINUTES,
    LIGHT_OFF_MINUTES,
    MAIN_REPORT_ID,
    MAIN_REPORT_LENGTH,
    MAIN_USAGE,
    PRODUCT_IDS,
    SHORT_REPORT_ID,
    SHORT_REPORT_LENGTH,
    SHORT_USAGE,
    VENDOR_ID,
    debounce_report,
    reset_report,
    rgb_effect_report,
    sleep_report,
)


def _number(value: str) -> int:
    return int(value, 0)


def _device_dict(device: HidrawDevice, *, include_unique: bool = False) -> dict[str, object]:
    result: dict[str, object] = {
        "path": str(device.path),
        "vid": f"{device.vendor_id:04x}",
        "pid": f"{device.product_id:04x}",
        "transport": PRODUCT_IDS.get(device.product_id, "unknown"),
        "name": device.name,
        "usages": [f"{page:04x}:{usage:04x}" for page, usage in sorted(device.usages)],
        "reports": [
            {
                "kind": report.kind,
                "id": report.report_id,
                "bytes": report.byte_length,
            }
            for report in device.reports
        ],
        "descriptor_hex": device.descriptor.hex(),
    }
    if include_unique:
        result["unique"] = device.unique
    return result


def command_probe(args: argparse.Namespace) -> int:
    devices = [
        device
        for device in discover_hidraw()
        if device.vendor_id == VENDOR_ID and device.product_id in PRODUCT_IDS
    ]
    if args.json:
        print(
            json.dumps(
                [
                    _device_dict(device, include_unique=args.include_unique)
                    for device in devices
                ],
                indent=2,
            )
        )
    elif not devices:
        print("Spade65 tidak ditemukan (VID 0603, PID 0351/0356).")
    else:
        for device in devices:
            print(
                f"{device.path}: {device.vendor_id:04x}:{device.product_id:04x} "
                f"{PRODUCT_IDS[device.product_id]} {device.name}".rstrip()
            )
            usages = ", ".join(
                f"{page:04x}:{usage:04x}" for page, usage in sorted(device.usages)
            )
            print(f"  usages: {usages or '-'}")
            for report in device.reports:
                print(
                    f"  {report.kind} report 0x{report.report_id:02x}: "
                    f"{report.byte_length} bytes"
                )
    return 0 if devices else 2


def _print_dry_run(report: bytes, usage: tuple[int, int]) -> None:
    print(f"usage={usage[0]:04x}:{usage[1]:04x}")
    print(f"report_id=0x{report[0]:02x} length={len(report)}")
    print(f"first_64_bytes={report[:64].hex(' ')}")


def _write_report(
    args: argparse.Namespace,
    report: bytes,
    usage: tuple[int, int],
    *,
    product_ids: set[int] | None = None,
) -> int:
    if args.dry_run:
        _print_dry_run(report, usage)
        return 0
    if not args.confirm:
        raise RuntimeError("refusing to write without --confirm (use --dry-run first)")

    device = choose_device(
        discover_hidraw(),
        vendor_id=VENDOR_ID,
        product_ids=product_ids or set(PRODUCT_IDS),
        usage=usage,
        explicit_path=args.device,
    )
    expected = device.report_length("feature", report[0])
    if expected is None:
        raise RuntimeError(
            f"{device.path} does not advertise feature report 0x{report[0]:02x}"
        )
    if expected != len(report):
        raise RuntimeError(
            f"report length mismatch: descriptor says {expected}, tool expects {len(report)}"
        )
    result = send_feature_report(device.path, report)
    print(f"Terkirim ke {device.path}; ioctl result={result}.")
    return 0


def command_rgb(args: argparse.Namespace) -> int:
    report = rgb_effect_report(
        args.effect,
        brightness=args.brightness,
        speed=args.speed,
        color_index=args.color_index,
        multicolor=args.multicolor,
    )
    return _write_report(args, report, MAIN_USAGE)


def command_debounce(args: argparse.Namespace) -> int:
    return _write_report(args, debounce_report(args.milliseconds), SHORT_USAGE)


def command_sleep(args: argparse.Namespace) -> int:
    report = sleep_report(
        light_off_minutes=args.light_off,
        hibernate_minutes=args.hibernate,
    )
    return _write_report(args, report, SHORT_USAGE, product_ids={0x0356})


def command_reset(args: argparse.Namespace) -> int:
    if not args.i_understand_reset:
        raise RuntimeError("reset also requires --i-understand-reset")
    return _write_report(args, reset_report(), SHORT_USAGE)


def _add_write_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--device", type=Path, help="explicit /dev/hidrawN path")
    parser.add_argument("--dry-run", action="store_true", help="print packet; do not write")
    parser.add_argument("--confirm", action="store_true", help="allow the HID write")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spade65ctl",
        description="Experimental Linux configuration tool for the non-QMK Noir Spade65",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    probe = subparsers.add_parser("probe", help="read-only HID descriptor inspection")
    probe.add_argument("--json", action="store_true")
    probe.add_argument(
        "--include-unique",
        action="store_true",
        help="include HID serial/unique value in JSON output",
    )
    probe.set_defaults(handler=command_probe)

    rgb = subparsers.add_parser("rgb", help="set a built-in RGB effect")
    rgb.add_argument("effect", choices=sorted(EFFECTS))
    rgb.add_argument("--brightness", type=int, choices=range(0, 5), default=4)
    rgb.add_argument("--speed", type=int, choices=range(1, 6), default=5)
    rgb.add_argument("--color-index", type=int, choices=range(0, 8), default=0)
    rgb.add_argument("--multicolor", action="store_true")
    _add_write_options(rgb)
    rgb.set_defaults(handler=command_rgb)

    debounce = subparsers.add_parser("debounce", help="set debounce time in milliseconds")
    debounce.add_argument("milliseconds", type=int)
    _add_write_options(debounce)
    debounce.set_defaults(handler=command_debounce)

    sleep = subparsers.add_parser("sleep", help="set wireless light-off and sleep timers")
    sleep.add_argument("--light-off", type=int, choices=LIGHT_OFF_MINUTES, required=True)
    sleep.add_argument("--hibernate", type=int, choices=HIBERNATE_MINUTES, required=True)
    _add_write_options(sleep)
    sleep.set_defaults(handler=command_sleep)

    reset = subparsers.add_parser("reset", help="reset keyboard settings")
    reset.add_argument("--i-understand-reset", action="store_true")
    _add_write_options(reset)
    reset.set_defaults(handler=command_reset)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return int(args.handler(args))
    except (OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
