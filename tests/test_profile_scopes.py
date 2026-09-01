"""Applying a profile must write only the parts the operator asked for.

The keyboard has no configuration readback, so a write that touches more than
the operator intended cannot be inspected or undone. Applying a keymap change
must therefore not repaint the lighting, and applying colours must not rewrite
the keymap.
"""

import io
import json
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from importlib.resources import files
from pathlib import Path
from unittest.mock import patch

from spade65.cli import main
from spade65.device import Device, ReportShape
from spade65.gui import execute_action
from spade65.protocol import (
    MAIN_REPORT_ID,
    MAIN_REPORT_LENGTH,
    MAIN_USAGE,
    VENDOR_ID,
)
from spade65.keymap import (
    PROFILE_SCOPES,
    compile_profile,
    profile_reports,
    profile_template,
)


def _opcodes(reports) -> list[int]:
    return [report[1] for report in reports]


def _profile(*, colors: bool = False, macro: bool = False, bound: bool = False):
    profile = profile_template()
    if macro or bound:
        profile["macros"] = [
            {
                "index": 0,
                "repeat": 1,
                "events": [{"delay_ms": 20, "usage": "a", "pressed": True}],
            }
        ]
    if bound:
        profile["layers"]["normal"]["esc"] = {"macro": 0}
    if colors:
        profile["colors"] = {"esc": "#ff0000"}
    return profile


class ProfileScopeTests(unittest.TestCase):
    def test_the_three_scopes_are_named(self) -> None:
        self.assertEqual(PROFILE_SCOPES, ("keymap", "macros", "colors"))

    def test_default_sends_everything_the_profile_defines(self) -> None:
        # Unchanged behaviour: no scope argument means the whole profile.
        profile = _profile(colors=True, macro=True)
        reports = profile_reports(profile, compile_profile(profile))
        self.assertEqual(_opcodes(reports), [0x03, 0x05, 0x02, 0x07])

    def test_keymap_scope_leaves_the_lighting_untouched(self) -> None:
        # The reported bug: changing a keymap repainted every key black.
        profile = _profile(colors=True)
        reports = profile_reports(
            profile, compile_profile(profile), scopes=["keymap"]
        )
        self.assertEqual(_opcodes(reports), [0x03])
        self.assertNotIn(0x02, _opcodes(reports))
        self.assertNotIn(0x07, _opcodes(reports))

    def test_colors_scope_leaves_the_keymap_untouched(self) -> None:
        profile = _profile(colors=True, macro=True)
        reports = profile_reports(
            profile, compile_profile(profile), scopes=["colors"]
        )
        self.assertEqual(_opcodes(reports), [0x02, 0x07])

    def test_macros_scope_sends_only_macro_reports(self) -> None:
        profile = _profile(macro=True)
        reports = profile_reports(
            profile, compile_profile(profile), scopes=["macros"]
        )
        self.assertEqual(_opcodes(reports), [0x05])

    def test_colors_scope_on_a_profile_without_colours_sends_nothing(self) -> None:
        profile = _profile()
        reports = profile_reports(
            profile, compile_profile(profile), scopes=["colors"]
        )
        self.assertEqual(reports, ())

    def test_a_keymap_bound_to_a_macro_refuses_to_go_without_it(self) -> None:
        # The device keeps its old macro table, so writing the keymap alone
        # would silently bind the key to whatever macro 0 currently holds.
        profile = _profile(bound=True)
        with self.assertRaisesRegex(ValueError, "macro"):
            profile_reports(
                profile, compile_profile(profile), scopes=["keymap"]
            )
        # Naming both scopes is accepted.
        reports = profile_reports(
            profile, compile_profile(profile), scopes=["keymap", "macros"]
        )
        self.assertEqual(_opcodes(reports), [0x03, 0x05])

    def test_a_keymap_without_macro_bindings_may_go_alone(self) -> None:
        profile = _profile(macro=True)
        reports = profile_reports(
            profile, compile_profile(profile), scopes=["keymap"]
        )
        self.assertEqual(_opcodes(reports), [0x03])

    def test_an_empty_or_unknown_scope_is_rejected(self) -> None:
        profile = _profile()
        compiled = compile_profile(profile)
        with self.assertRaisesRegex(ValueError, "at least one"):
            profile_reports(profile, compiled, scopes=[])
        with self.assertRaisesRegex(ValueError, "unknown profile scope"):
            profile_reports(profile, compiled, scopes=["lighting"])

    def test_scope_order_does_not_change_the_write_order(self) -> None:
        # Reports must always go keymap, macros, colours regardless of input.
        profile = _profile(colors=True, macro=True)
        reports = profile_reports(
            profile,
            compile_profile(profile),
            scopes=["colors", "macros", "keymap"],
        )
        self.assertEqual(_opcodes(reports), [0x03, 0x05, 0x02, 0x07])


def _main_device() -> Device:
    return Device(
        path=Path("/dev/hidraw-main"),
        vendor_id=VENDOR_ID,
        product_id=0x0351,
        usages={MAIN_USAGE},
        reports=[ReportShape("feature", MAIN_REPORT_ID, (MAIN_REPORT_LENGTH - 1) * 8)],
    )


