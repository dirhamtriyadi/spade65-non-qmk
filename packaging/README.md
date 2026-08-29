# Release packaging

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

The frozen `Spade65` launcher opens the localhost GUI in the default browser
when started without arguments. A second launch verifies the existing Spade65
session on port 8765, reopens it, and exits instead of failing on the occupied
port. Linux and macOS pass CLI arguments to this executable. The Windows ZIP
contains both windowed `Spade65.exe` for the GUI and console
`Spade65CLI.exe` for visible CLI output and errors.
The sidebar's **Quit application** action shuts down the authenticated local
server; merely closing the browser tab keeps it available for a later launch.

## Local builds

Install the project HID dependency and the build tools first:

```sh
python -m pip install -r requirements-build.txt ".[cross-platform]"
```

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

Linux requires `curl` and `sha256sum`; the script downloads the official
`AppImage/appimagetool` 1.9.1 release and verifies its pinned SHA-256 before
execution. A custom `APPIMAGETOOL_URL` must be paired with the corresponding
`APPIMAGETOOL_SHA256`. The embedded type-2 runtime is also downloaded by
immutable GitHub asset ID and hash-checked; overriding `APPIMAGE_RUNTIME_URL`
requires the matching `APPIMAGE_RUNTIME_SHA256`. Verification is never skipped,
and `--runtime-file` prevents appimagetool from fetching its mutable
`continuous` runtime. macOS requires Xcode command-line tools and a universal2
Python plus universal2 native dependencies. The release workflow builds
`hidapi` from source for both macOS architectures and scans every Mach-O file in
the finished application to reject thin native binaries. Every packaged
executable also runs a no-browser/no-device-enumeration smoke test before its
artifact is uploaded; Windows/macOS still load the native HID extension so
missing linked libraries fail the build without touching a keyboard.

The Windows script validates both executables, creates the ZIP, extracts it to
a temporary directory, and runs `Spade65CLI.exe --smoke-test` from the extracted
archive. The macOS script verifies the DMG, mounts it read-only, inspects the app,
and reruns the smoke test from the mounted image.

On macOS, install the native HID extension as universal2. In a clean virtual
environment this command builds both slices instead of accepting a thin wheel:

```sh
ARCHFLAGS="-arch x86_64 -arch arm64" MACOSX_DEPLOYMENT_TARGET=11.0 \
  python -m pip install --force-reinstall --no-cache-dir \
  --no-binary=hidapi "hidapi==0.15.0"
```

The macOS script reads the application version from `pyproject.toml`, verifies
it against `spade65.__version__`, and embeds it in the app automatically.

The Windows ZIP and macOS application are currently unsigned. The macOS build
receives only an ad-hoc signature and is not notarized, so downloaded releases
can show SmartScreen or Gatekeeper warnings. Production trust requires private
Windows code-signing and Apple Developer ID/notarization credentials configured
as repository secrets; no signing keys should be committed.
