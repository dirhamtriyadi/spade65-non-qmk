#!/usr/bin/env python3
"""Minimal extractor for Electron ASAR archives.

Only regular, packed files are supported. This is sufficient for the vendor
application bundled with the Spade65 configuration utility.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path, PurePosixPath


def read_archive(path: Path) -> tuple[dict, int]:
    with path.open("rb") as archive:
        prefix = archive.read(16)
        if len(prefix) != 16:
            raise ValueError("ASAR header is truncated")
        pickle_size, header_size, json_pickle_size, json_size = struct.unpack(
            "<IIII", prefix
        )
        if pickle_size != 4 or json_pickle_size + 4 != header_size:
            raise ValueError("unsupported ASAR header format")
        header = json.loads(archive.read(json_size).decode("utf-8"))
    return header, 8 + header_size


def walk_files(node: dict, prefix: PurePosixPath = PurePosixPath()) -> list[tuple[PurePosixPath, dict]]:
    entries: list[tuple[PurePosixPath, dict]] = []
    for name, metadata in node.get("files", {}).items():
        relative = prefix / name
        if "files" in metadata:
            entries.extend(walk_files(metadata, relative))
        else:
            entries.append((relative, metadata))
    return entries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--prefix",
        default="",
        help="extract only paths beginning with this archive path",
    )
    args = parser.parse_args()

    header, data_offset = read_archive(args.archive)
    wanted_prefix = PurePosixPath(args.prefix) if args.prefix else None

    with args.archive.open("rb") as archive:
        for relative, metadata in walk_files(header):
            if wanted_prefix and not relative.is_relative_to(wanted_prefix):
                continue
            if metadata.get("unpacked"):
                raise ValueError(f"unpacked file is unsupported: {relative}")
            size = int(metadata.get("size", 0))
            offset = int(metadata.get("offset", 0))
            destination = args.output.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            archive.seek(data_offset + offset)
            destination.write_bytes(archive.read(size))


if __name__ == "__main__":
    main()
