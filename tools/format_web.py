#!/usr/bin/env python3
"""Format the canonical JavaScript and CSS sources used by the GUI."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

try:
    import cssbeautifier
    import jsbeautifier
except ImportError as exc:  # pragma: no cover - exercised before dev setup
    raise SystemExit(
        'Web formatter dependencies are missing. Run: '
        'python -m pip install -e ".[dev]"'
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "spade65" / "web"
JS_FILES = tuple(sorted(WEB_ROOT.glob("*.js")))
CSS_FILES = tuple(sorted(WEB_ROOT.glob("*.css")))


def format_javascript(source: str) -> str:
    options = jsbeautifier.default_options()
    options.indent_size = 2
    options.eol = "\n"
    options.end_with_newline = True
    options.max_preserve_newlines = 2
    options.space_after_anon_function = True
    return jsbeautifier.beautify(source, options)


def format_css(source: str) -> str:
    options = cssbeautifier.default_options()
    options.indent_size = 2
    options.eol = "\n"
    options.end_with_newline = True
    options.max_preserve_newlines = 2
    options.space_around_combinator = True
    return cssbeautifier.beautify(source, options)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Format the readable, non-minified GUI sources in spade65/web."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report files that need formatting without changing them",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    targets: tuple[tuple[Path, Callable[[str], str]], ...] = (
        *((path, format_javascript) for path in JS_FILES),
        *((path, format_css) for path in CSS_FILES),
    )
    changed: list[Path] = []

    for path, formatter in targets:
        source = path.read_text(encoding="utf-8")
        formatted = formatter(source)
        if source == formatted:
            continue
        changed.append(path.relative_to(ROOT))
        if not args.check:
            path.write_text(formatted, encoding="utf-8")

    if not changed:
        print("Web sources are formatted.")
        return 0

    action = "Need formatting" if args.check else "Formatted"
    for path in changed:
        print(f"{action}: {path}")
    return 1 if args.check else 0


if __name__ == "__main__":
    raise SystemExit(main())
