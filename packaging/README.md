# Release packaging

**English** · [Bahasa Indonesia](README.id.md)

Pushing a `vMAJOR.MINOR.PATCH` tag runs `.github/workflows/release.yml`. The tag
must match `project.version` in `pyproject.toml`; a mismatch stops the release.
The workflow tests the source, builds on each target operating system, and
publishes exactly these GitHub Release assets:

- `Spade65-Windows-x64.zip`
- `Spade65-Linux-x86_64.AppImage`
- `Spade65-macOS-universal.dmg`

Manual workflow dispatch may resume or replace assets on an unpublished draft
for an existing tag. It deliberately refuses to overwrite a published release.
Runs for the same tag are serialized so draft creation and uploads cannot race.

Starting with v0.7.0, the frozen `Spade65` launcher starts the authenticated
localhost GUI on port 8765 inside a standalone PyWebView window. The interface
is still the repository's local HTML, CSS, and JavaScript—not a rewrite as fully
native widgets. If the platform WebView cannot load, the launcher reports the
failure and falls back to the default browser.

A second packaged-app launch verifies the existing Spade65 token, calls its
authenticated activation route, restores the existing window, and exits instead
of failing on the occupied port. The explicit `gui` command uses the same
coordinator. Port ownership is claimed before WebView initialization and an
activation arriving during startup is queued until the window exists. A foreign
service on 8765 is never killed or treated as Spade65. When close-to-tray is
enabled and a native tray is available, closing the desktop window hides it;
otherwise it exits. **Quit Spade65** in the tray or **Quit application** in the
GUI closes the window and localhost server. Settings can install per-user login
startup, which invokes the package with `gui --start-hidden`. In browser mode,
closing only the tab leaves the server running until **Quit application**,
Ctrl+C, or process termination.

Windowed processes without a console write stdout/stderr to a per-user launcher
log and display a best-effort native startup error. Log roots are
`%LOCALAPPDATA%\Spade65\Logs` on Windows,
`${XDG_STATE_HOME:-~/.local/state}/spade65` on Linux, and
`~/Library/Logs/Spade65` on macOS.

PyWebView uses a persistent, app-specific profile. Profile exports and library
backups use a native Save-dialog bridge on Linux/macOS; Windows uses WebView2's
UI-thread download handler, and explicit browser mode retains normal downloads. Its
custom storage roots are `%LOCALAPPDATA%\Spade65\WebView` on Windows and
`${XDG_DATA_HOME:-~/.local/share}/spade65/webview` on Linux. On macOS, Cocoa
WebKit persists the default website data store in an OS-managed location for
bundle ID `io.github.dirhamtriyadi.spade65`; pywebview does not expose a custom
path for that backend. Browser mode has a separate browser-owned storage
profile; backup/restore is the portable bridge between the two.

Linux and macOS pass CLI arguments to the packaged executable. The Windows ZIP
contains both windowed `Spade65.exe` for the GUI and console `Spade65CLI.exe`
for visible CLI output and errors. The CLI `gui --browser` flag forces browser
mode; `gui --no-browser` runs only the loopback server.

## Local builds

Install the HID, desktop, and build dependencies first:

```sh
python -m pip install -r requirements-build.txt ".[cross-platform,desktop]"
python -m pip check
```

On Debian/Ubuntu build hosts, also install the EGL loader used when the
packaged QtWebEngine backend is imported by the headless smoke test:

```sh
sudo apt-get update
sudo apt-get install --no-install-recommends \
  libegl1 libgl1 libxcb-shape0 libxcb-image0 libxcb-xkb1 libxcb-icccm4 \
  libxkbcommon-x11-0 libxcb-util1 libxcb-cursor0 libxcb-keysyms1 \
  libxcb-render-util0 libpulse0 curl coreutils
```

Use the equivalent EGL, curl, and SHA-256 utility packages on other Linux
distributions. A normal graphical desktop often already provides EGL, but the
build now states this dependency explicitly instead of relying on that.

For editable source installs that are not building release artifacts, Linux can
use `python -m pip install -e ".[desktop]"`; Windows and macOS use
`python -m pip install -e ".[cross-platform,desktop]"`. A base install can still
run `gui --browser` or `gui --no-browser` without the native desktop extra.
Use CPython 3.12 on Windows and macOS when building the full desktop package:
the pinned pysysaudio 0.1.3 native loopback wheels are published through
CPython 3.12. Linux packaging remains on CPython 3.13.

Build on the target computer with one cross-platform command. It automatically
selects the native script and uses the same Python interpreter that invoked it:

```sh
python packaging/build.py
```

