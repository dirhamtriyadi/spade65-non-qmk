**English** · [Bahasa Indonesia](id/cross-platform.md)

# Cross-platform support

## Status

| Platform | Discovery and writes | Desktop renderer (v0.7.0) | Active application | Background launcher | Physical validation |
|---|---|---|---|---|---|
| Linux | `hidraw` + sysfs | PySide6/QtWebEngine | X11, Wayland process fallback | systemd user service | Yes, USB `0603:0351` |
| Windows | HIDAPI / Win32 HID | Edge WebView2 | Win32 foreground window | Startup `.cmd` | Not yet tested on a Windows machine |
| macOS | HIDAPI / IOKit | Cocoa/WebKit | System Events frontmost process | LaunchAgent `.plist` | Not yet tested on a macOS machine |

The GUI, profile compiler, macros, vendor converter, AP renderer, timeline, and
safety rules share the same source across all operating systems. Windows and
macOS do not use `/dev/hidraw` or sysfs. The desktop window uses PyWebView as a
native shell, while its interface remains the same local HTML, CSS, and
JavaScript used by browser mode; its controls are not fully native widgets.

CI runs unit tests on Ubuntu, Windows, and macOS with Python 3.10 and 3.13. This
verifies imports, the compiler, simulated transports, the service, and the
launcher on those systems. Every push to `main` also runs a native packaging
preflight: a Windows ZIP, Linux AppImage on Ubuntu 22.04, and universal macOS DMG
are built and smoke-tested without being published. Physical validation remains
listed separately in the table above.

A `vMAJOR.MINOR.PATCH` release tag also runs a native build on each operating
system and publishes the following assets only when every build succeeds:

- `Spade65-Windows-x64.zip`
- `Spade65-Linux-x86_64.AppImage`
- `Spade65-macOS-universal.dmg`

These packages include the application runtime; users do not need to clone the
repository or run Python. See [`releasing.md`](releasing.md) for pipeline details
and tagging instructions.

## Installation

### Desktop packages

Download the appropriate asset from GitHub Releases.

- Windows x64: extract the ZIP completely, then run `Spade65.exe` for the GUI.
  Use `Spade65CLI.exe` from a terminal for CLI commands with visible console
  output and errors, for example `Spade65CLI.exe probe`. The standalone window
  requires Microsoft Edge WebView2 Runtime; an up-to-date Windows 10 or 11
  installation usually includes it. If the runtime is unavailable, the launcher
  opens the GUI in the default browser.
- Linux x86_64: make the file executable with
  `chmod +x Spade65-Linux-x86_64.AppImage`, then run it. If FUSE is unavailable,
  use `APPIMAGE_EXTRACT_AND_RUN=1 ./Spade65-Linux-x86_64.AppImage`. The desktop
  AppImage bundles PySide6/QtWebEngine, so it is larger and requires a graphical
  session. Official assets are built and smoke-tested on Ubuntu 22.04 x86_64
  (glibc 2.35), which is the supported baseline. Newer distributions are
  generally compatible; run `--smoke-test` to verify the package on another
  distribution.
- macOS Intel/Apple Silicon: open the DMG, then copy `Spade65.app` to
  `Applications`. The universal bundle is checked to ensure its native binary
  contains both `x86_64` and `arm64` slices. The window uses the system
  Cocoa/WebKit stack. The bundle permits localhost networking and declares
  microphone use; the microphone prompt is relevant only when an audio-reactive
  effect is enabled.

With no arguments, a package opens the local GUI at
`http://127.0.0.1:8765/` in a standalone window. A second launch verifies the
session token, then activates, shows, and restores the existing window. The
explicit `gui` command uses the same coordinator, so a second invocation does
not fail with `Address already in use`. The port is claimed before the renderer
loads, and activation requests received during startup are deferred until the
window is ready. A foreign service on port 8765 is never stopped or taken over;
startup fails with a clear message. When **Settings → Desktop integration →
Keep running in the system tray** is enabled and the desktop exposes a tray,
closing the window hides it without stopping the localhost server. **Open
Spade65** restores it; **Quit Spade65** in the tray or **Quit application** in
the GUI stops the process. If a Linux session does not expose a tray, the option
is disabled and closing the window exits normally. Browser mode behaves
differently: closing the tab does not stop the server; choose **Quit
application** or terminate the process in its terminal.

