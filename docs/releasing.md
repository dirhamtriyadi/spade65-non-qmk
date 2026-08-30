**English** · [Bahasa Indonesia](id/releasing.md)

# Desktop release guide

## Release artifacts

The [`.github/workflows/release.yml`](../.github/workflows/release.yml) workflow
runs when a tag matching `vMAJOR.MINOR.PATCH` is pushed. For version `0.7.3`,
the correct tag is `v0.7.3`. After validation and all three builds succeed, the
workflow publishes a GitHub Release containing exactly three assets:

- `Spade65-Windows-x64.zip`
- `Spade65-Linux-x86_64.AppImage`
- `Spade65-macOS-universal.dmg`

The builds run natively on Windows, Ubuntu, and macOS runners; the three formats
are not produced by a single cross-compiler. The publish job runs only after all
platform jobs succeed and confirms that all three assets exist and are nonempty.
A manual run (`workflow_dispatch`) can rebuild an existing tag only while its
release remains a draft. The workflow refuses to overwrite a published release.

Before a tag is created, every push to the `main` branch runs native package
preflights through the test workflow: the Windows ZIP, Linux AppImage, and macOS
DMG are built and smoke-tested without being published. The release workflow
still rebuilds all three assets from the immutable tagged commit; it does not
reuse preflight output as release assets.

Platform jobs transfer their output to the publish job through temporary
GitHub Actions artifacts. Each temporary artifact has a one-day retention as a
failure-recovery fallback. After a successful release run, the
[`release-artifact-cleanup.yml`](../.github/workflows/release-artifact-cleanup.yml)
workflow deletes those temporary copies. Its manual/bootstrap mode also sweeps
artifacts from older completed release runs. Published GitHub Release assets are
separate objects and are never targeted by this cleanup.

The root [`Jenkinsfile`](../Jenkinsfile) provides an independent, opt-in
fallback for the same test matrix, native packages, and guarded GitHub Release
publication. Controller, agent, credential, security, and storage setup are in
the [Jenkins CI/CD guide](jenkins.md).

When launched without arguments, the built GUI executable serves localhost at
`127.0.0.1:8765` and displays it in a standalone PyWebView window. The UI remains
local HTML, CSS, and JavaScript inside a WebView rather than a fully native
widget interface. If the native backend is unavailable, the launcher opens a
browser as a fallback. A second launch activates and restores the existing
window. Closing the window or choosing **Quit application** stops the server;
there is no system tray. WebView storage is persistent, and downloads for
profile and library exports are enabled.

The Windows ZIP also includes `Spade65CLI.exe`, so CLI output and errors remain
visible. On Linux and macOS, arguments passed to the same executable are
forwarded to the `spade65ctl` command. Explicit modes are available through the
`gui --browser` and `gui --no-browser` subcommands.

## Preparing a tag

The version must match in three places:

1. the Git tag, for example `v0.7.3`;
2. `project.version` in `pyproject.toml`, for example `0.7.3`;
3. `spade65.__version__` in `spade65/__init__.py`, for example `0.7.3`.

Verify the version and run the tests before creating the tag:

```bash
python packaging/check_version.py v0.7.3
python -m unittest discover -v
python -m compileall -q spade65 spade65ctl.py packaging tests
git status --short
```

After the release commit is on the remote and the worktree is in the expected
state, create and push the tag:

```bash
git tag -a v0.7.3 -m "Spade65 v0.7.3"
git push origin v0.7.3
```

Do not move a published tag to a different commit. If a build fails, fix the
source and publish a new patch version. A manual run is appropriate for retrying
an infrastructure failure when the tagged commit has not changed.

## What the workflow validates

Before publishing any assets, the pipeline:

- rejects a tag that has an invalid format or does not match both project
  version declarations;
- runs unit tests and bytecode compilation;
- installs the `desktop` extra and checks the dependency environment before
  building;
- includes the HTML, CSS, JavaScript, every locale catalog, PyWebView, and the
  platform renderer backend in the bundle;
- runs the executable smoke test without creating a window, opening a browser,
  enumerating devices, or writing HID reports; the test imports the WebView
  backend and, on Windows and macOS, still loads the native HID extension so
  broken binary dependencies are detected;
- tests an HTTP locale route from the bundle so missing PyInstaller data is
  detected;
- builds and smoke-tests the x86_64 AppImage on an Ubuntu 22.04 runner (glibc
  2.35), while bundling PySide6 and QtWebEngine;
- rejects unused GPL-only Qt modules after PyInstaller completes, preventing a
  hook or dependency change from silently expanding the license scope;
- extracts the Windows ZIP again and runs the smoke test through the extracted
  console executable, including validation of the Edge WebView2 renderer;