class ScopedApplyTests(unittest.TestCase):
    """The CLI and the GUI must both honour the scope, not just the helper."""

    def _sent(self, calls) -> list[int]:
        return [call.args[1][1] for call in calls]

    def test_cli_only_keymap_does_not_touch_the_lighting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(_profile(colors=True)), encoding="utf-8")
            with (
                patch("spade65.cli.discover_devices", return_value=[_main_device()]),
                patch(
                    "spade65.cli.send_feature_report", side_effect=lambda d, r: len(r)
                ) as send,
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(
                    main(
                        [
                            "profile", "apply", str(path), "--only", "keymap",
                            "--confirm", "--i-understand-profile-overwrite",
                        ]
                    ),
                    0,
                )
        self.assertEqual(self._sent(send.call_args_list), [0x03])

    def test_cli_without_only_still_sends_everything(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(_profile(colors=True)), encoding="utf-8")
            with (
                patch("spade65.cli.discover_devices", return_value=[_main_device()]),
                patch(
                    "spade65.cli.send_feature_report", side_effect=lambda d, r: len(r)
                ) as send,
                redirect_stdout(io.StringIO()),
            ):
                main(
                    [
                        "profile", "apply", str(path),
                        "--confirm", "--i-understand-profile-overwrite",
                    ]
                )
        self.assertEqual(self._sent(send.call_args_list), [0x03, 0x02, 0x07])

    def test_cli_rejects_a_keymap_scope_that_would_strand_a_macro(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(_profile(bound=True)), encoding="utf-8")
            error = io.StringIO()
            with (
                patch("spade65.cli.discover_devices", return_value=[_main_device()]),
                patch("spade65.cli.send_feature_report") as send,
                redirect_stdout(io.StringIO()),
                redirect_stderr(error),
            ):
                self.assertEqual(
                    main(
                        [
                            "profile", "apply", str(path), "--only", "keymap",
                            "--confirm", "--i-understand-profile-overwrite",
                        ]
                    ),
                    1,
                )
        self.assertIn("macro 0", error.getvalue())
        send.assert_not_called()

    def test_gui_only_keymap_does_not_touch_the_lighting(self) -> None:
        with (
            patch("spade65.gui.discover_devices", return_value=[_main_device()]),
            patch(
                "spade65.gui.send_feature_report", side_effect=lambda d, r: len(r)
            ) as send,
        ):
            result = execute_action(
                "profile",
                {
                    "profile": _profile(colors=True),
                    "confirmation": "APPLY PROFILE",
                    "scopes": ["keymap"],
                },
            )
        self.assertEqual(self._sent(send.call_args_list), [0x03])
        self.assertEqual(result["scopes"], ["keymap"])

    def test_gui_without_scopes_fails_closed_before_device_discovery(self) -> None:
        with (
            patch("spade65.gui.discover_devices") as discover,
            patch("spade65.gui.send_feature_report") as send,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "profile scopes are required"
            ):
                execute_action(
                    "profile",
                    {
                        "profile": _profile(colors=True),
                        "confirmation": "APPLY PROFILE",
                    },
                )
        discover.assert_not_called()
        send.assert_not_called()

    def test_gui_still_demands_the_typed_confirmation(self) -> None:
        with (
            patch("spade65.gui.discover_devices", return_value=[_main_device()]),
            patch("spade65.gui.send_feature_report") as send,
        ):
            with self.assertRaisesRegex(RuntimeError, "APPLY PROFILE"):
                execute_action(
                    "profile",
                    {"profile": _profile(), "scopes": ["keymap"]},
                )
        send.assert_not_called()

    def test_gui_rejects_a_malformed_scope_list(self) -> None:
        for scopes in ("keymap", None, ["keymap", None]):
            with (
                self.subTest(scopes=scopes),
                patch("spade65.gui.discover_devices") as discover,
                patch("spade65.gui.send_feature_report") as send,
            ):
                with self.assertRaisesRegex(RuntimeError, "must be a list"):
                    execute_action(
                        "profile",
                        {
                            "profile": _profile(),
                            "confirmation": "APPLY PROFILE",
                            "scopes": scopes,
                        },
                    )
                discover.assert_not_called()
                send.assert_not_called()

    def test_web_defaults_leave_per_key_colors_out_of_apply(self) -> None:
        page = (
            files("spade65.web")
            .joinpath("index.html")
            .read_text(encoding="utf-8")
        )

        def input_tag(identifier: str) -> str:
            match = re.search(rf'<input id="{identifier}"[^>]*>', page)
            if match is None:
                self.fail(f"missing {identifier} checkbox")
            return match.group(0)

        self.assertIn(" checked", input_tag("scopeKeymap"))
        self.assertIn(" checked", input_tag("scopeMacros"))
        self.assertNotIn(" checked", input_tag("scopeColors"))

        english = json.loads(
            files("spade65.web.locales")
            .joinpath("en.json")
            .read_text(encoding="utf-8")
        )
        indonesian = json.loads(
            files("spade65.web.locales")
            .joinpath("id.json")
            .read_text(encoding="utf-8")
        )
        self.assertIn("opt-in", english["profile.scopeHint"])
        self.assertIn("secara sengaja", indonesian["profile.scopeHint"])

    def test_the_web_ui_is_told_the_scope_names(self) -> None:
        from spade65.gui import gui_metadata

        with patch("spade65.gui.discover_devices", return_value=[]):
            self.assertEqual(
                gui_metadata()["profile_scopes"], list(PROFILE_SCOPES)
            )


if __name__ == "__main__":
    unittest.main()
