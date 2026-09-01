**English** · [Bahasa Indonesia](id/host-features.md)

# Cross-platform host features

## Converting exports from the original software

Original export files are JSON with a `filename`, `version`, and `value`
wrapper. The converter accepts the `Keyboard_Export`, `Macro_Export`, and
`Light_Export` sections and merges them into a native profile:

```bash
spade65ctl vendor-import profile.KeyAssign profile.json
spade65ctl vendor-import macro.Macro profile.json --base profile.json --force
spade65ctl vendor-import lighting.APMode profile.json --base profile.json --force
spade65ctl profile validate profile.json
```

The GUI provides an **Import vendor** button for the same flow. Conversion is
always offline; a vendor file never contains or sends arbitrary HID packets.

## GUI library backup

**Backup library** downloads one `spade65-library-v1` JSON file containing every
localStorage profile, the active profile, language, and per-model layout
selection map. **Restore library** validates every profile through the backend
before asking for confirmation to replace the local library. Older backups that
contain only a `layout` field are still migrated when a Spade65 is next detected.

## Custom-effect timeline

On the Lighting page, set the per-key colors and then choose **Capture frame**.
Each frame lasts 20–60000 ms. A timeline can contain up to 200 frames, can loop,
is stored in `settings.custom_timeline`, and uses the same USB streaming
transport as AP mode. Timeline data is never written to firmware flash.

## Desktop tray and login startup

In the native application, **Settings → Desktop integration** controls whether
closing the window hides it in the system tray and whether Spade65 starts after
the current user signs in. The tray menu can reopen the existing window or quit
the process. Start-after-sign-in invokes `gui --start-hidden`; enabling and
disabling it writes or removes only Spade65's per-user launcher.

The implementation reuses the desktop runtime already bundled for each host:
Qt on Linux, WinForms on Windows, and Cocoa on macOS. Linux environments without
a usable tray keep normal close-to-exit behavior. A hidden login launch also
falls back to a visible window so it cannot strand an inaccessible process.

Keeping the GUI in the tray is not a replacement for the service below. Hidden
WebViews can be throttled by their renderer; use the background service for
reliable AP/timeline playback and application associations after the window is
closed or hidden.

## Background service and application associations

### Release packages (recommended)

Open **Settings → Background service** in the packaged application. The page
detects the current operating system and release executable, then shows two
separate command blocks:

1. Create the per-user service configuration.
2. After editing that configuration, install and activate the per-user startup
   integration.

The generated commands invoke the current AppImage on Linux,
`Spade65CLI.exe` from the extracted Windows release, or the executable inside
the installed `Spade65.app` on macOS. They do not depend on a source checkout or
the `spade65ctl` command being installed globally.

Move the AppImage, extracted Windows directory, or macOS application to its
permanent location first. Opening the Settings page or copying a command does
not alter operating-system startup. The user must review and run each block
explicitly. Windows activation takes effect at the next sign-in; Linux systemd
and the macOS LaunchAgent are started by the second block.

### Source installations

The `spade65ctl` commands below are for a source or Python-package installation
only. Create an initial configuration:

```bash
mkdir -p ~/.config/spade65
spade65ctl service example ~/.config/spade65/default.json
```

Edit `associations` to contain application process names and profile paths. Then
run:

```bash
spade65ctl service run ~/.config/spade65/default.json
```

On X11, the service uses `_NET_ACTIVE_WINDOW` and `_NET_WM_PID`. Wayland has no
portable foreground-window API, so the fallback selects the first rule whose
process is running. Rule order is therefore significant. Windows uses the Win32
foreground-window API, and macOS uses the frontmost process through System
Events. macOS may request Automation/Accessibility permission.

By default, the service runs only AP effects and timelines. For an application
switch to write a keymap as well, both permissions must be enabled:

1. `"allow_profile_writes": true` in the configuration file.
2. The `--allow-profile-writes` runtime flag.

An enabled background profile write uses the same complete transaction as the
foreground UI: keymap, referenced macros, cached profile lighting, then cached
profile debounce. Both the main and short companion collections must pass
descriptor validation before the keymap is sent, and no timer is appended on a
wired device. See the [protocol notes](protocol.md#profile-apply--setkeymatrix-transaction)
for exact report delays.

Every write is still checked against the HID descriptor. From a source
installation, a launcher for the current operating system can be generated
without installing it immediately:

```bash
spade65ctl service integration ~/.config/spade65/default.json launcher-output
```

Use `--platform linux`, `windows`, or `macos` to generate a launcher for another
platform. A platform other than the host also requires `--target-config`,
`--target-executable`, and `--target-runtime packaged` or
`--target-runtime python`; the command refuses to guess the target's
configuration path, executable, or runtime from this host and reports the
missing options instead. When `--target-config` is supplied, the positional
configuration path can be omitted. Linux produces a systemd unit, Windows
produces a `.cmd` launcher for the Startup folder, and macOS produces a
LaunchAgent `.plist`.

This service and its launcher are background components that continue without
the GUI. The service itself has no tray icon and requires no additional desktop
toolkit; the tray belongs only to the native GUI described above. Audio-reactive
effects remain in the GUI because the service does not request microphone access
silently.

## Key tester

The **Key tester** page lights up each key as it is pressed and keeps it marked
afterwards, so anything still plain has not been tried. It also reports the
`KeyboardEvent.code` the host received, which is what makes it useful after
writing a keymap: press the physical key and confirm the box that lights is the
one the profile assigned.

It reads key events from the operating system rather than HID feature reports,
so it is the only page that works over every connection this keyboard offers —
the cable, the 2.4 GHz receiver, and Bluetooth. Configuration itself still
requires the wired interface.

Two keys cannot be relied on there. Fn is resolved inside the keyboard firmware
and emits no usage at all, confirmed with `evtest`, so it can never light up on
any tester. The desktop commonly claims the Super key before the page sees it,
so a dark Super key is not evidence that the key is broken. Both are drawn with
a dashed outline and excluded from the tested count.

A single spacebar event cannot say which segment of a split spacebar was
struck, so every space segment lights together.

## Read-only information

```bash
spade65ctl info
```

This command does not send a HID report. On Linux, `usb_revision` is read from
sysfs; on Windows and macOS, it comes from HIDAPI enumeration metadata. This
value is not a firmware version. The original software obtains its firmware
version from `GetFWVersion` in a closed Windows native add-on; without a verified
request method, this project does not send a guessed HID request. Battery data
is shown only when Linux exports it through `power_supply` for the same device;
there is no verified battery reader for Windows or macOS yet.

Physical test results and the boundaries of operations intentionally not sent
are documented in
[`hardware-verification.md`](hardware-verification.md).
