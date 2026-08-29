#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
build_python=${SPADE65_BUILD_PYTHON:-python}
artifact_dir="$repo_root/artifacts"
staging_dir="$repo_root/build/dmg-root"
application="$repo_root/dist/Spade65.app"
output="$artifact_dir/Spade65-macOS-universal.dmg"

rm -rf "$repo_root/build/Spade65" "$repo_root/dist/Spade65" \
  "$application" "$staging_dir"
mkdir -p "$artifact_dir" "$staging_dir"

source_version=$("$build_python" \
  "$repo_root/packaging/check_version.py" --print-version)
configured_version=${SPADE65_VERSION:-}
if [[ -n $configured_version && $configured_version != "$source_version" ]]; then
  echo "SPADE65_VERSION=$configured_version does not match source $source_version" >&2
  exit 1
fi
export SPADE65_VERSION=${configured_version:-$source_version}

SPADE65_TARGET_ARCH=universal2 "$build_python" -m PyInstaller \
  --noconfirm --clean "$repo_root/packaging/spade65.spec"

test -x "$application/Contents/MacOS/Spade65"

mach_o_count=0
while IFS= read -r -d '' candidate; do
  if file "$candidate" | grep -q 'Mach-O'; then
    lipo "$candidate" -verify_arch x86_64 arm64
    mach_o_count=$((mach_o_count + 1))
  fi
done < <(find "$application" -type f -print0)
if [[ $mach_o_count -eq 0 ]]; then
  echo "No Mach-O files found in application bundle" >&2
  exit 1
fi

"$application/Contents/MacOS/Spade65" --smoke-test

# Ad-hoc signing makes the bundle structurally valid on Apple Silicon. A public
# release still needs Developer ID signing and Apple notarization to avoid a
# Gatekeeper warning; those credentials intentionally do not live in this repo.
codesign --force --deep --sign - "$application"
codesign --verify --deep --strict "$application"

cp -R "$application" "$staging_dir/Spade65.app"
ln -s /Applications "$staging_dir/Applications"
rm -f "$output"
hdiutil create -quiet -volname "Spade65" -srcfolder "$staging_dir" \
  -format UDZO -ov "$output"
test -s "$output"
hdiutil verify -quiet "$output"

mount_dir=$(mktemp -d "${TMPDIR:-/tmp}/spade65-dmg.XXXXXX")
cleanup_mount() {
  hdiutil detach -quiet "$mount_dir" >/dev/null 2>&1 || true
  rmdir "$mount_dir" >/dev/null 2>&1 || true
}
trap cleanup_mount EXIT
hdiutil attach -quiet -readonly -nobrowse -mountpoint "$mount_dir" "$output"
test -x "$mount_dir/Spade65.app/Contents/MacOS/Spade65"
"$mount_dir/Spade65.app/Contents/MacOS/Spade65" --smoke-test
cleanup_mount
trap - EXIT
