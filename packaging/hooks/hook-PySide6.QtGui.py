"""Collect only QtGui plugins needed by the desktop WebView shell."""

from PyInstaller.utils.hooks.qt import add_qt6_dependencies


hiddenimports, binaries, datas = add_qt6_dependencies(__file__)

_allowed_plugins = (
    "/plugins/platforms/libqoffscreen",
    "/plugins/platforms/libqwayland",
    "/plugins/platforms/libqxcb",
    "/plugins/platforminputcontexts/libcompose",
    "/plugins/platforminputcontexts/libibus",
    "/plugins/wayland-decoration-client/",
    "/plugins/wayland-graphics-integration-client/",
    "/plugins/wayland-shell-integration/",
    "/plugins/xcbglintegrations/",
)


def _needed_for_desktop(entry: object) -> bool:
    normalized = str(entry).replace("\\", "/")
    if "/plugins/" not in normalized:
        return True
    return any(marker in normalized for marker in _allowed_plugins)


binaries = [entry for entry in binaries if _needed_for_desktop(entry)]