The Linux and macOS executables also accept CLI commands; for example, the
AppImage can be run with the `probe` argument. On Windows, use `Spade65CLI.exe`
so CLI output is not lost in the console-less GUI executable. To select a GUI
mode explicitly, use the `gui --browser` or `gui --no-browser` subcommand through
the CLI executable.

A GUI executable opened from a file manager does not always have a terminal. In
that case, output and errors are written to the following log, and startup
failures are also shown through an available native dialog or notification:

- Windows: `%LOCALAPPDATA%\Spade65\Logs\launcher.log`;
- Linux: `${XDG_STATE_HOME:-~/.local/state}/spade65/launcher.log`;
- macOS: `~/Library/Logs/Spade65/launcher.log`.

The Keyboard and Lighting pages share one layout state. When a configuration
interface is detected, the application restores the last host-side selection
for the Spade65; USB `0351` and dongle `0356` are treated as two transports for
the same model. When no configuration interface is detected — including when
only the read-only `0603:0352` receiver is present — both previews use the
default Noir Spade65-04 ANSI standard layout and their selectors are temporarily
disabled.
The firmware and descriptor do not expose the geometry variant, so the
application does not claim to read the physical layout from the keyboard. The
frontend checks for connection changes every two seconds and synchronizes both
previews automatically without altering the profile currently being edited.

PyWebView uses an application-specific storage profile with
`private_mode=False`. `localStorage` data for language, layout, and profiles is
preserved at the following locations:

- Windows: `%LOCALAPPDATA%\Spade65\WebView`;
- Linux: `${XDG_DATA_HOME:-~/.local/share}/spade65/webview`;
- macOS: the persistent default Cocoa WebKit website data store managed by the
  operating system for bundle ID `io.github.dirhamtriyadi.spade65`; this backend
  does not expose a custom path through pywebview.

The close-to-tray preference is native-shell state, not WebView data. It is
stored in `${XDG_CONFIG_HOME:-~/.config}/spade65/desktop-settings.json` on
Linux, `%APPDATA%\Spade65\desktop-settings.json` on Windows, and
`~/Library/Application Support/Spade65/desktop-settings.json` on macOS.

Browser mode uses the browser profile's storage and does not automatically share
data with the WebView. Use library backup and restore to transfer it. Profile
exports and JSON library-backup downloads are supported in the standalone
window.

The Windows package is not code-signed. The macOS application has only an ad-hoc
signature and is not notarized, so SmartScreen or Gatekeeper may display a
warning. Make sure the file came from a trusted project release. Installing from
source as described below remains a fallback.

Linux still requires the repository's udev rule so an ordinary user can open
`hidraw`. The official AppImage includes only the verified `hidraw` transport;
an experimental HIDAPI override can still be installed from source through the
`cross-platform` extra, but it is not part of the AppImage. macOS
Automation/Accessibility permission requirements for application associations
also apply to the desktop package. macOS microphone permission is required only
for audio input used by audio-reactive effects; the localhost server is not
exposed to an external network.

### Installing from source

For the CLI alone, Linux requires no additional runtime package:

```bash
python -m pip install -e .
```

Install the desktop extra for a PySide6/QtWebEngine window on Linux:

```bash
python -m pip install -e ".[desktop]"
python -m spade65 gui
```

Windows and macOS require HIDAPI 0.14 or newer so the report descriptor can be
read before a write. Combine both extras for the standalone GUI:

```bash
python -m pip install -e ".[cross-platform,desktop]"
python -m spade65 probe
python -m spade65 gui
```

On every operating system, `python -m spade65 gui` selects the desktop window by
default and falls back to the browser when the native runtime cannot be loaded.
Use `python -m spade65 gui --browser` to always open a browser, or
`python -m spade65 gui --no-browser` to run only the server.

### Troubleshooting Wayland and rolling distributions

