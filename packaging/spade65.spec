# -*- mode: python ; coding: utf-8 -*-
"""Cross-platform one-folder PyInstaller definition for Spade65."""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


ROOT = Path(SPECPATH).parent
TARGET_ARCH = os.environ.get("SPADE65_TARGET_ARCH") or None
DESKTOP_HIDDEN_IMPORTS = {
    "linux": [
        "webview.platforms.qt",
        "soundcard",
        "soundcard.pulseaudio",
    ],
    "win32": [
        "hid",
        "webview.platforms.winforms",
        "webview.platforms.edgechromium",
        "clr",
        "pysysaudio",
        "pysysaudio._pysysaudio_native",
    ],
    "darwin": [
        "hid",
        "webview.platforms.cocoa",
        "pysysaudio",
        "pysysaudio._pysysaudio_native",
    ],
}.get(sys.platform, [])
AUDIO_DATA_FILES = (
    collect_data_files("soundcard") if sys.platform.startswith("linux") else []
)
PLATFORM_EXCLUDES = {
    # QtPy imports this compatibility module from a suppressed optional block.
    # It is unrelated to the QtWebEngine widgets backend and pulls GPL-only Qt
    # Graphs/Data Visualization modules into an otherwise LGPL distribution.
    "linux": ["qtpy.QtDataVisualization", "PySide6.QtDataVisualization"],
}.get(sys.platform, [])
LINUX_HOST_RUNTIME_LIBRARIES = {
    # These libraries must stay aligned with the host graphics/audio drivers
    # and font configuration. Bundling Ubuntu build-host copies breaks newer
    # Mesa/Intel drivers, ALSA plugins, and rolling-release fontconfig.
    "libstdc++.so.6",
    "libgcc_s.so.1",
    "libgbm.so.1",
    "libfontconfig.so.1",
    "libfreetype.so.6",
    "libexpat.so.1",
    "libX11.so.6",
    "libX11-xcb.so.1",
    "libasound.so.2",
    "libpulse.so.0",
    # Driver-facing graphics dispatch libraries are normally excluded by
    # PyInstaller already. Listing their common sonames here makes that policy
    # explicit if upstream collection behavior changes.
    "libEGL.so.1",
    "libGL.so.1",
    "libGLX.so.0",
    "libGLdispatch.so.0",
    "libOpenGL.so.0",
    "libGLESv2.so.2",
    "libdrm.so.2",
    "libdrm_amdgpu.so.1",
    "libdrm_intel.so.1",
    "libdrm_nouveau.so.2",
    "libvulkan.so.1",
    "libva.so.2",
    "libva-drm.so.2",
    "libva-x11.so.2",
    "libxcb.so.1",
    "libxcb-dri2.so.0",
    "libxcb-dri3.so.0",
    "libwayland-client.so.0",
    "libwayland-cursor.so.0",
    "libwayland-egl.so.1",
    "libglapi.so.0",
    "libharfbuzz.so.0",
}

analysis = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[*collect_data_files("spade65.web"), *AUDIO_DATA_FILES],
    hiddenimports=["webview", *DESKTOP_HIDDEN_IMPORTS],
    hookspath=[str(ROOT / "packaging" / "hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=PLATFORM_EXCLUDES,
    noarchive=False,
    optimize=1,
)

if sys.platform.startswith("linux"):
    analysis.binaries = [
        entry
        for entry in analysis.binaries
        if Path(entry[0]).name not in LINUX_HOST_RUNTIME_LIBRARIES
    ]

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
            "NSAppTransportSecurity": {
                "NSAllowsLocalNetworking": True,
            },
            "NSAppleEventsUsageDescription": (
                "Spade65 reads the foreground application name to switch "
                "locally configured keyboard profiles."
            ),
            "NSMicrophoneUsageDescription": (
                "Spade65 uses microphone input only when you enable an "
                "audio-reactive lighting effect."
            ),
            "NSAudioCaptureUsageDescription": (
                "Spade65 captures system audio only when you select system "
                "output for an audio-reactive lighting effect."
            ),
        },
    )
