import tempfile
import unittest
from os import environ
from pathlib import Path
from unittest.mock import patch

from spade65.startup import (
    default_service_paths,
    release_service_setup,
    render_startup,
    startup_filename,
)


class StartupTests(unittest.TestCase):
    def test_default_service_paths_are_user_owned(self):
        linux = default_service_paths(
            "linux", environ={"XDG_CONFIG_HOME": "/config"}, home=Path("/home/test")
        )
        windows = default_service_paths(
            "windows",
            environ={"APPDATA": "C:/Users/test/Roaming"},
            home=Path("C:/Users/test"),
        )
        macos = default_service_paths("macos", environ={}, home=Path("/Users/test"))

        self.assertEqual(linux[0], Path("/config/spade65/background.json"))
        self.assertEqual(linux[1].name, "spade65-background.service")
        self.assertEqual(windows[1].name, "spade65-background.cmd")
        self.assertEqual(
            macos[1],
            Path("/Users/test/Library/LaunchAgents/com.spade65.background.plist"),
        )

    def test_release_linux_setup_uses_current_appimage(self):
        setup = release_service_setup(
            "linux",
            environ={
                "APPIMAGE": "/home/test/Applications/Spade65.AppImage",
                "XDG_CONFIG_HOME": "/home/test/.config",
            },
            home=Path("/home/test"),
            frozen=True,
        )

        self.assertTrue(setup["packaged"])
        self.assertIn(
            "Spade65.AppImage service example", setup["prepare_commands"]
        )
        self.assertIn("systemctl --user enable --now", setup["activate_commands"])
        self.assertNotIn("spade65ctl", setup["prepare_commands"])
        self.assertNotIn("spade65ctl", setup["activate_commands"])

    def test_release_windows_setup_uses_console_executable(self):
        setup = release_service_setup(
            "windows",
            environ={"APPDATA": "C:/Users/test/AppData/Roaming"},
            home=Path("C:/Users/test"),
            executable=Path("C:/Spade65/Spade65.exe"),
            frozen=True,
        )

        self.assertIn("Spade65CLI.exe", setup["prepare_commands"])
        self.assertIn("Spade65CLI.exe", setup["activate_commands"])
        self.assertIn(
            "Windows/Start Menu/Programs/Startup",
            setup["launcher_path"].replace("\\", "/"),
        )
        self.assertNotIn("spade65ctl", setup["prepare_commands"])
        self.assertNotIn("spade65ctl", setup["activate_commands"])

    def test_release_macos_setup_uses_launch_agent(self):
        setup = release_service_setup(
            "macos",
            environ={},
            home=Path("/Users/test"),
            executable=Path("/Applications/Spade65.app/Contents/MacOS/Spade65"),
            frozen=True,
        )

        self.assertIn("launchctl bootstrap", setup["activate_commands"])
        self.assertIn(
            "Spade65.app/Contents/MacOS/Spade65", setup["prepare_commands"]
        )

    def test_source_setup_keeps_commands_out_of_gui_metadata(self):
        setup = release_service_setup(
            "linux", environ={}, home=Path("/home/test"), frozen=False
        )

        self.assertFalse(setup["packaged"])
        self.assertEqual(setup["prepare_commands"], "")
        self.assertEqual(setup["activate_commands"], "")

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
        self.assertIn(
            '/home/user/Spade65.AppImage" service run', launcher.replace("\\", "/")
        )

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
