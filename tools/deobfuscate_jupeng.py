#!/usr/bin/env python3
"""Resolve the rotated string table in the vendor's JupengSeries module."""

from __future__ import annotations

import argparse
import ast
import json
import math
import re
from pathlib import Path


BASE_INDEX = 0x6A
TARGET = 0x89C67


def javascript_parse_int(value: str) -> float | int:
    match = re.match(r"\s*([+-]?\d+)", value)
    return int(match.group(1)) if match else math.nan


def rotation_expression(table: list[str]) -> float:
    def value(index: int) -> float | int:
        return javascript_parse_int(table[index - BASE_INDEX])

    return (
        -value(0xAD)
        - value(0x112) / 2 * (value(0xB7) / 3)
        + value(0x13D) / 4
        - value(0x71) / 5
        - value(0xD8) / 6
        + value(0xC6) / 7 * (-value(0x77) / 8)
        + value(0xB6) / 9
    )


def decode(source: str) -> str:
    table_match = re.search(
        r"var _0xd85c78=\[(.*?)\];_0x12fa=function", source, re.DOTALL
    )
    if not table_match:
        raise ValueError("JupengSeries string table was not found")
    table = ast.literal_eval("[" + table_match.group(1) + "]")

    for _ in range(len(table)):
        if rotation_expression(table) == TARGET:
            break
        table.append(table.pop(0))
    else:
        raise ValueError("could not resolve string-table rotation")

    aliases = {"_0x155b18", "_0x144b"}
    assignments = re.findall(
        r"\b(_0x[0-9a-f]+)\s*=\s*(_0x[0-9a-f]+)\b", source
    )
    changed = True
    while changed:
        changed = False
        for left, right in assignments:
            if right in aliases and left not in aliases:
                aliases.add(left)
                changed = True
    call = re.compile(
        rf"\b(?:{'|'.join(map(re.escape, sorted(aliases, key=len, reverse=True)))})"
        r"\((0x[0-9a-f]+)\)"
    )

    def substitute(match: re.Match[str]) -> str:
        index = int(match.group(1), 16) - BASE_INDEX
        if index < 0 or index >= len(table):
            return match.group(0)
        return json.dumps(table[index], ensure_ascii=False)

    return call.sub(substitute, source)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(decode(args.source.read_text()), encoding="utf-8")


if __name__ == "__main__":
    main()
