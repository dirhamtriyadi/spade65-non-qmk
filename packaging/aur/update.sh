#!/usr/bin/env bash
# Point the AUR package at a published release.
#
# The checksums can only be taken after the release build has uploaded its
# artefacts, so this runs after tagging, not as part of the release commit.
#
#   packaging/aur/update.sh 0.8.9

set -euo pipefail

version=${1:-}
if [ -z "$version" ]; then
  echo "usage: ${0##*/} VERSION" >&2
  exit 2
fi

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo=https://github.com/dirhamtriyadi/spade65-non-qmk
raw=https://raw.githubusercontent.com/dirhamtriyadi/spade65-non-qmk/v$version

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

fetch() {
  # A missing artefact must stop the update rather than checksum an error page.
  if ! curl -fsSL --retry 3 -o "$2" "$1"; then
    echo "cannot download $1" >&2
    exit 1
  fi
  sha256sum "$2" | cut -d' ' -f1
}

echo "reading v$version artefacts" >&2
appimage=$(fetch "$repo/releases/download/v$version/Spade65-Linux-x86_64.AppImage" \
  "$work/appimage")
rules=$(fetch "$raw/udev/99-spade65.rules" "$work/rules")
license=$(fetch "$raw/LICENSE" "$work/license")

sed -i \
  -e "s/^pkgver=.*/pkgver=$version/" \
  -e "s/^pkgrel=.*/pkgrel=1/" \
  "$here/PKGBUILD"

# The sums are positional, so replace the whole array at once rather than
# matching each line and risking the order.
python3 - "$here/PKGBUILD" "$appimage" "$rules" "$license" <<'PY'
import re
import sys

path, appimage, rules, license_sum = sys.argv[1:5]
with open(path, encoding="utf-8") as handle:
    text = handle.read()
block = "sha256sums=('%s'\n            '%s'\n            '%s')" % (
    appimage,
    rules,
    license_sum,
)
text = re.sub(r"sha256sums=\([^)]*\)", block, text, count=1)
with open(path, "w", encoding="utf-8") as handle:
    handle.write(text)
PY

if command -v makepkg >/dev/null; then
  (cd "$here" && makepkg --printsrcinfo > .SRCINFO)
  echo "PKGBUILD and .SRCINFO updated to v$version" >&2
else
  echo "PKGBUILD updated to v$version; run makepkg --printsrcinfo > .SRCINFO" >&2
fi