AppImage v0.7.2 and later use the host's C++, graphics, audio, and font runtimes
to remain compatible with distribution drivers and configuration. Older
releases can fail on EndeavourOS or Arch with `CXXABI not found`, `EGL not
available`, or Fontconfig errors. Use the latest release; as a safe fallback for
v0.7.1, run the server without opening another desktop process:

```bash
./Spade65-Linux-x86_64.AppImage gui --no-browser
```

Then open `http://127.0.0.1:8765/` manually in a browser. Do not hard-code an
`LD_PRELOAD` workaround in the launcher because library locations and ABIs vary
between distributions; the production fix is included in AppImage v0.7.2.

If a collection's descriptor cannot be read, `probe` may still display the
collection, but write commands reject it. VID/PID alone is never sufficient to
bypass validation.

The GUI in every package provides English as the default language and Bahasa
Indonesia as an option. The language preference is stored locally in the
application-specific WebView profile, or in the browser profile when fallback
mode is used. See [`localization.md`](localization.md) for the extensible
structure.

## Desktop login startup

The native Settings page can enable **Start after sign-in** for the current
user. It writes one OS-native, user-owned launcher and starts the same release
with `gui --start-hidden`:

- Linux: `${XDG_CONFIG_HOME:-~/.config}/autostart/io.github.dirhamtriyadi.spade65.desktop`;
- Windows: `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\spade65-gui.cmd`;
- macOS: `~/Library/LaunchAgents/io.github.dirhamtriyadi.spade65.gui.plist`.

Disabling the switch removes only that Spade65 launcher. Move the AppImage,
extracted Windows directory, or macOS application to its permanent location
before enabling it. If the application later moves, Settings reports the stale
launcher so it can be disabled and enabled again. Hidden startup is accepted
only for the native desktop mode. If a Linux tray disappears between sessions,
the application shows its window instead of leaving an inaccessible process.

This starts the GUI shell; it is separate from the service below. Use the
service when AP/timeline playback or application associations must continue
independently of the WebView.

## Background service startup

For release users, open **Settings → Background service**. The packaged GUI
detects Linux, Windows, or macOS and displays commands that invoke the release
executable actually in use. It separates configuration creation from startup
activation so the example process and profile paths can be edited first. Move
the release package to a permanent location before running those commands.

The following `spade65ctl` form is for source or Python-package installations.
Create a service configuration, then generate a launcher for the current
operating system:

```bash
spade65ctl service example spade65-service.json
spade65ctl service integration spade65-service.json launcher-output
```

- Linux: copy the unit to `~/.config/systemd/user/`, then enable it as the user.
- Windows: place the `.cmd` file in the user's Startup folder.
- macOS: place the `.plist` file in `~/Library/LaunchAgents/`, then load it with
  `launchctl` in the user's session.

The generator only writes the requested output file; it does not modify
operating-system startup automatically. On macOS, application associations may
require Automation/Accessibility permission to read the frontmost application.
See the [host-features guide](host-features.md) for the release-specific paths,
activation flow, and safety controls.

## Persistent device and host data

Keymap, macro, built-in/per-key effect, debounce, and dongle-timer reports target
the device's internal configuration, like the official software. Those settings
do not require a background service after they are applied. Named profiles,
application associations, AP/streaming animations, and custom timelines are host
data; their effects require the GUI or service to remain running.

On every OS, applying a keymap resolves the descriptor-gated main and short
companion collections and opens both handles before writing. The main handle
stays open while it sends keymap, referenced macros, and current/cached
lighting; the separate short handle sends per-profile debounce in the official
order. Wired mode ends after debounce; its transaction never sends a dongle
timer.

A temporary three-layer keymap and macro were applied to the wired `0603:0351`
unit and verified through physical input, then the default keymap and an empty
macro were re-applied to restore it. Persistence across a power cycle has still
not been measured. The device provides no readback, so a saved profile remains
the only restore path. The individual report paths have hardware evidence, but
visual lighting preservation after the newly completed combined transaction is
still awaiting confirmation.
Firmware flashing, bootloader access, raw flashing, and arbitrary HID are not
implemented on any operating system. Neither desktop packages nor local builds
contain a hidden path to those operations.
