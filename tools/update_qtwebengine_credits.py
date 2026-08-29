#!/usr/bin/env python3
"""Build the pinned offline QtWebEngine attribution document.

Qt's generated QtWebEngine documentation publishes one attribution page per
Chromium dependency.  This script collects every page linked by the Qt 6.11.2
licensing index into one self-contained HTML document.  It intentionally fails
if the online documentation no longer identifies itself as Qt 6.11.2.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import html
import re
import urllib.parse
import urllib.request
from pathlib import Path


QT_VERSION = "6.11.2"
BASE_URL = "https://doc.qt.io/qt-6/"
INDEX_NAME = "qtwebengine-licensing.html"
DEFAULT_OUTPUT = Path("licenses/QtWebEngine-6.11.2-THIRD-PARTY-NOTICES.html")
USER_AGENT = "Spade65-license-bundle/0.7.0"

ARTICLE_RE = re.compile(
    r'<article class="b-sidebar__content__left">(.*?)</article>', re.DOTALL
)
ATTRIBUTION_RE = re.compile(
    r'href="(qtwebengine-3rdparty-[^"]+\.html)"'
)
RELATIVE_LINK_RE = re.compile(r'href="(?![a-z]+:|#|/)([^"]+)"', re.IGNORECASE)


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def article_from_page(page: str, *, source_url: str) -> str:
    match = ARTICLE_RE.search(page)
    if match is None:
        raise RuntimeError(f"Qt documentation article is missing: {source_url}")
    article = match.group(1).strip()
    article = RELATIVE_LINK_RE.sub(
        lambda item: f'href="{urllib.parse.urljoin(BASE_URL, item.group(1))}"',
        article,
    )
    return article


def linked_attributions(index: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for name in ATTRIBUTION_RE.findall(index):
        if name not in seen:
            seen.add(name)
            result.append(name)
    if len(result) < 100:
        raise RuntimeError(
            f"Qt attribution index unexpectedly contains only {len(result)} pages"
        )
    return result


def render(index: str, pages: dict[str, str], names: list[str]) -> str:
    if f"Qt {QT_VERSION}" not in index:
        raise RuntimeError(f"Qt documentation is no longer pinned to {QT_VERSION}")

    index_url = urllib.parse.urljoin(BASE_URL, INDEX_NAME)
    index_article = article_from_page(index, source_url=index_url)
    sections = [index_article]
    for name in names:
        source_url = urllib.parse.urljoin(BASE_URL, name)
        article = article_from_page(pages[name], source_url=source_url)
        sections.append(
            '<hr class="component-separator">\n'
            f'<p class="source"><strong>Primary source:</strong> '
            f'<a href="{html.escape(source_url)}">{html.escape(source_url)}</a></p>\n'
            f"{article}"
        )

    body = "\n".join(sections)
    required_markers = (
        "Chromium License",
        "WebKit",
        "ffmpeg",
        "GNU LIBRARY GENERAL PUBLIC LICENSE",
        "Redistribution and use in source and binary forms",
    )
    for marker in required_markers:
        if marker.lower() not in body.lower():
            raise RuntimeError(f"generated attribution is missing {marker!r}")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Qt WebEngine {QT_VERSION} third-party notices</title>
<style>
body {{ color: #202124; font: 14px/1.5 sans-serif; margin: 2rem auto; max-width: 72rem; padding: 0 1.5rem; }}
pre {{ background: #f5f5f5; overflow-wrap: anywhere; padding: 1rem; white-space: pre-wrap; }}
table {{ border-collapse: collapse; width: 100%; }}
td, th {{ border: 1px solid #bbb; padding: .35rem; text-align: left; vertical-align: top; }}
.provenance {{ background: #eef6ff; border: 1px solid #9bc4ef; padding: 1rem; }}
.component-separator {{ border: 0; border-top: 3px solid #444; margin: 3rem 0 1rem; }}
.source {{ overflow-wrap: anywhere; }}
</style>
</head>
<body>
<h1>Qt WebEngine {QT_VERSION} third-party notices</h1>
<div class="provenance">
<p>This offline document was generated from the official Qt {QT_VERSION}
Qt WebEngine licensing index and all {len(names)} unique third-party attribution
pages linked by that index. It is bundled as a conservative superset of the
notices applicable to the unmodified PySide6 {QT_VERSION} Linux wheels.</p>
<p>Index primary source: <a href="{index_url}">{index_url}</a>.
Qt documentation is provided under the GNU Free Documentation License 1.3;
the corresponding text is shipped beside this file.</p>
</div>
{body}
</body>
</html>
"""


def generate(output: Path) -> None:
    index_url = urllib.parse.urljoin(BASE_URL, INDEX_NAME)
    index = fetch(index_url)
    names = linked_attributions(index)
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        contents = executor.map(
            fetch, (urllib.parse.urljoin(BASE_URL, name) for name in names)
        )
        pages = dict(zip(names, contents, strict=True))
    document = render(index, pages, names)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8", newline="\n")
    print(f"Wrote {output} ({len(names)} attribution pages)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    generate(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
