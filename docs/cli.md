**English** · [Bahasa Indonesia](id/cli.md)

# CLI and user guide

This guide covers day-to-day use of Spade65 from a release package or a source
checkout. The application provides the same local interface in a standalone
desktop window and in a browser, plus a command-line interface for inspection,
automation, and explicit configuration writes.

Spade65 supports the non-QMK Noir Spade65 wired USB identity `0603:0351` and
2.4 GHz dongle identity `0603:0356`. The physical receiver identity `0603:0352`
is listed for read-only diagnostics only: its descriptor advertises neither
verified configuration collection, so it is never a configuration target. Hardware validation is intentionally
incremental: wired discovery, descriptor parsing, built-in RGB, brightness,
speed, debounce, per-key RGB, and streaming have been tested on a physical
keyboard. Keymap, macro, reset, and dongle-timer report builders are covered by
automated tests but have not yet been sent to the available hardware. See the
[current hardware verification record](hardware-verification.md) for the exact
test boundary.

> **Safety boundary:** this project does not implement firmware flashing, raw
> flash writes, bootloader access, or arbitrary HID packets. Every device write
> is allowed only after the configuration descriptor matches the verified
> report shape. Direct configuration commands require their documented
> confirmation flags. The background service may stream AP/timeline frames
> without a `--confirm` flag, but automatic profile writes remain disabled
> unless they are enabled separately in both its configuration and CLI. Never
> bypass a descriptor or report-length error.

## Install or run Spade65

### Release packages

Release assets contain the runtime, so end users do not need Git, Python, or a
repository checkout:

- **Windows x64:** extract `Spade65-Windows-x64.zip`. Open `Spade65.exe` for the
  GUI and use `Spade65CLI.exe` in PowerShell or Command Prompt for CLI output.
- **Linux x86_64:** make `Spade65-Linux-x86_64.AppImage` executable and run it:

  ```bash
  chmod +x Spade65-Linux-x86_64.AppImage
  ./Spade65-Linux-x86_64.AppImage
  ```

  If FUSE is unavailable, prefix the command with
  `APPIMAGE_EXTRACT_AND_RUN=1`.
- **macOS Intel/Apple Silicon:** open `Spade65-macOS-universal.dmg`, copy
  `Spade65.app` to Applications, and open it. The universal application contains
  Intel and Apple Silicon code.

The Windows package is not code-signed, and the macOS application is ad-hoc
signed rather than notarized. Verify that a download came from the project's
GitHub release before accepting a SmartScreen or Gatekeeper warning. Platform
requirements and package-specific troubleshooting are documented in the
[cross-platform guide](cross-platform.md).

### Install from source

Python 3.10 or newer is required. For a CLI-only Linux installation:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
spade65ctl --help
```

Install the desktop runtime on Linux with:

```bash
python -m pip install -e ".[desktop]"
```

Windows and macOS need HIDAPI for descriptor-validated access. Install both
extras when the desktop window is also wanted:

```bash
python -m pip install -e ".[cross-platform,desktop]"
```

From an uninstalled checkout, replace `spade65ctl` in the examples below with
`python spade65ctl.py`. `python -m spade65` is another installed-source entry
point.

## Start the GUI or use the CLI

Opening a packaged application with no arguments starts the standalone desktop
window. From a terminal, these modes are also available:

```bash
spade65ctl gui
spade65ctl gui --browser
spade65ctl gui --no-browser
spade65ctl gui --start-hidden
```

The default desktop mode hosts the local interface at
`http://127.0.0.1:8765/` and embeds it in a PyWebView window. `--browser` opens
the same interface in the default browser. `--no-browser` starts only the local
server, which is useful on a Linux desktop where the embedded renderer is not
compatible with the current Wayland or graphics setup.

`--start-hidden` is the native desktop startup mode used by the per-user login
launcher created from **Settings → Desktop integration**. It cannot be combined
with browser/server-only modes. If the current Linux session has no usable
system tray, the application deliberately shows the window instead.

The server listens on loopback only. Its API requires a random session token
and rejects foreign `Host` and mismatched `Origin` values. A second desktop
launch activates the existing application instead of claiming port 8765 again.
If another, unrelated process owns the port, Spade65 reports the conflict and
does not terminate that process. With close-to-tray enabled and a tray
available, closing the desktop window hides it; otherwise close stops its
server. Choosing **Quit application** always stops the process. In browser mode,
closing the tab alone does not stop the terminal process.

