# -*- mode: python ; coding: utf-8 -*-
"""Cross-platform one-folder PyInstaller definition for Spade65."""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


ROOT = Path(SPECPATH).parent
TARGET_ARCH = os.environ.get("SPADE65_TARGET_ARCH") or None

analysis = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=collect_data_files("spade65.web"),
    hiddenimports=["hid"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(analysis.pure)

gui_executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Spade65",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch=TARGET_ARCH,
    codesign_identity=None,
    entitlements_file=None,
)

executables = [gui_executable]
if sys.platform == "win32":
    cli_executable = EXE(
        pyz,
        analysis.scripts,
        [],
        exclude_binaries=True,
        name="Spade65CLI",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=True,
        target_arch=TARGET_ARCH,
        codesign_identity=None,
        entitlements_file=None,
    )
    executables.append(cli_executable)

collection = COLLECT(
    *executables,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="Spade65",
)

if sys.platform == "darwin":
    application = BUNDLE(
        collection,
        name="Spade65.app",
        icon=None,
        bundle_identifier="io.github.dirhamtriyadi.spade65",
        info_plist={
            "CFBundleDisplayName": "Spade65",
            "CFBundleName": "Spade65",
            "CFBundleShortVersionString": os.environ.get(
                "SPADE65_VERSION", "0.0.0"
            ),
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSAppleEventsUsageDescription": (
                "Spade65 reads the foreground application name to switch "
                "locally configured keyboard profiles."
            ),
        },
    )