This path does not require GitHub Actions. It produces the same exact filename
under `artifacts/` and runs the same packaged smoke test as CI. To inspect the
selected command without building, use `python packaging/build.py --dry-run`;
`--help` lists the supported options.

The native scripts remain directly runnable when platform-specific automation
needs them:

```sh
bash packaging/build_linux.sh
pwsh -File packaging/build_windows.ps1
bash packaging/build_macos.sh
```

Linux requires an EGL loader, `curl`, and `sha256sum`; the script downloads the official
`AppImage/appimagetool` 1.9.1 release and verifies its pinned SHA-256 before
execution. A custom `APPIMAGETOOL_URL` must be paired with the corresponding
`APPIMAGETOOL_SHA256`. The embedded type-2 runtime uses GitHub's public release
download route instead of the rate-limited API asset route. Its exact bytes are
still pinned and verified with SHA-256; overriding `APPIMAGE_RUNTIME_URL`
requires the matching `APPIMAGE_RUNTIME_SHA256`. Verification is never skipped,
and `--runtime-file` prevents appimagetool from independently fetching an
unverified runtime.

The Linux x86_64 package bundles PySide6 and QtWebEngine. This materially
increases the AppImage size compared with the earlier browser-only package. The
official artifact is built and smoke-tested on the `ubuntu-22.04` x86_64 runner
(glibc 2.35), which is the supported Linux baseline. Newer distributions are
usually compatible, but glibc's version alone is not a complete compatibility
guarantee. A manual artifact inherits libc requirements from its build host, so
build on the oldest target environment you intend to support. A graphical
session and the normal Qt display dependencies are required to open the window,
while the packaged smoke test remains headless.

The AppImage deliberately excludes the build host's `libstdc++`, `libgcc_s`,
GBM, X11 core, ALSA, PulseAudio, Fontconfig, FreeType, Expat, and graphics-dispatch
libraries. Those libraries load GPU/audio drivers or parse host configuration
and must therefore stay aligned with the target system. The build fails if one
re-enters the bundle. This prevents an Ubuntu baseline library from shadowing a
newer Mesa/Intel driver, ALSA plugin, or Fontconfig installation on rolling
distributions.

The PyInstaller build uses local hooks for the widgets-only QtWebEngine backend.
They omit the unused QML tree, Qt Data Visualization, and optional virtual
keyboard/Quick 3D tooling that would otherwise pull GPL-only Qt modules into the
AppImage. `build_linux.sh` independently rejects Qt Graphs, Data Visualization,
Quick 3D, Quick Timeline, Virtual Keyboard, and Wayland Compositor filenames
before packaging. It also requires the generic XCB support libraries to be
collected, while leaving driver-facing EGL/GL dispatch to the host graphics
stack. Do not remove these checks when upgrading PySide6 or
PyInstaller; rebuild, inspect, and re-license the actual payload instead.

The AppImage supports the verified Linux `hidraw` transport and intentionally
does not bundle the optional HIDAPI extension or its vendored native libraries.
Developers can still test the HIDAPI override from a source installation with
the `cross-platform` extra; that override is not part of the released AppImage.

After PyInstaller finishes, `linux_legal_inventory.py` reads the generated
`COLLECT-00.toc`. Official Ubuntu jobs set `SPADE65_STRICT_LINUX_LEGAL=1`, so
every native binary collected from `/usr`, `/lib`, `/bin`, or `/sbin` must map
to an installed dpkg package and an available Debian copyright file. The
AppImage stores the resulting manifest and copied files under
`usr/share/doc/spade65/linux-system-libraries`. Manual builds on non-dpkg hosts
remain supported and receive a source-path-only manifest whose warning makes
the unverified system attribution explicit. The exact upstream license files
for the pinned type-2 runtime commit and appimagetool 1.9.1 are included in the
normal offline license directory.

Windows uses the Edge Chromium backend and requires Microsoft Edge WebView2
Runtime on both build/smoke-test hosts and end-user systems. Current Windows
10/11 installations commonly include it, but the runtime is not silently
replaced with legacy MSHTML; failure activates the documented browser fallback.

macOS requires Xcode command-line tools and a universal2 Python plus universal2
native dependencies. The release workflow builds
with the SHA-256-verified Python.org 3.12.10 universal2 installer instead of
assuming that an architecture-selected CI interpreter is fat. It then builds
`hidapi` from source for both macOS architectures and scans every Mach-O file in
the finished application to reject thin native binaries. The desktop renderer
uses Cocoa/WebKit through PyObjC. The bundle permits local networking for the
loopback UI and includes separate microphone and system-audio capture usage
descriptions. Core Audio tap capture requires macOS 14.2 or newer; microphone
fallback and the rest of the application retain the macOS 11 baseline.

