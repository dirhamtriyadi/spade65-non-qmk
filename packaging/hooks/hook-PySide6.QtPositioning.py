"""Collect the linked QtPositioning runtime without unused provider plugins."""

from PyInstaller.utils.hooks.qt import add_qt6_dependencies


hiddenimports, _provider_binaries, _provider_datas = add_qt6_dependencies(__file__)
binaries = []
datas = []
