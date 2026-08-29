import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from spade65.keymap import profile_template
from spade65.service import (
    BackgroundService,
    load_service_config,
    matching_rule,
    service_template,
)


class ServiceTests(unittest.TestCase):
    def test_config_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "service.json"
            path.write_text(json.dumps(service_template()))
            self.assertEqual(load_service_config(path)["format"], "spade65-service-v1")

    def test_background_timeline_streams_without_profile_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = profile_template()
            profile["settings"]["custom_timeline"] = {
                "frames": [{"duration_ms": 100, "colors": {"esc": "#ff0000"}}]
            }
            (root / "profile.json").write_text(json.dumps(profile))
            config = service_template()
            config["background_profile"] = "profile.json"
            config["associations"] = []
            (root / "service.json").write_text(json.dumps(config))
            with patch("spade65.service.stream_colors") as stream:
                status = BackgroundService(root / "service.json", clock=lambda: 1).step()
            self.assertEqual(status, "timeline:profile.json")
            stream.assert_called_once_with({"esc": "#ff0000"}, path=None)

    @patch("spade65.service.active_process_name", return_value="firefox")
    def test_x11_foreground_process_selects_profile(self, active) -> None:
        config = service_template()
        config["associations"] = [
            {"process": "/usr/bin/firefox", "profile": "browser.json"},
            {"process": "code", "profile": "editor.json"},
        ]
        self.assertEqual(matching_rule(config)["profile"], "browser.json")

    @patch("spade65.service.running_process_names", return_value={"code"})
    @patch("spade65.service.active_process_name", return_value=None)
    def test_wayland_running_process_fallback_selects_profile(self, active, running) -> None:
        config = service_template()
        config["associations"] = [
            {"process": "firefox", "profile": "browser.json"},
            {"process": "/usr/bin/code", "profile": "editor.json"},
        ]
        self.assertEqual(matching_rule(config)["profile"], "editor.json")

    def test_profile_writes_need_runtime_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "profile.json").write_text(json.dumps(profile_template()))
            config = service_template()
            config.update({
                "background_profile": "profile.json", "associations": [],
                "allow_profile_writes": True,
            })
            (root / "service.json").write_text(json.dumps(config))
            with self.assertRaisesRegex(RuntimeError, "--allow-profile-writes"):
                BackgroundService(root / "service.json").step()


if __name__ == "__main__":
    unittest.main()