The GUI and CLI share the same protocol implementation and safety checks. The
GUI adds profiles, three-layer key assignment, macro recording, per-key colors,
built-in and host-streamed lighting, a custom timeline, vendor import,
backup/restore, device information, debounce, timers, and reset. English is the
default interface language; Bahasa Indonesia can be selected in the GUI.

Packaged CLI examples:

```powershell
# Windows
.\Spade65CLI.exe probe
.\Spade65CLI.exe info
```

```bash
# Linux
./Spade65-Linux-x86_64.AppImage probe

# macOS, after copying the application
/Applications/Spade65.app/Contents/MacOS/Spade65 probe
```

The rest of this guide uses the installed `spade65ctl` command for readability.

## Linux device permissions

Linux users should install the supplied udev rule so the application can open
the verified `hidraw` interface as an ordinary user:

```bash
sudo install -Dm644 udev/99-spade65.rules /etc/udev/rules.d/99-spade65.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Unplug and reconnect the keyboard or dongle afterward. Run Spade65 as your
normal user. Using `sudo` can help identify a permissions problem, but it should
not be the regular way to launch the application.

## Recommended first hardware check

Start with read-only inspection and a reversible, visible lighting change. Do
not begin with a profile apply, timer, or reset.

1. Connect the keyboard by USB cable and save a privacy-safe probe:

   ```bash
   spade65ctl probe --json > probe-wired.json
   ```

   Serial and unique identifiers are omitted unless `--include-unique` is
   explicitly supplied.
2. Confirm that the configuration collection has usage `ff02:0001`, feature
   report ID `0x07`, and a 620-byte report. Short configuration commands use
   usage `ff03:0001`, report ID `0x08`, and an 8-byte report.
3. Build, but do not send, a known RGB command:

   ```bash
   spade65ctl rgb fixed --brightness 2 --speed 3 --dry-run
   ```

4. Only when the descriptor matches, send the easy-to-reverse change:

   ```bash
   spade65ctl rgb fixed --brightness 2 --speed 3 --confirm
   ```

5. Optionally try a second built-in effect:

   ```bash
   spade65ctl rgb rainbow-wheel --brightness 4 --speed 5 \
     --multicolor --confirm
   ```

6. If a dongle is available, repeat `probe --json` while connected through it
   and save the result separately.

Every write command can take `--device PATH` when more than one matching device
is present. Use only a path printed by `probe`. A matching VID/PID is not enough
to authorize a write; descriptor validation must also succeed.

## Read-only commands

### Inspect HID interfaces

```bash
spade65ctl probe
spade65ctl probe --json
```

`probe` reads enumeration and descriptor information; it does not send a
configuration report.

Each interface reports a `configuration_status`, in the text output as a
`configuration:` line and in `--json` and `info` as a top-level field:

| Value | Meaning |
| --- | --- |
| `descriptor-gated` | A supported configuration identity. Writes are still checked against the advertised report shape before anything is sent. |
| `unsupported-read-only` | Discovered for diagnostics only. No command will write to it. |

### Display available device information

```bash
spade65ctl info
```

`info` sends no HID packets. On Linux, it can report the USB revision from
sysfs and battery information only when the operating system exposes a matching
power-supply device. Windows and macOS use enumeration metadata. The displayed
USB revision is **not** claimed to be the keyboard firmware version: the vendor
firmware-version request has not been safely verified, so Spade65 does not guess
or transmit one.

### Export the known default frame offline

```bash
spade65ctl keymap export-default > keymap-default.json
spade65ctl keymap export-default --format hex
```

This generates the reconstructed default mapping/frame without reading from or
writing to a keyboard. The device does not provide a verified keymap readback,
so an applied profile file remains the backup and source of truth.

## Device configuration commands

All examples first show either validation or `--dry-run` where applicable. A
real write requires `--confirm`; some destructive or broad operations require
an additional acknowledgement.

### Built-in RGB effects

```bash
spade65ctl rgb EFFECT [options] --dry-run
spade65ctl rgb EFFECT [options] --confirm
```

Run `spade65ctl rgb --help` for the current effect list. Common options are:

- `--brightness 0..4`
- `--speed 1..5`
- `--color-index 0..7`
- `--multicolor`
- `--device PATH`

Example:

```bash
spade65ctl rgb breathe --brightness 3 --speed 2 --color-index 0 --confirm
```

Built-in RGB, brightness, and speed writes have been validated on the available
wired keyboard.

### Debounce

The vendor default is 5 ms:

```bash
spade65ctl debounce 5 --dry-run
spade65ctl debounce 5 --confirm
```

A 5 ms debounce write has been validated on the available wired keyboard.

### Profiles, keymaps, and macros

Create and validate a complete editable profile before compiling a write:

```bash
spade65ctl profile create spade65-profile.json
spade65ctl profile validate spade65-profile.json
spade65ctl profile apply spade65-profile.json --dry-run
```

The `layers` object contains `normal`, `fn1`, and `fn2`. Assignments may use a
HID name such as `"b"`, a numeric usage such as `5`, a modified usage such as
`{"usage":"b","modifiers":2}`, or a macro reference such as
`{"macro":0}`.

A macro contains key-down/key-up events and their delays:

```json
{
  "index": 0,
  "repeat": 1,
  "events": [
    {"delay_ms": 20, "usage": "a", "pressed": true},
    {"delay_ms": 20, "usage": "a", "pressed": false}
  ]
}
```

Applying a profile overwrites all three keymap layers and writes each macro
included in that profile. It therefore requires two explicit acknowledgements:

```bash
spade65ctl profile apply spade65-profile.json \
  --confirm --i-understand-profile-overwrite
