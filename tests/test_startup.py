import tempfile
import unittest
from os import environ
from pathlib import Path
from unittest.mock import patch

from spade65.startup import render_startup, startup_filename


class StartupTests(unittest.TestCase):
    def test_platform_specific_filenames(self):
        self.assertEqual(startup_filename("linux"), "spade65-background.service")
        self.assertEqual(startup_filename("windows"), "spade65-background.cmd")
        self.assertEqual(startup_filename("macos"), "com.spade65.background.plist")

    def test_launchers_run_same_cross_platform_service(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "service & profile.json"
            python = Path(directory) / "python"
            linux = render_startup(config, platform="linux", python_executable=python)
            windows = render_startup(config, platform="windows", python_executable=python)
            macos = render_startup(config, platform="macos", python_executable=python)
        self.assertIn("-m spade65 service run", linux)
        self.assertIn("pythonw.exe", windows)
        self.assertIn("-m</string><string>spade65", macos)
        self.assertIn("&amp;", macos)

    def test_frozen_launcher_calls_bundled_executable_directly(self):
        executable = Path("/opt/Spade65/Spade65")
        config = Path("/tmp/service.json")
        linux = render_startup(
            config, platform="linux", python_executable=executable, frozen=True
        )
        windows = render_startup(
            config, platform="windows", python_executable=executable, frozen=True
        )
        macos = render_startup(
            config, platform="macos", python_executable=executable, frozen=True
        )
        for launcher in (linux, windows, macos):
            self.assertNotIn("-m spade65", launcher)
            self.assertIn("service", launcher)
        self.assertNotIn("pythonw.exe", windows)

    def test_frozen_appimage_launcher_uses_persistent_image_path(self):
        with patch.dict(environ, {"APPIMAGE": "/home/user/Spade65.AppImage"}):
            launcher = render_startup(
                Path("/tmp/service.json"), platform="linux", frozen=True
            )
        self.assertIn('/home/user/Spade65.AppImage" service run', launcher)

    def test_windows_cli_generates_hidden_gui_service_launcher(self):
        launcher = render_startup(
            Path("C:/Users/test/service.json"),
            platform="windows",
            python_executable=Path("C:/Spade65/Spade65CLI.exe"),
            frozen=True,
        )
        self.assertIn("Spade65.exe", launcher)
        self.assertNotIn("Spade65CLI.exe", launcher)


if __name__ == "__main__":
    unittest.main()
