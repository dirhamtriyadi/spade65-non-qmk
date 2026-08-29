import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from spade65.cli import main


class CliTests(unittest.TestCase):
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
