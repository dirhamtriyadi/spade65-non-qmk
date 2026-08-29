"""Collect QtQml runtime libraries without every optional QML module.

QtWebEngineWidgets links QtQuick/QtQml even when an application uses only the
widgets API.  PyInstaller's stock QtQml hook consequently copies the complete
QML tree from the PySide6 Addons wheel, including unrelated GPL-only modules
such as Qt Graphs, Quick 3D, Virtual Keyboard, and Wayland Compositor.  Spade65
does not load QML, so only the native dependency closure is required.
"""

from PyInstaller.utils.hooks.qt import add_qt6_dependencies


hiddenimports, binaries, datas = add_qt6_dependencies(__file__)

# Spade65 neither loads QML nor exposes a QML debugger. Dropping the generic
# qmltooling plugin set before PyInstaller scans binary dependencies also
# prevents the GPL-only Quick3D profiler dependency from entering the bundle.
binaries = [
    entry
    for entry in binaries
    if "/plugins/qmltooling/" not in str(entry).replace("\\", "/")
]
