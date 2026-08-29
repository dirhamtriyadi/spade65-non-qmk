#!/usr/bin/env bash
set -euo pipefail

if [[ $(uname -s) != Darwin ]]; then
  echo "macOS CI preparation must run on macOS" >&2
  exit 1
fi

mode=${1:?usage: prepare_macos_ci.sh download|install|verify|venv}
runner_temp=${RUNNER_TEMP:?RUNNER_TEMP is required}
installer_pkg="$runner_temp/python-3.13.15-macos11.pkg"
installer_url=https://www.python.org/ftp/python/3.13.15/python-3.13.15-macos11.pkg
installer_sha256=3b7eaf7f29825f796e8267024435540ddf1f17fc9a97ad58095daa7a75bfdcd3
framework_python=/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13
framework_library=/Library/Frameworks/Python.framework/Versions/3.13/Python
venv_dir="$runner_temp/spade65-build-venv"

verify_installer() {
  test -s "$installer_pkg"
  echo "$installer_sha256  $installer_pkg" | shasum -a 256 -c -
}

case $mode in
  download)
    curl --fail --location --proto '=https' --tlsv1.2 \
      "$installer_url" --output "$installer_pkg"
    verify_installer
    ;;
  install)
    verify_installer
    sudo /usr/sbin/installer -pkg "$installer_pkg" -target /
    ;;
  verify)
    test -x "$framework_python"
    test -f "$framework_library"
    file "$framework_python" "$framework_library"
    lipo -verify_arch x86_64 arm64 "$framework_python"
    lipo -verify_arch x86_64 arm64 "$framework_library"
    ;;
  venv)
    : "${GITHUB_PATH:?GITHUB_PATH is required}"
    : "${GITHUB_ENV:?GITHUB_ENV is required}"
    rm -rf "$venv_dir"
    "$framework_python" -m venv "$venv_dir"
    venv_bin="$venv_dir/bin"
    venv_python="$venv_bin/python"
    resolved_python=$("$venv_python" -c \
      'import pathlib, sys; print(pathlib.Path(sys.executable).resolve())')
    file "$resolved_python"
    lipo -verify_arch x86_64 arm64 "$resolved_python"
    echo "$venv_bin" >> "$GITHUB_PATH"
    echo "SPADE65_BUILD_PYTHON=$venv_python" >> "$GITHUB_ENV"
    ;;
  *)
    echo "unknown macOS CI preparation mode: $mode" >&2
    exit 2
    ;;
esac
