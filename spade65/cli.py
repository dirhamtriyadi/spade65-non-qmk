"""Command-line interface for cross-platform Spade65 configuration."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import __version__
from .transport import (
    Device,
    choose_device,
    discover_devices,
    readonly_device_info,
    send_feature_report,
    send_output_report,
)
from .keymap import (
    compile_profile,
    default_keymap_report,
    export_default,
    load_profile,
    profile_template,
)
from .protocol import (
    EFFECTS,
    HIBERNATE_MINUTES,
    LIGHT_OFF_MINUTES,
    MAIN_REPORT_ID,
    MAIN_REPORT_LENGTH,
    MAIN_USAGE,
    OUTPUT_USAGE,
    PRODUCT_IDS,
    SHORT_REPORT_ID,
    SHORT_REPORT_LENGTH,
    SHORT_USAGE,
    VENDOR_ID,
    debounce_report,
    reset_report,
    rgb_effect_report,
    sleep_report,
    streaming_activation_report,
    streaming_rgb_reports,
)


def _number(value: str) -> int:
    return int(value, 0)


def _device_dict(device: Device, *, include_unique: bool = False) -> dict[str, object]:
    result: dict[str, object] = {
        "path": str(device.path),
        "backend": device.backend,
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
        for device in discover_devices()
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
        discover_devices(),
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
    result = send_feature_report(device, report)
    print(f"Terkirim ke {device.path}; transport result={result}.")
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


def command_keymap_export_default(args: argparse.Namespace) -> int:
    if args.format == "hex":
        print(default_keymap_report().hex())
    else:
        print(json.dumps(export_default(), indent=2))
    return 0


def command_profile_create(args: argparse.Namespace) -> int:
    if args.output.exists() and not args.force:
        raise RuntimeError(f"refusing to overwrite {args.output}; use --force")
    args.output.write_text(
        json.dumps(profile_template(), indent=2) + "\n", encoding="utf-8"
    )
    print(f"Profile template ditulis ke {args.output}.")
    return 0


def command_profile_validate(args: argparse.Namespace) -> int:
    data = load_profile(args.profile)
    compiled = compile_profile(data)
    print(
        f"Valid: keymap={len(compiled['keymap'])} bytes, "
        f"macros={len(compiled['macros'])}, colors={len(data.get('colors', {}))}."
    )
    return 0


def _main_device(args: argparse.Namespace) -> Device:
    device = choose_device(
        discover_devices(),
        vendor_id=VENDOR_ID,
        product_ids=set(PRODUCT_IDS),
        usage=MAIN_USAGE,
        explicit_path=args.device,
    )
    expected = device.report_length("feature", MAIN_REPORT_ID)
    if expected != MAIN_REPORT_LENGTH:
        raise RuntimeError(
            f"report length mismatch: descriptor says {expected}, tool expects "
            f"{MAIN_REPORT_LENGTH}"
        )
    return device


def _send_main_reports(device: Device, reports: list[bytes] | tuple[bytes, ...]) -> None:
    for index, report in enumerate(reports):
        result = send_feature_report(device, report)
        if result != len(report):
            raise RuntimeError(f"short feature write: {result}/{len(report)}")
        if index + 1 < len(reports):
            time.sleep(0.1)


def command_profile_apply(args: argparse.Namespace) -> int:
    data = load_profile(args.profile)
    compiled = compile_profile(data)
    reports = [compiled["keymap"], *compiled["macros"]]
    if data.get("colors"):
        reports.extend(
            (
                rgb_effect_report("custom", brightness=4, speed=5),
                compiled["colors"],
            )
        )
    if args.dry_run:
        for index, report in enumerate(reports, 1):
            print(f"report {index}/{len(reports)}")
            _print_dry_run(report, MAIN_USAGE)
        return 0
    if not args.confirm or not args.i_understand_profile_overwrite:
        raise RuntimeError(
            "profile write requires --confirm and --i-understand-profile-overwrite"
        )
    device = _main_device(args)
    _send_main_reports(device, reports)
    print(f"{len(reports)} report profil terkirim ke {device.path}.")
    return 0


def command_rgb_per_key(args: argparse.Namespace) -> int:
    data = load_profile(args.profile)
    compiled = compile_profile(data)
    reports = (
        rgb_effect_report(
            "custom", brightness=args.brightness, speed=args.speed
        ),
        compiled["colors"],
    )
    if args.dry_run:
        for report in reports:
            _print_dry_run(report, MAIN_USAGE)
        return 0
    if not args.confirm:
        raise RuntimeError("refusing to write without --confirm (use --dry-run first)")
    device = _main_device(args)
    _send_main_reports(device, reports)
    print(f"Per-key RGB terkirim ke {device.path}.")
    return 0


def command_rgb_stream(args: argparse.Namespace) -> int:
    data = load_profile(args.profile)
    compiled = compile_profile(data)
    activation = streaming_activation_report()
    chunks = streaming_rgb_reports(compiled["matrix_colors"])
    if args.dry_run:
        _print_dry_run(activation, SHORT_USAGE)
        for report in chunks:
            _print_dry_run(report, OUTPUT_USAGE)
        return 0
    if not args.confirm:
        raise RuntimeError("refusing to write without --confirm (use --dry-run first)")
    device = choose_device(
        discover_devices(),
        vendor_id=VENDOR_ID,
        product_ids={0x0351},
        usage=OUTPUT_USAGE,
        explicit_path=args.device,
    )
    if device.report_length("feature", SHORT_REPORT_ID) != SHORT_REPORT_LENGTH:
        raise RuntimeError("stream interface has no matching short feature report")
    if device.report_length("output", 0x06) != 64:
        raise RuntimeError("stream interface has no 64-byte output report 0x06")
    feature_result = send_feature_report(device, activation)
    if feature_result != len(activation):
        raise RuntimeError("short streaming activation write")
    for report in chunks:
        result = send_output_report(device, report)
        if result != len(report):
            raise RuntimeError(f"short output write: {result}/{len(report)}")
    print(f"1 frame streaming RGB terkirim ke {device.path}.")
    return 0


def command_gui(args: argparse.Namespace) -> int:
    from .gui import run_gui

    run_gui(host=args.host, port=args.port, open_browser=not args.no_browser)
    return 0


def command_info(args: argparse.Namespace) -> int:
    devices = [
        device for device in discover_devices()
        if device.vendor_id == VENDOR_ID and device.product_id in PRODUCT_IDS
    ]
    summaries = []
    seen: set[tuple[int, int, str]] = set()
    for device in devices:
        identity = (device.vendor_id, device.product_id, device.unique)
        if identity in seen:
            continue
        seen.add(identity)
        summaries.append({**_device_dict(device), **readonly_device_info(device)})
    print(json.dumps(summaries, indent=2))
    return 0 if summaries else 2


def command_vendor_import(args: argparse.Namespace) -> int:
    from .vendor import convert_vendor_file

    base = load_profile(args.base) if args.base else None
    profile, imported = convert_vendor_file(args.input, base_profile=base)
    if args.output.exists() and not args.force:
        raise RuntimeError(f"refusing to overwrite {args.output}; use --force")
    args.output.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    print(f"Imported {', '.join(imported)} into {args.output}.")
    return 0


def command_service_example(args: argparse.Namespace) -> int:
    from .service import service_template

    if args.output.exists() and not args.force:
        raise RuntimeError(f"refusing to overwrite {args.output}; use --force")
    args.output.write_text(
        json.dumps(service_template(), indent=2) + "\n", encoding="utf-8"
    )
    print(f"Service config template ditulis ke {args.output}.")
    return 0


def command_service_run(args: argparse.Namespace) -> int:
    from .service import BackgroundService

    service = BackgroundService(
        args.config,
        allow_profile_writes=args.allow_profile_writes,
        device=args.device,
    )
    service.run(once=args.once)
    return 0


def command_service_integration(args: argparse.Namespace) -> int:
    from .startup import render_startup

    if args.output.exists() and not args.force:
        raise RuntimeError(f"refusing to overwrite {args.output}; use --force")
    platform = None if args.platform == "auto" else args.platform
    args.output.write_text(
        render_startup(args.config, platform=platform), encoding="utf-8"
    )
    print(f"Background launcher ditulis ke {args.output}.")
    return 0


def _add_write_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--device", type=Path, help="explicit HID path shown by probe")
    parser.add_argument("--dry-run", action="store_true", help="print packet; do not write")
    parser.add_argument("--confirm", action="store_true", help="allow the HID write")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spade65ctl",
        description="Cross-platform configuration tool for the non-QMK Noir Spade65",
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

    info = subparsers.add_parser(
        "info", help="read-only USB revision and available battery information"
    )
    info.set_defaults(handler=command_info)

    gui = subparsers.add_parser("gui", help="launch the local graphical interface")
    gui.add_argument("--host", default="127.0.0.1")
    gui.add_argument("--port", type=int, default=8765)
    gui.add_argument("--no-browser", action="store_true")
    gui.set_defaults(handler=command_gui)

    rgb = subparsers.add_parser("rgb", help="set a built-in RGB effect")
    rgb.add_argument("effect", choices=sorted(EFFECTS))
    rgb.add_argument("--brightness", type=int, choices=range(0, 5), default=4)
    rgb.add_argument("--speed", type=int, choices=range(1, 6), default=5)
    rgb.add_argument("--color-index", type=int, choices=range(0, 8), default=0)
    rgb.add_argument("--multicolor", action="store_true")
    _add_write_options(rgb)
    rgb.set_defaults(handler=command_rgb)

    per_key = subparsers.add_parser(
        "per-key-rgb", help="apply per-key RGB from a profile"
    )
    per_key.add_argument("profile", type=Path)
    per_key.add_argument("--brightness", type=int, choices=range(0, 5), default=4)
    per_key.add_argument("--speed", type=int, choices=range(1, 6), default=5)
    _add_write_options(per_key)
    per_key.set_defaults(handler=command_rgb_per_key)

    stream = subparsers.add_parser("stream-rgb", help="send one real-time RGB frame")
    stream.add_argument("profile", type=Path)
    _add_write_options(stream)
    stream.set_defaults(handler=command_rgb_stream)

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

    keymap = subparsers.add_parser(
        "keymap", help="offline keymap inspection"
    )
    keymap_subparsers = keymap.add_subparsers(dest="keymap_command", required=True)
    export = keymap_subparsers.add_parser(
        "export-default", help="export the wired default matrix and opcode 0x03 frame"
    )
    export.add_argument("--format", choices=("json", "hex"), default="json")
    export.set_defaults(handler=command_keymap_export_default)

    profile = subparsers.add_parser(
        "profile", help="create, validate, or apply a complete configuration profile"
    )
    profile_subparsers = profile.add_subparsers(
        dest="profile_command", required=True
    )
    create = profile_subparsers.add_parser("create", help="create an editable profile")
    create.add_argument("output", type=Path)
    create.add_argument("--force", action="store_true")
    create.set_defaults(handler=command_profile_create)
    validate = profile_subparsers.add_parser(
        "validate", help="validate and compile a profile"
    )
    validate.add_argument("profile", type=Path)
    validate.set_defaults(handler=command_profile_validate)
    apply = profile_subparsers.add_parser(
        "apply", help="write keymap, macros, and optional colors"
    )
    apply.add_argument("profile", type=Path)
    apply.add_argument("--i-understand-profile-overwrite", action="store_true")
    _add_write_options(apply)
    apply.set_defaults(handler=command_profile_apply)

    vendor_import = subparsers.add_parser(
        "vendor-import", help="convert original KeyAssign/Macro/APMode JSON export"
    )
    vendor_import.add_argument("input", type=Path)
    vendor_import.add_argument("output", type=Path)
    vendor_import.add_argument("--base", type=Path, help="merge into an existing profile")
    vendor_import.add_argument("--force", action="store_true")
    vendor_import.set_defaults(handler=command_vendor_import)

    service = subparsers.add_parser(
        "service", help="background AP effects and application associations"
    )
    service_subparsers = service.add_subparsers(dest="service_command", required=True)
    service_example = service_subparsers.add_parser("example", help="write a config template")
    service_example.add_argument("output", type=Path)
    service_example.add_argument("--force", action="store_true")
    service_example.set_defaults(handler=command_service_example)
    service_run = service_subparsers.add_parser("run", help="run the background service")
    service_run.add_argument("config", type=Path)
    service_run.add_argument("--device", type=Path)
    service_run.add_argument("--once", action="store_true")
    service_run.add_argument(
        "--allow-profile-writes", action="store_true",
        help="required in addition to allow_profile_writes in config",
    )
    service_run.set_defaults(handler=command_service_run)
    service_integration = service_subparsers.add_parser(
        "integration", help="generate an OS startup launcher without installing it"
    )
    service_integration.add_argument("config", type=Path)
    service_integration.add_argument("output", type=Path)
    service_integration.add_argument(
        "--platform", choices=("auto", "linux", "windows", "macos"),
        default="auto",
    )
    service_integration.add_argument("--force", action="store_true")
    service_integration.set_defaults(handler=command_service_integration)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return int(args.handler(args))
    except (OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
