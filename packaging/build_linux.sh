#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
build_python=${SPADE65_BUILD_PYTHON:-python}
artifact_dir="$repo_root/artifacts"
app_dir="$repo_root/build/Spade65.AppDir"
appimagetool="$repo_root/build/appimagetool-x86_64.AppImage"
runtime_file="$repo_root/build/runtime-x86_64"
output="$artifact_dir/Spade65-Linux-x86_64.AppImage"
legal_inventory_dir="$app_dir/usr/share/doc/spade65/linux-system-libraries"

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

# Host graphics dispatchers, C/C++ runtimes, ALSA, and the font stack must
# remain compatible with the user's GPU/audio drivers and /etc/fonts
# configuration. Ubuntu copies inside the AppImage can shadow newer rolling-
# distribution libraries and break Wayland, XWayland, audio, or font loading.
for host_library_pattern in \
  'libstdc++.so*' \
  'libgcc_s.so*' \
  'libgbm.so*' \
  'libfontconfig.so*' \
  'libfreetype.so*' \
  'libexpat.so*' \
  'libX11.so*' \
  'libX11-xcb.so*' \
  'libasound.so*' \
  'libEGL.so*' \
  'libGL.so*' \
  'libGLX.so*' \
  'libGLdispatch.so*' \
  'libOpenGL.so*' \
  'libGLES*.so*' \
  'libdrm.so*' \
  'libdrm_amdgpu.so*' \
  'libdrm_intel.so*' \
  'libdrm_nouveau.so*' \
  'libvulkan.so*' \
  'libva.so*' \
  'libva-drm.so*' \
  'libva-x11.so*' \
  'libxcb.so*' \
  'libxcb-dri2.so*' \
  'libxcb-dri3.so*' \
  'libwayland-client.so*' \
  'libwayland-cursor.so*' \
  'libwayland-egl.so*' \
  'libglapi.so*' \
  'libharfbuzz.so*'; do
  bundled_host_library=$(find "$repo_root/dist/Spade65" \
    -name "$host_library_pattern" -print -quit)
  if [[ -n $bundled_host_library ]]; then
    echo "Host-bound Linux runtime entered the bundle: $bundled_host_library" >&2
    exit 1
  fi
done

# The host graphics dispatcher (EGL/GL) must match the user's driver stack,
# but these generic XCB support libraries are safe and necessary to bundle.
# Fail before AppImage creation if the build host could not supply any of them.
for required_library in \
  'libxcb-shape.so.0' \
  'libxcb-image.so.0' \
  'libxcb-xkb.so.1' \
  'libxcb-icccm.so.4' \
  'libxkbcommon-x11.so.0' \
  'libxcb-util.so.1' \
  'libxcb-cursor.so.0' \
  'libxcb-keysyms.so.1' \
  'libxcb-render-util.so.0'; do
  if ! find "$repo_root/dist/Spade65" -type f \
    -name "$required_library" -print -quit | grep -q .; then
    echo "Required Qt/XCB runtime was not bundled: $required_library" >&2
    exit 1
  fi
done

# QtWebEngineWidgets needs the LGPL QtQuick runtime libraries, but not these
# optional GPL-only modules. Keep this artifact check next to the real build so
# a PyInstaller/PySide hook change cannot silently broaden the license scope.
for forbidden_pattern in \
  '*Qt6Graphs*' \
  '*Qt6DataVisualization*' \
  '*Qt6Quick3D*' \
  '*qtquick3d*' \
  '*Qt6QuickTimeline*' \
  '*Qt6VirtualKeyboard*' \
  '*qtvirtualkeyboard*' \
  '*Qt6WaylandCompositor*'; do
  forbidden_file=$(find "$repo_root/dist/Spade65" -type f \
    -iname "$forbidden_pattern" -print -quit)
  if [[ -n $forbidden_file ]]; then
    echo "Forbidden GPL-only Qt module entered the Linux bundle: $forbidden_file" >&2
    exit 1
  fi
done

# Linux uses the descriptor-gated hidraw backend. The optional HIDAPI wheel is
# for Windows/macOS and would add an unused extension plus vendored native
# libraries to the AppImage.
unexpected_hidapi=$(find "$repo_root/dist/Spade65" -type f \
  \( -path '*/hidapi.libs/*' -o -name 'hid.*.so' \) -print -quit)