- builds a universal macOS application and checks every Mach-O file for both
  `x86_64` and `arm64` slices; the bundle uses Cocoa/WebKit and declares local
  networking and microphone use for audio-reactive features;
- verifies and mounts the DMG read-only before the final smoke test;
- refuses to publish if any of the three output files is missing or empty.

The packaging smoke test covers startup, desktop-runtime imports, resources,
and application routes only. It does not open the interactive GUI, replace
physical-keyboard testing, or send HID reports. Manual testing on every OS must
still cover second-launch activation, close and quit behavior, browser fallback,
the file picker, and export downloads.

## Local builds

Install the project dependencies and build tools:

```bash
python -m pip install -r requirements-build.txt ".[cross-platform,desktop]"
python -m pip check
```

Run the dispatcher on the target OS. This command automatically selects the
native script, uses the active Python interpreter, runs the packaged smoke test,
and produces the same artifact name as CI:

```bash
python packaging/build.py
```

Use `python packaging/build.py --dry-run` to see which script would run without
building. The platform scripts can also be invoked directly for genuinely
OS-specific automation:

```bash
# Linux
bash packaging/build_linux.sh

# Windows PowerShell
pwsh -File packaging/build_windows.ps1

# macOS
bash packaging/build_macos.sh
```

The scripts write their output to `artifacts/`. A universal macOS build requires
Python and every native dependency in universal2 format; the script deliberately
fails if it finds a single-architecture Mach-O file. A thin `hidapi` wheel is
not sufficient. Use the `ARCHFLAGS` and `--no-binary=hidapi` command documented
in the packaging guide. macOS uses Cocoa/WebKit through PyObjC, and the bundle
metadata permits localhost traffic and explains the microphone prompt for
audio-reactive features.

The Windows build and its smoke test require the Edge WebView2 Runtime on the
host. The Linux build requires an EGL loader, `curl`, and `sha256sum`. On
Debian/Ubuntu, install `libegl1`, `libgl1`, the XCB runtime packages listed in
[`packaging/README.md`](../packaging/README.md), `curl`, and `coreutils`. The
script verifies the hashes of the pinned `appimagetool` and type-2 runtime before
executing them. The PySide6/QtWebEngine AppImage is substantially larger than a
browser-only package. Official assets are built and smoke-tested on Ubuntu 22.04
x86_64 (glibc 2.35); this is the supported baseline, not a compatibility promise
based solely on the glibc version number. A manual build inherits the libc
requirements of its build machine, so it should be produced on the oldest target
OS that needs to be supported.

The official Ubuntu build also enables strict dpkg-based legal inventory. Every
native binary copied from a system directory into the PyInstaller output must
have an owning package and a `/usr/share/doc/<package>/copyright` file; otherwise,
the workflow fails before creating the AppImage. The manifest and copied
copyright notices are stored under
`usr/share/doc/spade65/linux-system-libraries` in the AppImage. A manual build on
a non-dpkg host still works, but its manifest is labeled `source-path-only` and
does not claim that system-library attribution is complete. Low-level details
are documented in [`packaging/README.md`](../packaging/README.md).

The `main` package preflight and the release workflow use the same desktop
dependencies as a manual build: Windows installs
`.[cross-platform,desktop]`; Linux installs only `.[desktop]` because its package
uses `hidraw`; and macOS installs the `desktop` extra before building universal2
HIDAPI with a separate helper. Do not treat unit tests or a headless smoke test
as substitutes for interactive renderer testing on the target OS.

If a desktop package is not yet available for a commit, installation from source
remains supported as described in
[`docs/cross-platform.md`](cross-platform.md). Release-package users do not need
to clone the repository or run Python manually.

## Signing and distribution

The Windows package currently has no code signature. The macOS bundle is signed
ad hoc only to keep the application structure valid, not with an Apple Developer
ID, and the DMG has not been notarized. Windows SmartScreen or macOS Gatekeeper
may therefore warn about a downloaded file. Proceed only when the asset came
from the project's release page and its tag and commit are trusted; installing
from source is the transparent fallback.

Production signing requires a private Windows certificate and Apple Developer
ID/notarization credentials. Never commit certificates, passwords, tokens, or
provisioning secrets. Any future signing support must use repository secrets and
retain the smoke test before publication.

## Safety boundary

The desktop package contains the same configuration features as the source.
Packaging does not add firmware flashing, bootloader access, raw flash/write, or
arbitrary HID packets. Those operations still have no backend route or packet
builder because they can brick the device and no verified recovery procedure is
available. Do not add them to the release workflow, installer, or launcher.
