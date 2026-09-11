import importlib.util
import re
import shutil
import subprocess
import unittest
import xml.etree.ElementTree as ElementTree
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "io.github.dirhamtriyadi.Spade65"
METAINFO = ROOT / "packaging" / "flatpak" / f"{APP_ID}.metainfo.xml"


def _load(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# tomllib arrived in 3.11 and this project supports 3.10.
versions = _load("spade65_appstream_versions", "packaging/check_version.py")


def _tree() -> ElementTree.Element:
    return ElementTree.parse(METAINFO).getroot()


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


class AppStreamTests(unittest.TestCase):
    def test_it_validates(self) -> None:
        # Flathub rejects a submission whose metainfo does not validate, and
        # the failure arrives after the pull request rather than before it.
        if shutil.which("appstreamcli") is None:
            self.skipTest("appstreamcli is required to validate metainfo")
        result = subprocess.run(
            ["appstreamcli", "validate", "--no-net", str(METAINFO)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_id_is_the_one_the_flatpak_is_named_after(self) -> None:
        # Flathub keys the repository, the desktop file and the icon to this
        # exact string; a mismatch anywhere means the app will not launch.
        root = _tree()
        self.assertEqual(root.findtext("id"), APP_ID)
        launchable = root.find("launchable[@type='desktop-id']")
        self.assertIsNotNone(launchable)
        self.assertEqual(launchable.text, f"{APP_ID}.desktop")
        self.assertEqual(METAINFO.name, f"{APP_ID}.metainfo.xml")

    def test_the_licence_matches_the_project(self) -> None:
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        declared = re.search(r'^license\s*=\s*"([^"]+)"', project, re.M)
        self.assertIsNotNone(declared)
        self.assertEqual(_tree().findtext("project_license"), declared.group(1))

    def test_screenshots_are_pinned_to_a_tag(self) -> None:
        # A screenshot URL on a branch changes under Flathub's feet, and the
        # store would show whatever the branch happens to hold that day.
        images = [image.text or "" for image in _tree().iter("image")]
        self.assertTrue(images)
        for url in images:
            with self.subTest(url=url):
                self.assertRegex(url, r"/v\d+\.\d+\.\d+/")
                self.assertNotIn("/main/", url)
                self.assertNotIn("/refs/heads/", url)

    def test_every_screenshot_file_exists_in_this_repository(self) -> None:
        # The URLs point at this repository, so a missing file here is a
        # broken image in the store.
        for url in (image.text or "" for image in _tree().iter("image")):
            with self.subTest(url=url):
                relative = url.split("/docs/", 1)[1]
                self.assertTrue((ROOT / "docs" / relative).is_file())

    def test_it_carries_what_flathub_requires_beyond_validation(self) -> None:
        # appstreamcli accepts metainfo without these, but Flathub refuses it.
        # Finding that out from a rejected pull request wastes a review round.
        root = _tree()
        required = {
            "content_rating": root.find("content_rating"),
            "developer": root.find("developer"),
            "summary": root.find("summary"),
            "name": root.find("name"),
            "homepage url": root.find("url[@type='homepage']"),
            "bugtracker url": root.find("url[@type='bugtracker']"),
            "screenshots": root.find("screenshots"),
            "releases": root.find("releases"),
        }
        missing = sorted(name for name, node in required.items() if node is None)
        self.assertEqual(missing, [])
        self.assertEqual(root.find("content_rating").get("type"), "oars-1.1")
        # Exactly one screenshot may be the default one shown in the store.
        defaults = [
            s for s in root.iter("screenshot") if s.get("type") == "default"
        ]
        self.assertEqual(len(defaults), 1)

    def test_the_newest_release_is_not_ahead_of_the_project(self) -> None:
        releases = [r.get("version", "") for r in _tree().iter("release")]
        self.assertTrue(releases)
        current = versions.project_version_from_text(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        self.assertLessEqual(_version(releases[0]), _version(current))

    def test_releases_are_listed_newest_first(self) -> None:
        # Software centres show the first entry as "what's new".
        releases = [_version(r.get("version", "")) for r in _tree().iter("release")]
        self.assertEqual(releases, sorted(releases, reverse=True))


if __name__ == "__main__":
    unittest.main()
