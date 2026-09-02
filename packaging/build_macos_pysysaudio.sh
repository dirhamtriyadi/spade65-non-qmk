#!/usr/bin/env bash
set -euo pipefail

if [[ $(uname -s) != Darwin ]]; then
  echo "Universal2 pysysaudio preparation must run on macOS" >&2
  exit 1
fi

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
build_python=${SPADE65_BUILD_PYTHON:-python}
wheel_dir="$repo_root/build/macos-pysysaudio-wheel"
pysysaudio_version=0.1.3
pysysaudio_wheel="$wheel_dir/pysysaudio-$pysysaudio_version-cp312-cp312-macosx_14_0_universal2.whl"
pysysaudio_wheel_url=https://files.pythonhosted.org/packages/16/a6/a08934f0dd9dc11e812895cbdf151eb4091185aade05b65d0c8e48dfd238/pysysaudio-0.1.3-cp312-cp312-macosx_14_0_universal2.whl
pysysaudio_wheel_sha256=471466ea7eb0309746fc1b3f3106e6a403f5aab265fdd6608e2d21553a4664a5

resolved_python=$("$build_python" -c \
  'import pathlib, sys; print(pathlib.Path(sys.executable).resolve())')
if ! file "$resolved_python" | grep -q 'Mach-O'; then
  echo "Build interpreter is not a Mach-O executable: $resolved_python" >&2
  exit 1
fi
lipo "$resolved_python" -verify_arch x86_64 arm64

# The pinned wheel is built for one ABI, so a different interpreter must fail
# loudly here rather than leaving the thin wheel pip already chose in place.
abi_tag=$("$build_python" -c \
  'import sys; print("cp%d%d" % sys.version_info[:2])')
if [[ $abi_tag != cp312 ]]; then
  echo "Pinned pysysaudio wheel is cp312 but the build interpreter is $abi_tag" >&2
  exit 1
fi

# pysysaudio publishes arm64, x86_64 and universal2 wheels for the same tag.
# pip prefers the single-architecture build that matches the runner, which
# PyInstaller then refuses because the app is universal2. Install the published
# universal2 wheel explicitly instead. Building from the sdist is not an
# alternative: its own setup.py passes -mmacosx-version-min=14.2 because the
# ScreenCaptureKit system-audio API it wraps is annotated available(macOS 14.2).
rm -rf "$wheel_dir"
mkdir -p "$wheel_dir"
curl --fail --location --proto '=https' --tlsv1.2 \
  "$pysysaudio_wheel_url" --output "$pysysaudio_wheel"
echo "$pysysaudio_wheel_sha256  $pysysaudio_wheel" | shasum -a 256 -c -

"$build_python" -m pip install --force-reinstall --no-deps "$pysysaudio_wheel"
pysysaudio_extension=$("$build_python" -c \
  'import pysysaudio._pysysaudio_native as m, pathlib; print(pathlib.Path(m.__file__).resolve())')
file "$pysysaudio_extension"
lipo "$pysysaudio_extension" -verify_arch x86_64 arm64
"$build_python" -c \
  "import importlib.metadata as m; v = m.version('pysysaudio'); assert v == '$pysysaudio_version', v"