Every packaged executable runs a no-window/no-browser/no-device-enumeration
smoke test before upload. It imports the selected PyWebView backend and checks
the packaged HTTP resources without creating an interactive window.
Windows/macOS still load the native HID and pysysaudio extensions so missing
linked libraries fail the build without touching a keyboard or opening an
audio device. Linux verifies NumPy, CFFI, SoundCard's package data, and its
PulseAudio runtime prerequisite without connecting to the headless CI audio
server.

The Windows script validates both executables, creates the ZIP, and extracts it
to a temporary directory. It checks that LICENSE, `THIRD-PARTY-NOTICES.md`, and
the `licenses/` texts survived archiving, then runs `--smoke-test` from the
extracted archive through both `Spade65.exe` and `Spade65CLI.exe`; either
non-zero exit fails the build. The macOS script verifies the DMG, mounts it
read-only, inspects the app, and reruns the smoke test from the mounted image.

On macOS, install the native HID extension as universal2. In a clean virtual
environment, first verify that the selected Python itself contains both slices,
then use the same helper as CI. The helper forces a source wheel build, uses the
pinned Cython/setuptools/wheel versions from `requirements-build.txt`, and
hash-checks the pinned `hidapi` source archive before compiling it. It rejects a
thin result before packaging:

```sh
resolved_python=$(python -c \
  'import pathlib, sys; print(pathlib.Path(sys.executable).resolve())')
lipo "$resolved_python" -verify_arch x86_64 arm64
bash packaging/build_macos_hidapi.sh
bash packaging/build_macos_pysysaudio.sh
python packaging/build.py
```

`build_macos_pysysaudio.sh` solves the same problem from the other direction.
`pysysaudio` publishes arm64, x86_64 and universal2 wheels under one tag, and
pip prefers the single architecture matching the runner, which PyInstaller then
refuses with `IncompatibleBinaryArchError` while assembling a universal2 app.
The helper installs the published universal2 wheel by pinned URL and SHA-256
and verifies the extension with `lipo`. It does not build from the sdist,
because that project's own `setup.py` passes `-mmacosx-version-min=14.2` for
the ScreenCaptureKit API it wraps, so no 11.0 build exists to make.

GitHub Actions installs the pinned Python.org package after verifying SHA-256.
For a manual build, install a current Python.org universal2 distribution first;
the helper fails closed if the interpreter or resulting HID extension is thin.

CI has two native-package layers. Every push to `main` runs non-publishing
Windows, Linux, and macOS package preflight jobs. A release tag rebuilds all
three artifacts from the immutable tag commit and only then permits publishing;
preflight artifacts are not reused as release assets. Both layers use the CI
dependency contract: Windows installs
`.[cross-platform,desktop]`, Linux installs `.[desktop]` for its hidraw-only
AppImage, and macOS installs the `desktop` extra then builds HIDAPI universal2
separately. Windows and macOS package with CPython 3.12.10; the general source
test matrix still covers Python 3.10 and 3.13. Each also installs
`requirements-build.txt`. All three run `pip
check`, the packaged smoke test, and native artifact verification.

The macOS script reads the application version from `pyproject.toml`, verifies
it against `spade65.__version__`, and embeds it in the app automatically.

The Windows ZIP and macOS application are currently unsigned. The macOS build
receives only an ad-hoc signature and is not notarized, so downloaded releases
can show SmartScreen or Gatekeeper warnings. Production trust requires private
Windows code-signing and Apple Developer ID/notarization credentials configured
as repository secrets; no signing keys should be committed.

PyWebView and its platform runtimes retain their upstream license terms. Review
[`THIRD-PARTY-NOTICES.md`](../THIRD-PARTY-NOTICES.md), which is copied into
every release artifact, together with
the licensing material for
[pywebview](https://github.com/r0x0r/pywebview/blob/master/LICENSE.md),
[Qt for Python/PySide6](https://doc.qt.io/qtforpython-6/licenses.html),
[Microsoft Edge WebView2](https://www.microsoft.com/legal/webview2terms), and
[PyObjC](https://github.com/ronaldoussoren/pyobjc/blob/main/LICENSE.txt),
[SoundCard](https://github.com/bastibe/SoundCard/blob/0.4.6/LICENSE),
[NumPy](https://github.com/numpy/numpy/blob/v2.5.2/LICENSE.txt), and
[pysysaudio](https://github.com/scottjg/pysysaudio/blob/v0.1.3/LICENSE) when
redistributing the release artifacts. Repository copies of the relevant
[GPL-3.0](../licenses/GPL-3.0.txt) and
[LGPL-3.0](../licenses/LGPL-3.0.txt) texts are also available for Qt components
distributed under those license options.
