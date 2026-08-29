#!/usr/bin/env bash
set -euo pipefail

if [[ $(uname -s) != Darwin ]]; then
  echo "Universal2 hidapi preparation must run on macOS" >&2
  exit 1
fi

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
build_python=${SPADE65_BUILD_PYTHON:-python}
wheel_dir="$repo_root/build/macos-hidapi-wheel"
hidapi_sdist="$wheel_dir/hidapi-0.15.0.tar.gz"
hidapi_sdist_url=https://files.pythonhosted.org/packages/74/f6/caad9ed701fbb9223eb9e0b41a5514390769b4cb3084a2704ab69e9df0fe/hidapi-0.15.0.tar.gz
hidapi_sdist_sha256=ecbc265cbe8b7b88755f421e0ba25f084091ec550c2b90ff9e8ddd4fcd540311

resolved_python=$("$build_python" -c \
  'import pathlib, sys; print(pathlib.Path(sys.executable).resolve())')
if ! file "$resolved_python" | grep -q 'Mach-O'; then
  echo "Build interpreter is not a Mach-O executable: $resolved_python" >&2
  exit 1
fi
file "$resolved_python"
lipo "$resolved_python" -verify_arch x86_64 arm64

# cython-hidapi publishes separate thin macOS wheels. Build its sdist with a
# universal2 interpreter instead; do not let pip silently fall back to a wheel
# or download unpinned build-isolation tooling.
export ARCHFLAGS="-arch x86_64 -arch arm64"
export MACOSX_DEPLOYMENT_TARGET=11.0
rm -rf "$wheel_dir"
mkdir -p "$wheel_dir"
curl --fail --location --proto '=https' --tlsv1.2 \
  "$hidapi_sdist_url" --output "$hidapi_sdist"
echo "$hidapi_sdist_sha256  $hidapi_sdist" | shasum -a 256 -c -
"$build_python" -m pip wheel \
  --no-cache-dir \
  --no-deps \
  --no-binary=:all: \
  --no-build-isolation \
  --wheel-dir "$wheel_dir" \
  "$hidapi_sdist"

hid_wheels=("$wheel_dir"/hidapi-0.15.0-*.whl)
if [[ ${#hid_wheels[@]} -ne 1 || ! -f ${hid_wheels[0]} ]]; then
  echo "Expected exactly one locally built hidapi wheel" >&2
  exit 1
fi
case ${hid_wheels[0]} in
  *-macosx_11_0_universal2.whl) ;;
  *)
    echo "hidapi wheel is not tagged macosx_11_0_universal2: ${hid_wheels[0]}" >&2
    exit 1
    ;;
esac

"$build_python" -m pip install --force-reinstall --no-deps "${hid_wheels[0]}"
hid_extension=$("$build_python" -c \
  'import hid, pathlib; print(pathlib.Path(hid.__file__).resolve())')
file "$hid_extension"
lipo "$hid_extension" -verify_arch x86_64 arm64
"$build_python" -c \
  'import hid; assert hid.__version__ == "0.15.0", hid.__version__'
