import json
import tempfile
import unittest
from pathlib import Path

from spade65.desktop_preferences import (
    desktop_preferences_path,
    load_desktop_preferences,
    save_desktop_preferences,
)


class DesktopPreferenceTests(unittest.TestCase):
    def test_preferences_use_platform_application_config_directories(self) -> None:
        home = Path("/users/test")
        self.assertEqual(
            desktop_preferences_path(
                "linux", environ={"XDG_CONFIG_HOME": "/config"}, home=home
            ),
            Path("/config/spade65/desktop-settings.json"),
        )
        self.assertEqual(
            desktop_preferences_path(
                "win32", environ={"APPDATA": "C:/Roaming"}, home=home
            ),
            Path("C:/Roaming/Spade65/desktop-settings.json"),
        )
        self.assertEqual(
            desktop_preferences_path("darwin", environ={}, home=home),
            home
            / "Library"
            / "Application Support"
            / "Spade65"
            / "desktop-settings.json",
        )

    def test_preferences_default_safely_and_persist_close_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "desktop.json"
            self.assertEqual(
                load_desktop_preferences(target), {"close_to_tray": True}
            )

            saved = save_desktop_preferences(
                {"close_to_tray": False}, path=target
            )
            self.assertEqual(saved, {"close_to_tray": False})
            self.assertEqual(
                json.loads(target.read_text(encoding="utf-8")), saved
            )
            self.assertEqual(load_desktop_preferences(target), saved)

            target.write_text("not json", encoding="utf-8")
            self.assertEqual(
                load_desktop_preferences(target), {"close_to_tray": True}
            )

    def test_preferences_reject_non_boolean_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "boolean"):
                save_desktop_preferences(
                    {"close_to_tray": "yes"},
                    path=Path(directory) / "desktop.json",
                )


if __name__ == "__main__":
    unittest.main()
