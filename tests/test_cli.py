import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from spade65.cli import main
from spade65.desktop import DesktopUnavailable


class CliTests(unittest.TestCase):
    def test_cli_error_path_tolerates_a_windowed_process_without_stderr(self) -> None:
        with patch("spade65.cli.sys.stderr", None):
            self.assertEqual(main(["profile", "validate", "/missing-profile"]), 1)

    def test_gui_prefers_desktop_and_keeps_browser_fallback(self) -> None:
        with (
            patch("spade65.desktop.run_desktop") as run_desktop,
            patch("spade65.gui.run_gui") as run_gui,
        ):
            self.assertEqual(main(["gui", "--port", "0"]), 0)
        run_desktop.assert_called_once_with(host="127.0.0.1", port=0)
        run_gui.assert_not_called()

        with (
            patch(
                "spade65.desktop.run_desktop",
                side_effect=DesktopUnavailable("missing"),
            ),
            patch("spade65.gui.run_gui") as run_gui,
            patch("spade65.cli.sys.stderr", None),
        ):
            self.assertEqual(main(["gui", "--port", "0"]), 0)
        run_gui.assert_called_once_with(
            host="127.0.0.1", port=0, open_browser=True
        )

    def test_gui_can_force_browser_or_server_only_mode(self) -> None:
        with (
            patch("spade65.desktop.run_desktop") as run_desktop,
            patch("spade65.gui.run_gui") as run_gui,
        ):
            self.assertEqual(main(["gui", "--browser", "--port", "0"]), 0)
            self.assertEqual(main(["gui", "--no-browser", "--port", "0"]), 0)
        run_desktop.assert_not_called()
        self.assertEqual(run_gui.call_args_list[0].kwargs["open_browser"], True)
        self.assertEqual(run_gui.call_args_list[1].kwargs["open_browser"], False)

    def test_profile_create_validate_and_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profile.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["profile", "create", str(profile)]), 0)
                self.assertEqual(main(["profile", "validate", str(profile)]), 0)
                self.assertEqual(
                    main(["profile", "apply", str(profile), "--dry-run"]), 0
                )
            data = json.loads(profile.read_text())
            self.assertEqual(data["format"], "spade65-profile-v1")

    def test_profile_write_requires_double_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profile.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["profile", "create", str(profile)]), 0)
            error = io.StringIO()
            with redirect_stderr(error):
                self.assertEqual(
                    main(["profile", "apply", str(profile), "--confirm"]), 1
                )
            self.assertIn("--i-understand-profile-overwrite", error.getvalue())

    def test_stream_dry_run_builds_five_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profile.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["profile", "create", str(profile)]), 0)
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    main(["stream-rgb", str(profile), "--dry-run"]), 0
                )
            self.assertEqual(output.getvalue().count("report_id=0x06"), 5)

    def test_vendor_import_converts_apmode_export(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "APMode.json"
            output = root / "profile.json"
            source.write_text(json.dumps({
                "filename": "APMode",
                "value": {"Light_Export": [{
                    "name": "Static", "check": True,
                    "colors": ["#123456"],
                    "frame_selection_range": [True],
                }]},
            }))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(["vendor-import", str(source), str(output)]), 0
                )
            profile = json.loads(output.read_text())
            self.assertEqual(profile["settings"]["app_effects"][0]["mode"], "static")


if __name__ == "__main__":
    unittest.main()
