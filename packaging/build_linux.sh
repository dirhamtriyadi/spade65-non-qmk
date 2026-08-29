#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
build_python=${SPADE65_BUILD_PYTHON:-python}
artifact_dir="$repo_root/artifacts"
app_dir="$repo_root/build/Spade65.AppDir"
appimagetool="$repo_root/build/appimagetool-x86_64.AppImage"
runtime_file="$repo_root/build/runtime-x86_64"
output="$artifact_dir/Spade65-Linux-x86_64.AppImage"

verify_sha256() {
  local target=$1
  local expected=$2
  local label=$3
  local actual
  actual=$(sha256sum "$target")
  actual=${actual%% *}
  if [[ $actual != "$expected" ]]; then
    echo "$label checksum mismatch: $actual" >&2
    exit 1
  fi
}

rm -rf "$repo_root/build/Spade65" "$repo_root/dist/Spade65" "$app_dir"
mkdir -p "$artifact_dir" "$app_dir/usr/lib" "$app_dir/usr/bin"

source_version=$("$build_python" \
  "$repo_root/packaging/check_version.py" --print-version)
"$build_python" -m PyInstaller --noconfirm --clean \
  "$repo_root/packaging/spade65.spec"
cp -a "$repo_root/dist/Spade65" "$app_dir/usr/lib/spade65"
install -m 0755 "$repo_root/packaging/linux/AppRun" "$app_dir/AppRun"
install -m 0644 "$repo_root/packaging/linux/spade65.desktop" \
  "$app_dir/spade65.desktop"
install -m 0644 "$repo_root/packaging/linux/spade65.svg" "$app_dir/spade65.svg"

mkdir -p "$app_dir/usr/share/applications" \
  "$app_dir/usr/share/icons/hicolor/scalable/apps"
cp "$app_dir/spade65.desktop" "$app_dir/usr/share/applications/spade65.desktop"
cp "$app_dir/spade65.svg" \
  "$app_dir/usr/share/icons/hicolor/scalable/apps/spade65.svg"
ln -s ../lib/spade65/Spade65 "$app_dir/usr/bin/Spade65"

tool_url=${APPIMAGETOOL_URL:-https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage}
tool_sha256=${APPIMAGETOOL_SHA256:-ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0}
curl --fail --location --retry 3 --output "$appimagetool" "$tool_url"
verify_sha256 "$appimagetool" "$tool_sha256" "appimagetool"
chmod 0755 "$appimagetool"

runtime_url=${APPIMAGE_RUNTIME_URL:-https://api.github.com/repos/AppImage/type2-runtime/releases/assets/456065460}
runtime_sha256=${APPIMAGE_RUNTIME_SHA256:-1cc49bcf1e2ccd593c379adb17c9f85a36d619088296504de95b1d06215aebbf}
curl --fail --location --retry 3 --header "Accept: application/octet-stream" \
  --output "$runtime_file" "$runtime_url"
verify_sha256 "$runtime_file" "$runtime_sha256" "AppImage runtime"

rm -f "$output"
ARCH=x86_64 VERSION="$source_version" APPIMAGE_EXTRACT_AND_RUN=1 "$appimagetool" \
  --runtime-file "$runtime_file" "$app_dir" "$output"
test -s "$output"
chmod 0755 "$output"
APPIMAGE_EXTRACT_AND_RUN=1 "$output" --smoke-test
