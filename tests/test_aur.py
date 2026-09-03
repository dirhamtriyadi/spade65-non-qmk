import re
import shutil
import subprocess
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUR = ROOT / "packaging" / "aur"
PKGBUILD = AUR / "PKGBUILD"


def _field(name: str) -> str:
    match = re.search(rf"^{name}=(.+)$", PKGBUILD.read_text(encoding="utf-8"), re.M)
    assert match is not None, f"{name} is missing from the PKGBUILD"
    return match.group(1).strip().strip("'\"")


class AurPackageTests(unittest.TestCase):
    def test_srcinfo_matches_the_pkgbuild(self) -> None:
        # An AUR package whose .SRCINFO is stale installs the previous release
        # for everyone, because that is the file the AUR actually reads.
        if shutil.which("makepkg") is None:
            self.skipTest("makepkg is required to regenerate .SRCINFO")
        result = subprocess.run(
            ["makepkg", "--printsrcinfo"],
            cwd=AUR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            (AUR / ".SRCINFO").read_text(encoding="utf-8"),
            "run packaging/aur/update.sh, or makepkg --printsrcinfo > .SRCINFO",
        )

    def test_it_points_at_a_release_that_exists(self) -> None:
        # The AUR package trails the project: its checksums can only be taken
        # after a release build has published its artefacts. Ahead of the
        # project version it would name a tag nobody can download.
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        packaged = tuple(int(part) for part in _field("pkgver").split("."))
        current = tuple(int(part) for part in project["version"].split("."))
        self.assertLessEqual(packaged, current)

    def test_every_source_is_pinned_to_the_packaged_version(self) -> None:
        # .SRCINFO carries the expanded URLs and is the file the AUR reads, so
        # a source left on a branch would install something nobody reviewed
        # even if the PKGBUILD looked pinned.
        srcinfo = (AUR / ".SRCINFO").read_text(encoding="utf-8")
        version = _field("pkgver")
        urls = re.findall(r"source = \S+?::(\S+)", srcinfo)
        self.assertEqual(len(urls), 3)
        for url in urls:
            with self.subTest(url=url):
                self.assertIn(f"v{version}", url)
                self.assertNotIn("/main/", url)
                self.assertNotIn("/latest/", url)

    def test_the_sums_are_real(self) -> None:
        sums = re.search(r"sha256sums=\((.*?)\)", PKGBUILD.read_text(), re.S)
        assert sums is not None
        digests = re.findall(r"'([^']*)'", sums.group(1))
        self.assertEqual(len(digests), 3)
        for digest in digests:
            with self.subTest(digest=digest):
                self.assertRegex(digest, r"^[0-9a-f]{64}$")
                self.assertNotEqual(digest, "0" * 64)

    def test_the_launcher_entry_is_valid(self) -> None:
        # The entry the AUR package installs is taken out of the AppImage, so
        # this is the file that decides whether Spade65 appears in the menu.
        if shutil.which("desktop-file-validate") is None:
            self.skipTest("desktop-file-validate is required")
        entry = ROOT / "packaging" / "linux" / "spade65.desktop"
        result = subprocess.run(
            ["desktop-file-validate", str(entry)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_icon_name_matches_the_installed_icon(self) -> None:
        # A launcher entry naming an icon that is not installed shows a blank
        # tile in the menu, which looks like a broken install.
        entry = (ROOT / "packaging" / "linux" / "spade65.desktop").read_text()
        icon = re.search(r"^Icon=(.+)$", entry, re.M)
        assert icon is not None
        self.assertEqual(icon.group(1).strip(), "spade65")
        self.assertTrue((ROOT / "packaging" / "linux" / "spade65.svg").is_file())
        packaged = PKGBUILD.read_text(encoding="utf-8")
        self.assertIn("icons/hicolor/scalable/apps/$_appname.svg", packaged)


if __name__ == "__main__":
    unittest.main()
