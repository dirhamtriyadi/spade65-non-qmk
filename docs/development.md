**English** · [Bahasa Indonesia](id/development.md)

# Development guide

## Architecture

```text
spade65ctl.py
  └── spade65.cli
        ├── spade65.protocol   # constants and pure packet builders
        ├── spade65.device     # OS-neutral descriptor model and parser
        ├── spade65.transport  # cross-platform backend selector
        ├── spade65.hidraw     # Linux backend: sysfs + ioctl
        ├── spade65.application # shared port ownership + GUI lifecycle
        ├── spade65.instance   # localhost instance identity/activation
        ├── spade65.gui        # loopback HTTP API + web assets
        └── spade65.desktop    # PyWebView window lifecycle
              └── spade65.web # HTML/CSS/JS + locale catalogs

packaging/
  ├── build.py                 # manual build dispatcher for the host OS
  ├── launcher.py              # desktop default, browser fallback, smoke test
  ├── spade65.spec             # assets + per-platform WebView backend
  └── build_*                  # native Windows, Linux, and macOS packages
```

This separation is intentional:

- `protocol.py` can be tested without Linux or a keyboard.
- `hidraw.py` does not know the meaning of opcodes.
- `transport.py` retains hidraw on Linux and uses HIDAPI, which can read
  descriptors, on Windows and macOS.
- `cli.py` handles safety validation and user experience.
- `gui.py` binds only to loopback, creates a session token, validates the
  `Host`/`Origin` authority to reject DNS rebinding, and serves the same API and
  assets to the WebView and browser.
- `desktop.py` manages PyWebView, persistent storage, server/window lifecycle,
  downloads, and activation of an existing instance.
- `application.py` claims the port atomically, starts the server before the
  renderer, queues activation during window startup, and shares one path between
  the no-argument executable and the `gui` subcommand.
- `instance.py` accepts only an instance whose Spade65 page and token have been
  verified; it does not take over another service on port 8765.
- `web/locales/index.json` registers languages; `en.json` is the canonical and
  default catalog, and every other locale must contain the same keys.
- `packaging/launcher.py` opens the desktop window on stable port 8765 when no
  arguments are supplied, falls back to the browser if the native backend fails,
  activates the existing window on a second launch, and passes other arguments
  to the CLI.

The v0.7.0 GUI is not a rewrite using native widgets. The interface layout and
logic remain HTML/CSS/JavaScript rendered in a native PyWebView shell. The
`desktop` extra installs the platform backend: PySide6/QtWebEngine on Linux,
pythonnet/Edge WebView2 on Windows, and PyObjC/Cocoa/WebKit on macOS. The
`cross-platform` extra still installs `hidapi` for Windows and macOS; do not add
a write fallback when HIDAPI cannot read a descriptor. Windows requires Edge
WebView2 Runtime on the host.

The desktop uses `private_mode=False` and an application-specific storage
directory so `localStorage` is not lost when the window closes.
`desktop_storage_path()` selects Local AppData on Windows and XDG data on Linux.
Cocoa WebKit uses the persistent default website data store managed by macOS for
the application bundle ID because that backend ignores pywebview's custom path.
On Linux and macOS, `DesktopApi` validates JSON and opens a native Save dialog
for profile and library exports. Windows uses the WebView2 download handler on
the UI thread; browser mode continues to use Blob downloads. Closing the window
or calling the quit endpoint stops the server; there is no system tray. Browser
mode and `--no-browser` remain available through the CLI.

The GUI layouts use the `ItemCss` coordinates for `SPADE65-01` through
`SPADE65-04` found in `KeyBoardStyle.js`. The repository stores only the geometry
and an original HTML/CSS implementation; vendor PNG images must not be copied
into Git. `web/layout-state.js` is a pure resolver for layout enums, storage
migration, USB/dongle normalization, and the disconnected fallback. Neither the
firmware nor the original software provides physical-layout readback, so the
frontend restores only a host preference and states this explicitly in the UI.

## Editing the web interface

Files under `spade65/web/` are the canonical frontend source. They are served by
the development server and copied into release packages directly; the repository
does not commit a generated or minified copy. Keep the HTML, JavaScript, CSS, and
JSON catalogs readable so the GUI can be maintained without reconstructing a
production bundle.

Install the small, pinned Python formatters and format all JavaScript and CSS:

```bash
python -m pip install -e ".[dev]"
python tools/format_web.py
```

For native GUI development, install both extras in one command:

```bash
python -m pip install -e ".[desktop,dev]"
```

`python tools/format_web.py --check` verifies formatting without changing files.
The formatter deliberately does not rewrite `index.html` or locale JSON because
those files are already stored as readable source.

## Running quality checks

```bash
python -m unittest discover -v
python -m compileall -q spade65 spade65ctl.py tests tools
python tools/format_web.py --check
node --check spade65/web/layout-state.js
node --check spade65/web/app.js
node tests/layout_state.test.js
python spade65ctl.py rgb fixed --dry-run
python spade65ctl.py sleep --light-off 10 --hibernate 30 --dry-run
```

For transport changes, add synthetic descriptors to `tests/test_hidraw.py`. For
packet changes, add offset-by-offset assertions to `tests/test_protocol.py`.

