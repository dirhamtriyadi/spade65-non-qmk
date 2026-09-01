"""Vendor-compatible, descriptor-gated profile write transaction."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from contextlib import ExitStack, nullcontext
from pathlib import Path
from typing import ContextManager

from .device import Device, choose_companion_feature_device, choose_device
from .protocol import (
    MAIN_REPORT_ID,
    MAIN_REPORT_LENGTH,
    MAIN_USAGE,
    PRODUCT_IDS,
    SHORT_REPORT_ID,
    SHORT_REPORT_LENGTH,
    SHORT_USAGE,
    VENDOR_ID,
)


FeatureSender = Callable[[bytes], int]
FeatureSession = Callable[[Device], ContextManager[FeatureSender]]
Sleep = Callable[[float], object]


def choose_profile_devices(
    devices: Sequence[Device], *, explicit_path: Path | None = None
) -> tuple[Device, Device]:
    """Resolve the main collection and its short-report companion once."""

    main = choose_device(
        devices,
        vendor_id=VENDOR_ID,
        product_ids=set(PRODUCT_IDS),
        usage=MAIN_USAGE,
        explicit_path=explicit_path,
    )
    short = choose_companion_feature_device(
        devices,
        primary=main,
        usage=SHORT_USAGE,
        report_id=SHORT_REPORT_ID,
        report_length=SHORT_REPORT_LENGTH,
    )
    return main, short


def _validate_reports(
    device: Device,
    reports: Sequence[bytes],
    *,
    report_id: int,
    report_length: int,
) -> None:
    advertised = device.report_length("feature", report_id)
    if advertised != report_length:
        raise RuntimeError(
            f"report 0x{report_id:02x} mismatch on {device.path}: "
            f"descriptor={advertised}, expected={report_length}"
        )
    for report in reports:
        if not report or report[0] != report_id:
            raise RuntimeError(
                f"refusing feature report other than 0x{report_id:02x} "
                f"on {device.path}"
            )
        if len(report) != report_length:
            raise RuntimeError(
                f"invalid report 0x{report_id:02x} length: "
                f"{len(report)}/{report_length}"
            )


def _main_delay(report: bytes) -> float:
    opcode = report[1]
    if opcode == 0x05:
        return 0.2
    if opcode == 0x07:
        return 0.05
    return 0.1


def _recover_lighting(
    reports: Sequence[bytes],
    *,
    send: FeatureSender,
    sleep: Sleep,
    label: str,
) -> None:
    for index, report in enumerate(reports):
        result = send(report)
        if result != len(report):
            raise RuntimeError(
                f"short {label} on report {index + 1}/{len(reports)} "
                f"(id 0x{report[0]:02x} opcode 0x{report[1]:02x}): "
                f"{result}/{len(report)}"
            )
        sleep(_main_delay(report))


def send_profile_transaction(
    main_device: Device,
    short_device: Device,
    main_reports: Sequence[bytes],
    debounce: bytes,
    *,
    feature_session: FeatureSession,
    recovery_reports: Sequence[bytes] = (),
    sleep: Sleep = time.sleep,
    lock: ContextManager[object] | None = None,
    write_label: str = "feature write",
    recovery_label: str = "recovery write",
) -> list[int]:
    """Send one official-style keymap transaction across both HID usages.

    Both descriptors and every report are checked before opcode ``0x03`` is
    allowed onto the wire.  Main-report failures receive the existing
    best-effort lighting recovery.  A failed final debounce is reported as a
    partial transaction after best-effort restoration of the cached lighting,
    so the host does not silently retain a known-stale snapshot.
    """

    if not main_reports:
        raise ValueError("profile transaction requires at least one main report")
    _validate_reports(
        main_device,
        (*main_reports, *recovery_reports),
        report_id=MAIN_REPORT_ID,
        report_length=MAIN_REPORT_LENGTH,
    )
    _validate_reports(
        short_device,
        (debounce,),
        report_id=SHORT_REPORT_ID,
        report_length=SHORT_REPORT_LENGTH,
    )

    results: list[int] = []
    transaction = lock if lock is not None else nullcontext()
    with transaction:
        with ExitStack() as stack:
            # Open both verified interfaces before opcode 0x03.  A permission
            # or open failure on the short companion therefore cannot leave a
            # partially written keymap.  Separate handles mirror the vendor
            # backend even when both report IDs share one OS device path.
            send_main = stack.enter_context(feature_session(main_device))
            send_short = stack.enter_context(feature_session(short_device))
            for index, report in enumerate(main_reports):
                try:
                    result = send_main(report)
                    if result != len(report):
                        raise RuntimeError(
                            f"short {write_label} on report "
                            f"{index + 1}/{len(main_reports)} "
                            f"(id 0x{report[0]:02x} opcode 0x{report[1]:02x}): "
                            f"{result}/{len(report)}"
                        )
                except Exception as error:
                    if not recovery_reports:
                        raise
                    try:
                        _recover_lighting(
                            recovery_reports,
                            send=send_main,
                            sleep=sleep,
                            label=recovery_label,
                        )
                    except Exception as recovery_error:
                        raise RuntimeError(
                            f"{error}; cached lighting recovery also failed: "
                            f"{recovery_error}"
                        ) from error
                    raise RuntimeError(
                        f"{error}; cached lighting recovery succeeded"
                    ) from error
                results.append(result)
                # The official SetKeyMatrix sequence also waits after the
                # final lighting frame before using the short-report handle.
                sleep(_main_delay(report))

            try:
                result = send_short(debounce)
                if result != len(debounce):
                    raise RuntimeError(
                        f"short profile debounce write "
                        f"(id 0x{debounce[0]:02x} opcode 0x{debounce[1]:02x}): "
                        f"{result}/{len(debounce)}"
                    )
            except Exception as error:
                partial = (
                    "keymap and lighting reports succeeded, but the final "
                    f"debounce report on {short_device.path} failed: {error}"
                )
                if not recovery_reports:
                    raise RuntimeError(partial) from error
                try:
                    _recover_lighting(
                        recovery_reports,
                        send=send_main,
                        sleep=sleep,
                        label=recovery_label,
                    )
                except Exception as recovery_error:
                    raise RuntimeError(
                        f"{partial}; cached lighting recovery also failed: "
                        f"{recovery_error}"
                    ) from error
                raise RuntimeError(
                    f"{partial}; cached lighting recovery succeeded"
                ) from error
            results.append(result)
            sleep(0.01)
    return results


__all__ = ["choose_profile_devices", "send_profile_transaction"]
