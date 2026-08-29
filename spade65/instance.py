"""Authenticated localhost discovery for an existing Spade65 GUI instance."""

from __future__ import annotations

import json
import re
import urllib.request
import webbrowser


LOCALHOST_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def gui_url(host: str, port: int) -> str:
    """Build the loopback URL used by the GUI server."""

    authority = f"[{host}]" if ":" in host else host
    if port != 80:
        authority = f"{authority}:{port}"
    return f"http://{authority}/"


def running_gui_token(url: str) -> str | None:
    """Return the token of an existing verified Spade65 GUI session."""

    try:
        with LOCALHOST_OPENER.open(url, timeout=1) as response:
            if response.status != 200:
                return None
            contents = response.read(1_000_000).decode("utf-8", errors="replace")
        marker = re.search(
            r'<meta\s+name="spade65-token"\s+content="([A-Za-z0-9_-]{20,})"',
            contents,
        )
        if marker is None or "<title>Spade65 Control Center</title>" not in contents:
            return None
    except (OSError, UnicodeError, ValueError):
        return None
    return marker.group(1)


def activate_running_gui(url: str) -> bool:
    """Ask an existing authenticated desktop session to restore its window."""

    token = running_gui_token(url)
    if token is None:
        return False
    request = urllib.request.Request(
        f"{url.rstrip('/')}/api/activate",
        data=b"{}",
        headers={
            "Content-Type": "application/json",
            "X-Spade65-Token": token,
        },
        method="POST",
    )
    try:
        with LOCALHOST_OPENER.open(request, timeout=1) as response:
            result = json.loads(response.read(1_000_000))
        return (
            response.status == 200
            and isinstance(result, dict)
            and result.get("ok") is True
        )
    except (AttributeError, OSError, TypeError, UnicodeError, ValueError):
        return False


def reopen_running_gui_in_browser(url: str) -> bool:
    """Open a verified browser/server session and report whether it was opened."""

    if running_gui_token(url) is None:
        return False
    try:
        return bool(webbrowser.open(url))
    except (OSError, webbrowser.Error):
        return False
