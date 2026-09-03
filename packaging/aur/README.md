# AUR package

Files for the `spade65-appimage` package on the Arch User Repository. They live
here so the packaging is reviewed with the rest of the project; the AUR itself
is a separate git repository that carries only `PKGBUILD`, `.SRCINFO` and
`spade65-appimage.install`.

## What it installs

| Path | Purpose |
|---|---|
| `/opt/spade65/spade65.AppImage` | the published release, unmodified |
| `/usr/bin/spade65` | symlink, so the command works from a terminal |
| `/usr/share/applications/spade65.desktop` | the launcher entry |
| `/usr/share/icons/hicolor/scalable/apps/spade65.svg` | the launcher icon |
| `/usr/lib/udev/rules.d/99-spade65.rules` | `hidraw` access without root |

The launcher entry and the icon are taken out of the AppImage during the build
rather than kept here as a second copy, so what appears in the application menu
is always the metadata the release was built with. Only `Exec` is rewritten,
because inside the image it is resolved by the AppImage runtime.

The udev rule is not carried in the AppImage, so it is fetched from the tagged
source tree.

## After a release

Checksums can only be taken once the release build has uploaded its artefacts,
so the AUR package trails the project by design and is updated after tagging:

```bash
packaging/aur/update.sh 0.8.9
python -m unittest tests.test_aur
```

That rewrites `pkgver`, resets `pkgrel`, re-reads all three checksums and
regenerates `.SRCINFO`. Then copy the three files into the AUR clone and push:

```bash
git clone ssh://aur@aur.archlinux.org/spade65-appimage.git
cp packaging/aur/{PKGBUILD,.SRCINFO,spade65-appimage.install} spade65-appimage/
cd spade65-appimage && git commit -am "Update to 0.8.9" && git push
```

Publishing needs an AUR account with an SSH key registered, and the account
must be the package maintainer.

## Testing it before publishing

```bash
cd packaging/aur && makepkg -f
tar --zstd -tf spade65-appimage-*-x86_64.pkg.tar.zst
sudo pacman -U spade65-appimage-*-x86_64.pkg.tar.zst
```

`tests/test_aur.py` guards the parts that rot silently: a `.SRCINFO` left stale
after a `PKGBUILD` edit, a source URL slipped off its tag, a placeholder
checksum, and a launcher entry that no longer validates or names an icon that
is not installed.
