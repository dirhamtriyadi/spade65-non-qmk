"""Generate an artifact-derived legal inventory for a Linux PyInstaller build.

Official Ubuntu builds run this tool in strict dpkg mode.  Every native binary
collected from a system directory must then be owned by an installed Debian
package with an available ``/usr/share/doc/<package>/copyright`` file.  Manual
builds on other distributions remain supported: their manifest records the
exact source paths and clearly states that no dpkg attribution was possible.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import NamedTuple


NATIVE_KINDS = frozenset({"BINARY", "EXTENSION", "EXECUTABLE"})
DEFAULT_SYSTEM_ROOTS = (
    Path("/bin"),
    Path("/lib"),
    Path("/lib64"),
    Path("/sbin"),
    Path("/usr"),
)
MANIFEST_NAME = "LINUX-SYSTEM-LIBRARIES.json"
README_NAME = "README.txt"


class InventoryError(RuntimeError):
    """Raised when a strict legal inventory is incomplete."""


class CollectRecord(NamedTuple):
    bundled_path: str
    source_path: str
    kind: str


class PackageInfo(NamedTuple):
    name: str
    version: str
    copyright_path: Path | None


CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def _default_runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def load_collect_records(path: Path) -> list[CollectRecord]:
    """Load and validate the public tuple structure written by PyInstaller."""

    try:
        payload = ast.literal_eval(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError) as error:
        raise InventoryError(f"cannot read PyInstaller COLLECT table: {path}") from error

    # Current PyInstaller writes ``([records],)``.  Accept a direct record list
    # as well so the inventory is not tied to a cosmetic outer tuple.
    if (
        isinstance(payload, tuple)
        and len(payload) == 1
        and isinstance(payload[0], list)
    ):
        payload = payload[0]
    if not isinstance(payload, (list, tuple)):
        raise InventoryError(f"unexpected PyInstaller COLLECT table: {path}")

    records: list[CollectRecord] = []
    for index, entry in enumerate(payload):
        if not isinstance(entry, (list, tuple)) or len(entry) < 3:
            raise InventoryError(f"invalid COLLECT record {index}: {entry!r}")
        bundled_path, source_path, kind = entry[:3]
        if not all(isinstance(value, str) for value in (bundled_path, source_path, kind)):
            raise InventoryError(f"invalid COLLECT record {index}: {entry!r}")
        records.append(CollectRecord(bundled_path, source_path, kind))
    return records


def _is_below(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def source_origin(
    record: CollectRecord,
    *,
    project_root: Path,
    python_prefix: Path,
    system_roots: Iterable[Path] = DEFAULT_SYSTEM_ROOTS,
) -> str:
    """Classify a COLLECT source without guessing licenses from filenames."""

    source = Path(record.source_path)
    if not source.is_absolute():
        return "collected-reference"
    if _is_below(source, project_root):
        return "project-build"
    if record.kind in NATIVE_KINDS and any(
        _is_below(source, root) for root in system_roots
    ):
        return "system-native"
    if _is_below(source, python_prefix):
        return "python-environment"
    return "external-source"


def _ownership_candidates(path: Path) -> list[Path]:
    """Return merged-/usr variants which may be used by the dpkg database."""

    candidates = [path]
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        resolved = path
    if resolved not in candidates:
        candidates.append(resolved)

    for candidate in tuple(candidates):
        value = str(candidate)
        if value.startswith("/usr/"):
            legacy = Path(value[4:])
            if legacy not in candidates:
                candidates.append(legacy)
        elif value.startswith(("/bin/", "/lib/", "/lib64/", "/sbin/")):
            merged = Path("/usr" + value)
            if merged not in candidates:
                candidates.append(merged)
    return candidates


class DpkgInspector:
    """Resolve binary ownership and Debian copyright files."""

    def __init__(
        self,
        executable: str,
        *,
        runner: CommandRunner = _default_runner,
        doc_root: Path = Path("/usr/share/doc"),
    ) -> None:
        self.executable = executable
        self.runner = runner
        self.doc_root = doc_root
        self._cache: dict[Path, PackageInfo | None] = {}

    def package_for_path(self, source: Path) -> PackageInfo | None:
        if source in self._cache:
            return self._cache[source]

        owner: str | None = None
        for candidate in _ownership_candidates(source):
            result = self.runner([self.executable, "-S", str(candidate)])
            if result.returncode != 0:
                continue
            for line in result.stdout.splitlines():
                if ": " not in line:
                    continue
                package_field, _listed_path = line.split(": ", 1)
                # dpkg permits multiple owners separated by commas.  Any one
                # owning binary package provides the corresponding copyright.
                owner = package_field.split(",", 1)[0].strip()
                if owner:
                    break
            if owner:
                break

        if owner is None:
            self._cache[source] = None
            return None

        version = "unknown"
        metadata = self.runner(
            [
                self.executable,
                "-W",
                "-f=${binary:Package}\t${Version}\n",
                owner,
            ]
        )
        if metadata.returncode == 0 and metadata.stdout.strip():
            fields = metadata.stdout.strip().split("\t", 1)
            owner = fields[0]
            if len(fields) == 2 and fields[1]:
                version = fields[1]

        copyright_path = self._copyright_path(owner)
        info = PackageInfo(owner, version, copyright_path)
        self._cache[source] = info
        return info

    def _copyright_path(self, package: str) -> Path | None:
        base_name = package.split(":", 1)[0]
        direct = self.doc_root / base_name / "copyright"
        if direct.is_file():
            return direct

        listing = self.runner([self.executable, "-L", package])
        if listing.returncode != 0:
            return None
        prefix = Path("/usr/share/doc")
        for value in listing.stdout.splitlines():
            candidate = Path(value)
            if candidate.name != "copyright":
                continue
            try:
                relative = candidate.relative_to(prefix)
            except ValueError:
                continue
            local_candidate = self.doc_root / relative
            if local_candidate.is_file():
                return local_candidate
        return None


def _safe_package_filename(package: str) -> str:
    return "".join(
        character if character.isalnum() or character in ".+-" else "_"
        for character in package
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _prepare_output(directory: Path) -> Path:
    if directory.exists():
        shutil.rmtree(directory)
    copyright_directory = directory / "dpkg-copyright"
    copyright_directory.mkdir(parents=True)
    return copyright_directory


def generate_inventory(
    records: Sequence[CollectRecord],
    output_directory: Path,
    *,
    project_root: Path,
    python_prefix: Path,
    strict_dpkg: bool,
    inspector: DpkgInspector | None,
    system_roots: Iterable[Path] = DEFAULT_SYSTEM_ROOTS,
) -> dict[str, object]:
    """Write the inventory and return its serializable manifest."""

    roots = tuple(system_roots)
    copyright_directory = _prepare_output(output_directory)
    mode = (
        "strict-dpkg"
        if strict_dpkg
        else "dpkg-best-effort"
        if inspector is not None
        else "source-path-only"
    )
    issues: list[dict[str, str]] = []
    manifest_records: list[dict[str, str]] = []
    packages: dict[str, dict[str, object]] = {}
    system_binary_count = 0
    mapped_system_binary_count = 0

    for record in sorted(records, key=lambda item: (item.bundled_path, item.kind)):
        origin = source_origin(
            record,
            project_root=project_root,
            python_prefix=python_prefix,
            system_roots=roots,
        )
        manifest_record = {
            "bundled_path": record.bundled_path,
            "source_path": record.source_path,
            "kind": record.kind,
            "origin": origin,
        }
        if origin == "system-native":
            system_binary_count += 1
            info = (
                inspector.package_for_path(Path(record.source_path))
                if inspector is not None
                else None
            )
            if info is None:
                reason = (
                    "dpkg-query unavailable"
                    if inspector is None
                    else "no owning dpkg package"
                )
                manifest_record["mapping"] = "unmapped"
                issues.append(
                    {
                        "bundled_path": record.bundled_path,
                        "source_path": record.source_path,
                        "reason": reason,
                    }
                )
            elif info.copyright_path is None:
                manifest_record["mapping"] = "package-without-copyright"
                manifest_record["dpkg_package"] = info.name
                manifest_record["dpkg_version"] = info.version
                issues.append(
                    {
                        "bundled_path": record.bundled_path,
                        "source_path": record.source_path,
                        "reason": f"{info.name} has no available Debian copyright file",
                    }
                )
            else:
                mapped_system_binary_count += 1
                manifest_record["mapping"] = "dpkg"
                manifest_record["dpkg_package"] = info.name
                manifest_record["dpkg_version"] = info.version
                package = packages.get(info.name)
                if package is None:
                    copied_name = f"{_safe_package_filename(info.name)}.copyright"
                    copied_path = copyright_directory / copied_name
                    shutil.copyfile(info.copyright_path, copied_path)
                    package = {
                        "name": info.name,
                        "version": info.version,
                        "copyright_source": str(info.copyright_path),
                        "copyright_file": f"dpkg-copyright/{copied_name}",
                        "copyright_sha256": _sha256(copied_path),
                        "bundled_paths": [],
                    }
                    packages[info.name] = package
                bundled_paths = package["bundled_paths"]
                assert isinstance(bundled_paths, list)
                bundled_paths.append(record.bundled_path)
        manifest_records.append(manifest_record)

    for package in packages.values():
        bundled_paths = package["bundled_paths"]
        assert isinstance(bundled_paths, list)
        bundled_paths.sort()

    complete = not issues
    notice = (
        "Strict Ubuntu/dpkg inventory: every system-origin native binary is "
        "mapped to an installed package and copied Debian copyright file."
        if strict_dpkg
        else "Best-effort dpkg inventory; review unmapped entries before redistribution."
        if inspector is not None
        else "Source-path-only inventory generated on a non-dpkg host; package ownership "
        "and system-library license completeness have not been verified."
    )
    manifest: dict[str, object] = {
        "schema_version": 1,
        "scope": "PyInstaller COLLECT records for the Linux desktop artifact",
        "mode": mode,
        "strict_dpkg": strict_dpkg,
        "complete_system_mapping": complete,
        "notice": notice,
        "record_count": len(manifest_records),
        "system_native_binary_count": system_binary_count,
        "mapped_system_native_binary_count": mapped_system_binary_count,
        "issues": issues,
        "packages": [packages[name] for name in sorted(packages)],
        "records": manifest_records,
    }
    (output_directory / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_directory / README_NAME).write_text(
        "Linux system-library legal inventory\n"
        "====================================\n\n"
        f"Mode: {mode}\n\n"
        f"{notice}\n\n"
        "The JSON manifest is generated from PyInstaller's COLLECT table after "
        "each build. In strict Ubuntu builds, dpkg package versions and exact "
        "Debian copyright files accompany every system-origin native binary. "
        "Python-wheel and project-origin files remain covered by Spade65's "
        "static third-party notices.\n",
        encoding="utf-8",
    )

    if strict_dpkg and issues:
        details = "\n".join(
            f"- {issue['bundled_path']} <- {issue['source_path']}: {issue['reason']}"
            for issue in issues
        )
        raise InventoryError(
            "strict Linux legal inventory is incomplete:\n" + details
        )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inventory Linux binaries collected by PyInstaller"
    )
    parser.add_argument("--toc", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--strict-dpkg",
        action="store_true",
        help="fail if a system-origin native binary lacks dpkg copyright mapping",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(arguments)
    dpkg_query = shutil.which("dpkg-query")
    inspector = DpkgInspector(dpkg_query) if dpkg_query is not None else None
    if args.strict_dpkg and inspector is None:
        print(
            "strict Linux legal inventory requires dpkg-query",
            file=sys.stderr,
        )
        return 1
    try:
        records = load_collect_records(args.toc)
        manifest = generate_inventory(
            records,
            args.output_dir,
            project_root=Path(__file__).resolve().parents[1],
            python_prefix=Path(sys.prefix).resolve(),
            strict_dpkg=args.strict_dpkg,
            inspector=inspector,
        )
    except InventoryError as error:
        print(error, file=sys.stderr)
        return 1
    print(
        "Linux legal inventory: "
        f"{manifest['mapped_system_native_binary_count']}/"
        f"{manifest['system_native_binary_count']} system binaries mapped "
        f"({manifest['mode']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
