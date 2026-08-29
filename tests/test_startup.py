import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