if [[ -n $unexpected_hidapi ]]; then
  echo "Unexpected HIDAPI payload entered the Linux bundle: $unexpected_hidapi" >&2
  exit 1
fi

cp -a "$repo_root/dist/Spade65" "$app_dir/usr/lib/spade65"
install -m 0755 "$repo_root/packaging/linux/AppRun" "$app_dir/AppRun"
install -m 0644 "$repo_root/packaging/linux/spade65.desktop" \
  "$app_dir/spade65.desktop"
install -m 0644 "$repo_root/packaging/linux/spade65.svg" "$app_dir/spade65.svg"

mkdir -p "$app_dir/usr/share/applications" \
  "$app_dir/usr/share/icons/hicolor/scalable/apps" \
  "$app_dir/usr/share/doc/spade65"
cp "$app_dir/spade65.desktop" "$app_dir/usr/share/applications/spade65.desktop"
cp "$app_dir/spade65.svg" \
  "$app_dir/usr/share/icons/hicolor/scalable/apps/spade65.svg"
install -m 0644 "$repo_root/LICENSE" \
  "$app_dir/usr/share/doc/spade65/LICENSE"
install -m 0644 "$repo_root/THIRD-PARTY-NOTICES.md" \
  "$app_dir/usr/share/doc/spade65/THIRD-PARTY-NOTICES.md"
cp -a "$repo_root/licenses" "$app_dir/usr/share/doc/spade65/licenses"
test -s "$app_dir/usr/share/doc/spade65/THIRD-PARTY-NOTICES.md"
test -s "$app_dir/usr/share/doc/spade65/licenses/GPL-3.0.txt"
test -s "$app_dir/usr/share/doc/spade65/licenses/LGPL-3.0.txt"
test -s "$app_dir/usr/share/doc/spade65/licenses/LGPL-2.1.txt"
test -s "$app_dir/usr/share/doc/spade65/licenses/Qt-6.11.2-LICENSE.Chromium"
test -s "$app_dir/usr/share/doc/spade65/licenses/QtWebEngine-6.11.2-THIRD-PARTY-NOTICES.html"
test -s "$app_dir/usr/share/doc/spade65/licenses/GFDL-1.3-no-invariants-only.txt"
test -s "$app_dir/usr/share/doc/spade65/licenses/PERMISSIVE-LICENSES.txt"
test -s "$app_dir/usr/share/doc/spade65/licenses/PYTHON-3.13.txt"
test -s "$app_dir/usr/share/doc/spade65/licenses/PYINSTALLER.txt"
test -s \
  "$app_dir/usr/share/doc/spade65/licenses/AppImage-type2-runtime-75849dc-LICENSE"
test -s \
  "$app_dir/usr/share/doc/spade65/licenses/AppImage-appimagetool-1.9.1-LICENSE"

legal_inventory_args=(
  --toc "$repo_root/build/spade65/COLLECT-00.toc"
  --output-dir "$legal_inventory_dir"
)
case ${SPADE65_STRICT_LINUX_LEGAL:-0} in
  0) ;;
  1) legal_inventory_args+=(--strict-dpkg) ;;
  *)
    echo "SPADE65_STRICT_LINUX_LEGAL must be 0 or 1" >&2
    exit 2
    ;;
esac
"$build_python" "$repo_root/packaging/linux_legal_inventory.py" \
  "${legal_inventory_args[@]}"
test -s "$legal_inventory_dir/LINUX-SYSTEM-LIBRARIES.json"
test -s "$legal_inventory_dir/README.txt"
ln -s ../lib/spade65/Spade65 "$app_dir/usr/bin/Spade65"

tool_url=${APPIMAGETOOL_URL:-https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage}
tool_sha256=${APPIMAGETOOL_SHA256:-ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0}
curl --fail --location --retry 3 --output "$appimagetool" "$tool_url"
verify_sha256 "$appimagetool" "$tool_sha256" "appimagetool"
chmod 0755 "$appimagetool"

runtime_url=${APPIMAGE_RUNTIME_URL:-https://api.github.com/repos/AppImage/type2-runtime/releases/assets/456065460}
# Asset 456065460 was built from AppImage/type2-runtime commit 75849dc.
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
