"""Build the native desktop artifact for the current operating system."""

from __future__ import annotations

import argparse
import os
import platform
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = {
    "linux": "Spade65-Linux-x86_64.AppImage",
    "windows": "Spade65-Windows-x64.zip",
    "macos": "Spade65-macOS-universal.dmg",
}


def platform_family(value: str | None = None) -> str:
    current = value or sys.platform
    if current.startswith("linux"):
        return "linux"
    if current in {"win32", "windows"}:
        return "windows"
    if current in {"darwin", "macos"}:
        return "macos"
    raise RuntimeError(f"desktop packaging is unsupported on {current}")


def validate_architecture(family: str, machine: str | None = None) -> None:
    architecture = (machine or platform.machine()).casefold()
    if family in {"linux", "windows"} and architecture not in {
        "amd64",
        "x86_64",
    }:
        raise RuntimeError(
            f"{family} release artifact requires an x86_64 host, got {architecture}"
        )


def native_command(
    family: str,
    *,
    root: Path = ROOT,
    find_executable: Callable[[str], str | None] = shutil.which,
) -> list[str]:
    if family in {"linux", "macos"}:
        shell = find_executable("bash")
        if shell is None:
            raise RuntimeError("bash is required for this native build")
        script = "build_linux.sh" if family == "linux" else "build_macos.sh"
        return [shell, str(root / "packaging" / script)]
    if family == "windows":
        shell = find_executable("pwsh") or find_executable("powershell.exe")
        if shell is None:
            raise RuntimeError("PowerShell is required for the Windows build")
        return [
            shell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(root / "packaging" / "build_windows.ps1"),
        ]
    raise RuntimeError(f"unknown packaging platform: {family}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build the Spade65 artifact for this native OS. Windows and Linux "
            "must be x86_64; macOS produces a verified universal2 app."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the selected native command without building",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(arguments)
    family = platform_family()
    validate_architecture(family)
    command = native_command(family)
    if args.dry_run:
        print(shlex.join(command))
        return 0

    environment = os.environ.copy()
    environment["SPADE65_BUILD_PYTHON"] = sys.executable
    subprocess.run(command, cwd=ROOT, env=environment, check=True)
    artifact = ROOT / "artifacts" / ARTIFACTS[family]
    if not artifact.is_file() or artifact.stat().st_size == 0:
        raise RuntimeError(f"native build did not produce {artifact}")
    print(f"Built: {artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