```

Keep the validated profile and a GUI library backup before applying it. The
available physical keyboard has not been used to test keymap or macro writes
because its existing configuration cannot first be read back and restored.

### Per-key and one-frame streaming RGB

Add a `colors` object to a profile, for example:

```json
{"esc":"#ff0000", "a":[0,255,0]}
```

Then validate and send either stored per-key configuration or one real-time
frame:

```bash
spade65ctl per-key-rgb spade65-profile.json --dry-run
spade65ctl per-key-rgb spade65-profile.json --confirm
spade65ctl stream-rgb spade65-profile.json --dry-run
spade65ctl stream-rgb spade65-profile.json --confirm
```

Keys absent from `colors` are black/off in the generated frame. Per-key and
streaming transports have been validated over wired USB. `stream-rgb` sends one
host-driven frame; continuous AP effects and custom timelines require the GUI
or background service to keep running and are not stored as a self-running
firmware animation.

### Dongle lighting and sleep timers

The timer command deliberately searches only for dongle PID `0356`:

```bash
spade65ctl sleep --light-off 10 --hibernate 30 --dry-run
spade65ctl sleep --light-off 10 --hibernate 30 --confirm
```

Valid light-off values are 1, 2, 5, 10, 15, 20, 25, or 30 minutes. Valid
hibernation values are 3, 5, 10, 15, 20, 25, 30, or 60 minutes. This report has
not been physically tested because the matching dongle was not available.

### Reset

Reset can erase settings stored by the keyboard. Inspect the packet first and
use the extra acknowledgement only when a reset is genuinely necessary:

```bash
spade65ctl reset --dry-run --i-understand-reset
spade65ctl reset --confirm --i-understand-reset
```

The GUI uses an equivalent additional typed confirmation. Reset has not been
sent to the available keyboard because no guaranteed keymap readback/restore
path exists.

## Import profiles from the original software

The converter accepts the original JSON wrappers containing `Keyboard_Export`,
`Macro_Export`, and `Light_Export`. Conversion is offline and never forwards an
arbitrary packet from the input file:

```bash
spade65ctl vendor-import original.KeyAssign profile.json
spade65ctl vendor-import original.Macro profile.json \
  --base profile.json --force
spade65ctl vendor-import original.APMode profile.json \
  --base profile.json --force
