# Spade65

**English** · [Bahasa Indonesia](README.id.md)

Spade65 is an independent, cross-platform configuration application for the
**non-QMK Noir Spade65** keyboard. It provides a standalone desktop interface
and a command-line tool for managing supported keyboard settings without the
official Windows-only application.

The project is based on static analysis of `Spade65_SETUP_20240403.exe` and
incremental validation with a physical Spade65. It deliberately supports only
configuration paths that can be reproduced with clear safety boundaries.

## Preview

<table>
  <tr>
    <td width="50%"><a href="docs/images/spade65-overview.png"><img src="docs/images/spade65-overview.png" alt="Spade65 application overview showing device status and profile controls" /></a></td>
    <td width="50%"><a href="docs/images/spade65-keyboard.png"><img src="docs/images/spade65-keyboard.png" alt="Spade65 keyboard layout and key-assignment editor" /></a></td>
  </tr>
  <tr>
    <td align="center"><strong>Overview and profiles</strong></td>
    <td align="center"><strong>Keyboard and keymap</strong></td>
  </tr>
  <tr>
    <td width="50%"><a href="docs/images/spade65-lighting.png"><img src="docs/images/spade65-lighting.png" alt="Spade65 lighting effects and per-key RGB editor" /></a></td>
    <td width="50%"><a href="docs/images/spade65-macros.png"><img src="docs/images/spade65-macros.png" alt="Spade65 macro editor and recorder" /></a></td>
  </tr>
  <tr>
    <td align="center"><strong>Lighting and RGB</strong></td>
    <td align="center"><strong>Macros</strong></td>
  </tr>
</table>

## Highlights

- Standalone desktop GUI and CLI on Linux, Windows, and macOS.
- Automatic device detection and a synchronized preview for all four Spade65
  physical layouts: ANSI/ISO with standard or split spacebar.
- Three-layer keymap editor with the assignment categories exposed by the
  original application.
- Macro recording, editing, repeat settings, and key binding.
- All 20 built-in lighting effect IDs, brightness, speed, palette, per-key RGB,
  AP-mode effects, audio reactivity, and a custom-effect timeline.
- Local profiles, full library backup/restore, and conversion of original
  KeyAssign, Macro, and APMode JSON exports.
- Optional background effects and application-to-profile associations on all
  three supported desktop platforms.
- English interface by default, with Bahasa Indonesia included and a catalog
  structure designed for additional languages.

The GUI and backend run locally. The embedded server listens only on loopback,
uses a random session token, and rejects foreign Host and Origin values.

## What persists on the keyboard?

Spade65 uses both device-backed configuration and host-side features:

| Configuration | Where it lives | Available after changing computers or operating systems? |
|---|---|---|
| Keymap, macros, built-in lighting, per-key lighting, debounce, and supported dongle timers | Sent through the vendor configuration reports to keyboard memory | Designed to remain on the keyboard after it is applied |
| Profile library, selected visual layout, application associations, AP/custom timeline playback, and audio-reactive streaming | Local application data | Requires Spade65 or its optional background service on that host |

The four physical layout variants cannot be read from the keyboard descriptor.
When a device is connected, the application restores the layout last selected
locally for that model; when no device is detected, it displays the
`Spade65-04 · ANSI standard` fallback preview.

## Safety boundary

Firmware flashing, bootloader access, raw flash/write operations, and arbitrary
HID packets are intentionally **not implemented** because an incorrect operation
could brick the keyboard. They have no GUI action, API endpoint, packet builder,
or hidden fallback in this project.

Configuration writes are descriptor-gated. A complete keymap overwrite requires
two confirmations, while reset requires a typed confirmation. These exclusions
and safeguards are part of the design, not unfinished release items.

## Download

Ready-to-run packages are published on
[GitHub Releases](https://github.com/dirhamtriyadi/spade65-non-qmk/releases/latest):

| Platform | Release asset | Notes |
|---|---|---|
| Windows x64 | `Spade65-Windows-x64.zip` | Includes GUI and console executables; Microsoft WebView2 is required |
| Linux x86_64 | `Spade65-Linux-x86_64.AppImage` | Built on Ubuntu 22.04; uses the host graphics and desktop libraries |
| macOS universal | `Spade65-macOS-universal.dmg` | Runs on Intel and Apple silicon |

Opening the packaged application without arguments launches the desktop GUI.
The Windows package is not code-signed, and the macOS package is not notarized,
so the operating system may show a security warning. See the
[cross-platform guide](docs/cross-platform.md) for installation notes and the
[release guide](docs/releasing.md) for CI and manual builds.

## Quick start from source

Python 3.10 or newer is required.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[desktop,cross-platform]"
spade65ctl gui
```

On Windows, activate the environment with
`.venv\Scripts\activate` instead. Basic CLI discovery is available with:

```bash
spade65ctl --help
spade65ctl probe
```

Linux users normally need the included udev rule before accessing `hidraw` as a
regular user. Platform-specific setup and troubleshooting are documented in
[`docs/cross-platform.md`](docs/cross-platform.md); complete commands and safe
hardware workflows are in [`docs/cli.md`](docs/cli.md).

## Verification status

The current physical validation uses a wired Linux device identified as
`0603:0351`. Descriptor discovery, the fixed built-in RGB effect and its
brightness/speed controls, debounce, per-key RGB, real-time streaming, a
background-service timeline frame, and read-only USB revision reporting have
been exercised successfully.

Keymap and macro writes, reset, and dongle timers are covered by offline packet
and integration tests but have not been sent during the latest physical test.
Keymap/reset lack a guaranteed readback-and-restore path, and dongle PID
`0603:0356` was not connected. See
[`docs/hardware-verification.md`](docs/hardware-verification.md) for the precise
test record. Automated or offline coverage is never presented as physical
device verification.

## Documentation

- [CLI and safe operation](docs/cli.md)
- [Cross-platform installation and troubleshooting](docs/cross-platform.md)
- [Feature parity with the original application](docs/parity.md)
- [Profiles, vendor import, timelines, and background service](docs/host-features.md)
- [Protocol and report formats](docs/protocol.md)
- [Hardware verification record](docs/hardware-verification.md)
- [Development guide](docs/development.md)
- [Localization guide](docs/localization.md)
- [Release and manual-build guide](docs/releasing.md)
- [Desktop packaging details](packaging/README.md)

English is the canonical documentation language. Maintained Indonesian
translations are linked from each guide.

## Contributing

Start with the [development guide](docs/development.md). Before submitting a
change, run:

```bash
python -m unittest discover -v
python -m compileall -q spade65 spade65ctl.py tests tools
```

Protocol changes should include offline tests and must not weaken the firmware,
raw-write, descriptor, or confirmation boundaries. Physical test claims should
be added only with a reproducible test record.

## Legal and license

This is an independent project and is not official Noir software. The repository
does not distribute the official installer, firmware, extracted vendor source,
or vendor-native binaries. Use it only with hardware you own.

Original project code is licensed under the [MIT License](LICENSE). Bundled and
runtime dependencies retain their own licenses; versions, notices, source
locations, and replacement instructions are listed in
[`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md). Vendor software, firmware,
names, and assets remain the property of their respective rights holders.