Locale changes must preserve key parity with `en.json`, named `{...}`
placeholders, and the English fallback. Follow
[`localization.md`](localization.md), and test both static text and dynamic
renderers.

Desktop-packaging changes must be tested on the target operating system. Every
executable must pass `--smoke-test` without creating a window, opening a browser,
enumerating devices, or writing HID before it is packaged. The smoke test imports
the platform WebView backend and checks localhost assets and routes; lifecycle
unit tests use a mock WebView so they do not require a display. Continue to test
window close, **Quit application**, second-launch activation, import, and export
downloads manually on the target operating system.

The test workflow for every push to `main` runs a native Windows, Linux, and
macOS packaging preflight without publishing. The tag workflow then installs the
`desktop` extra, rebuilds immutable source from the tag, checks the universal
Mach-O binary on macOS, and publishes the three assets only after all are
available. The release AppImage is built and smoke-tested on an Ubuntu 22.04
x86_64 runner (glibc 2.35) and includes PySide6/QtWebEngine, so reviewing artifact
size is part of packaging review. An AppImage built manually inherits the build
machine's glibc baseline and does not automatically have the same portability.
See [`releasing.md`](releasing.md).

## Implementation safety rules

1. Every write command must continue to require `--confirm`.
2. Every write command must provide `--dry-run`.
3. Select interfaces by VID, PID, usage, report ID, and report length.
4. A descriptor mismatch is an error, not a warning.
5. Firmware updates, raw flashing, and bootloader access remain out of scope
   until a recovery procedure has been tested; do not create endpoints or
   builders for them.
6. Do not write reports to ordinary boot-keyboard or consumer interfaces.
7. If a command is valid only for the dongle, restrict its PID in code.
8. The GUI may bind only to loopback, must use a session token, must reject
   foreign `Host` values and mismatched browser `Origin` values, and may expose
   only an allowlist of configuration actions with validated builders.
9. JSON profiles are declarative data; never accept raw report bytes or packets.

## Hardware-testing workflow

Create a separate branch and proceed from the smallest operation:

1. Run `probe` over USB and through the dongle.
2. Apply one built-in RGB effect.
3. Set debounce to the default 5 ms first.
4. Set dongle timers.
5. Read current state if the get-report format is known.
6. Apply per-key RGB.
7. Remap one key.
8. Test layers and macros.

After every write, test keyboard input with a tool such as `evtest` or a keyboard
tester page. Disconnect and reconnect the device before concluding that a
command failed permanently.

## Adding a command

1. Create a builder that returns `bytes` in `protocol.py`.
2. Validate every range before constructing the buffer.
3. Add a test that checks report length and important offsets.
4. Add a CLI handler that uses `_write_report()`.
5. Select the narrowest applicable usage and PID.
6. Document its status as untested until hardware testing is complete.

## Key-remapping status

Known facts:

- Report ID `07`, opcode `03`, length 620 bytes.
- Data begins at offset 8.
- There are three layers.
- Each matrix slot uses two bytes.
- The wired internal matrix has 102 slots; the UI layout has 70 keys.
- Default USB HID keycodes are available in the vendor's `SKLocation` module.

Implementation progress:

1. Complete: extract entry `0x06030x0351` from `SKLocation.js` locally.
2. Complete: convert the mapping into an original 102-slot constant in
   `spade65/keymap.py`.
3. Complete: add the `KeyAssignment(modifiers, usage)` model and three-layer
   builder.
4. Complete: create `keymap export-default`, which generates only offline JSON
   and frames.
5. Complete: implement JSON profiles for keyboard assignments, macros, and
   colors.
6. Complete: enable writes with dry-run, descriptor validation, and an additional
   confirmation.
7. Next: compare one remap against a USB capture and validate macros on hardware.

Do not build the keymap from only the 70-key physical order. The firmware uses
empty slots in its 102-element matrix, so removing the empty slots can shift
every assignment.

## Continuing local reverse engineering

Vendor artifacts are not stored in the repository. If the official installer is
available at the checkout root:

```bash
innoextract --extract --output-dir extracted Spade65_SETUP_20240403.exe
python tools/extract_asar.py extracted/app/resources/app.asar reverse_engineered --prefix backend
python tools/deobfuscate_jupeng.py \
  reverse_engineered/backend/protocol/device/keyborad/JupengSeries.js \
  reverse_engineered/backend/protocol/device/keyborad/JupengSeries.deobfuscated.js
```

`innoextract` is a system tool and is not bundled. The two Python scripts in the
repository use only the standard library.

## Useful Windows captures

If necessary, use USBPcap and Wireshark and make only one change in each capture:

- Capture A: fixed RGB, brightness 1.
- Capture B: fixed RGB, brightness 2.
- Capture C: remap A to B.
- Capture D: restore B to A.

A single-delta comparison reduces ambiguity. Record the wired/dongle mode,
firmware version, and the action timestamp. Avoid capturing a firmware update.

## Sensitive data and vendor artifacts

- `probe --json` does not display the `unique`/serial value by default. Do not
  use `--include-unique` in public artifacts.
- Do not commit the installer, firmware, `app.asar`, `.node` binaries, or
  extracted vendor source.
- Commit only interoperability notes and original implementation code.