spade65ctl profile validate profile.json
```

`--base` merges the next vendor section into an existing native profile, and
`--force` permits replacing the output file. Importing does not write to the
keyboard. Review and validate the converted profile before any apply command.

## Background effects and application associations

Release users should use **Settings → Background service** in the packaged GUI;
it supplies the correct AppImage, `Spade65CLI.exe`, or macOS application
executable and separates configuration from activation. The `spade65ctl`
notation below applies to source or Python-package installations.

Create a host-service configuration, edit its profile paths and process-name
associations, then run it:

```bash
spade65ctl service example spade65-service.json
spade65ctl service run spade65-service.json
```

By default, the service runs only AP effects and custom timelines. It can keep
host-streamed lighting active after the GUI closes and select profiles according
to the active application. On Wayland, where no portable foreground-window API
exists, it falls back to the first configured rule whose process is running;
rule order matters. This service has no tray icon; the system tray belongs to
the separate native GUI process.

Automatic keymap/profile writes are disabled by default. Enabling them requires
both `"allow_profile_writes": true` in the configuration and the independent
runtime flag:

```bash
spade65ctl service run spade65-service.json \
  --allow-profile-writes
```

Generate, but do not install, a startup integration file with:

```bash
spade65ctl service integration spade65-service.json launcher-output
```

It produces a systemd user unit on Linux, a Startup `.cmd` launcher on Windows,
or a LaunchAgent `.plist` on macOS. Review the generated file before installing
it. Full association behavior and OS limitations are in the
[host-features guide](host-features.md).

## What is stored on the keyboard and what is host-driven

Commands for built-in effects, debounce, timers, keymaps, macros, and stored
per-key configuration send the vendor configuration reports intended for the
device. Those settings are expected to remain when the keyboard moves to
another operating system, as they do with the original software. Features that
stream frames—AP effects, audio-reactive effects, custom timelines, and
application associations—are host-driven and work only while the GUI or service
is running.

Spade65 cannot safely read the full current keymap, macros, or every setting
back from the keyboard. A saved profile and GUI library backup are therefore
the recovery source, not an assumed firmware readback.

## Troubleshooting

### `Spade65 not found`

On Linux, inspect the known USB identities:

```bash
lsusb -d 0603:0351
lsusb -d 0603:0352
lsusb -d 0603:0356
```

Reconnect the cable or dongle and run `spade65ctl probe` again. If a production
unit has a different VID/PID, save its USB and descriptor information before
changing source constants; it may be another hardware revision.

### `Permission denied: /dev/hidrawN`

Install the udev rule, reconnect the device, and inspect the node as your normal
user:

```bash
getfacl /dev/hidrawN
```

### `report length mismatch` or descriptor validation failure

Do not force the write and do not add an arbitrary raw-HID fallback. Save
`spade65ctl probe --json` output and compare it with the verified descriptor.
The mismatch can indicate the wrong interface or an unsupported firmware or
hardware revision.

### Port 8765 is already in use

A normal second GUI launch should activate the first window. If the port is
owned by another program, stop that program yourself or choose a different
local port explicitly:

```bash
spade65ctl gui --port 8875
```

Spade65 never kills or takes over an unrelated listener.

### Linux desktop window is blank or reports EGL/graphics errors

Use the latest AppImage. As a renderer-independent fallback, run:

```bash
./Spade65-Linux-x86_64.AppImage gui --no-browser
```

Then open `http://127.0.0.1:8765/` in an existing browser. Distribution-specific
Wayland and runtime notes are in the [cross-platform guide](cross-platform.md).

### The keyboard temporarily stops responding

Stop any streaming service, then unplug and reconnect the cable or dongle. Do
not repeat reset commands and do not try firmware files extracted from the
official installer. Record the command and `probe --json` output before filing
an issue.

### An executable opened from the file manager shows no error

Startup failures are shown through an available desktop notification/dialog and
written to a user log:

- Windows: `%LOCALAPPDATA%\Spade65\Logs\launcher.log`
- Linux: `${XDG_STATE_HOME:-~/.local/state}/spade65/launcher.log`
- macOS: `~/Library/Logs/Spade65/launcher.log`

Run the CLI executable in a terminal when command output needs to remain
visible.

## Further documentation

- [Cross-platform installation and runtime behavior](cross-platform.md)
- [Host service, import, timeline, and backup details](host-features.md)
- [Hardware verification results](hardware-verification.md)
- [Feature-parity audit](parity.md)
- [Protocol research](protocol.md)
- [Development guide](development.md)

Protocol and development internals intentionally live in those dedicated
documents so this guide can remain focused on safe user workflows.
