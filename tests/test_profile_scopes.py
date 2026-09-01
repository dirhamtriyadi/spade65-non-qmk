"""Profile scopes and the vendor-compatible lighting compensation sequence.

The firmware clears its current lighting when a keymap/profile frame is
accepted.  The official application compensates by sending lighting after the
keymap and macros.  Scoped applies must preserve that ordering without turning
the compensating report into an unrelated per-key-colour write.
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
    EFFECTS,
    MAIN_REPORT_ID,
    MAIN_REPORT_LENGTH,
    MAIN_USAGE,
    SHORT_REPORT_ID,
    SHORT_REPORT_LENGTH,
    SHORT_USAGE,
    VENDOR_ID,
    debounce_report,
    rgb_effect_report,
)
from spade65.keymap import (
    DEFAULT_LIGHTING,
    PROFILE_SCOPES,
    compile_profile,
    profile_lighting_recovery_reports,
    profile_reports,
    profile_template,
)
from tests.session_support import FeatureSessionRecorder


def _opcodes(reports) -> list[int]:
    return [report[1] for report in reports]


_TEMPLATE_LIGHTING = object()


def _profile(
    *,
    colors: bool = False,
    macro: bool = False,
    bound: bool = False,
    lighting: object = _TEMPLATE_LIGHTING,
):
    profile = profile_template()
    if lighting is not _TEMPLATE_LIGHTING:
        profile["lighting"] = lighting
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

    def test_default_replays_active_lighting_not_an_unapplied_color_draft(self) -> None:
        profile = _profile(colors=True, macro=True)
        reports = profile_reports(profile, compile_profile(profile))
        self.assertEqual(_opcodes(reports), [0x03, 0x02])
        self.assertEqual(reports[-1], rgb_effect_report(**DEFAULT_LIGHTING))

    def test_full_apply_sends_only_macros_referenced_by_the_keymap(self) -> None:
        profile = _profile()
        profile["macros"] = [
            {"index": index, "repeat": 1, "events": []}
            for index in (0, 1, 2)
        ]
        profile["layers"]["normal"]["esc"] = {"macro": 2}
        profile["layers"]["fn1"]["q"] = {"macro": 0}
        profile["layers"]["fn2"]["q"] = {"macro": 2}
        compiled = compile_profile(profile)

        full = profile_reports(profile, compiled)
        self.assertEqual(_opcodes(full), [0x03, 0x05, 0x05, 0x02])
        self.assertEqual(full[1][3], 0)
        self.assertEqual(full[2][3], 2)

        macro_only = profile_reports(profile, compiled, scopes=["macros"])
        self.assertEqual(_opcodes(macro_only), [0x05, 0x05, 0x05])
        self.assertEqual([report[3] for report in macro_only], [0, 1, 2])

    def test_keymap_scope_restores_a_built_in_lighting_snapshot(self) -> None:
        profile = _profile(
            lighting={
                "effect": "fixed",
                "brightness": 3,
                "speed": 2,
                "color_index": 5,
                "multicolor": False,
            }
        )
        reports = profile_reports(
            profile, compile_profile(profile), scopes=["keymap"]
        )
        self.assertEqual(_opcodes(reports), [0x03, 0x02])
        self.assertEqual(
            reports[1],
            rgb_effect_report(
                "fixed",
                brightness=3,
                speed=2,
                color_index=5,
                multicolor=False,
            ),
        )
        self.assertNotIn(0x07, _opcodes(reports))

    def test_keymap_scope_restores_a_custom_snapshot_and_its_colors(self) -> None:
        profile = _profile(
            colors=True,
            lighting={
                "effect": "custom",
                "brightness": 2,
                "speed": 4,
                "color_index": 0,
                "multicolor": False,
                "colors": {"esc": "#0000ff"},
            },
        )
        compiled = compile_profile(profile)
        reports = profile_reports(profile, compiled, scopes=["keymap"])
        self.assertEqual(_opcodes(reports), [0x03, 0x02, 0x07])
        self.assertEqual(
            reports[1],
            rgb_effect_report(
                "custom",
                brightness=2,
                speed=4,
                color_index=0,
                multicolor=False,
            ),
        )
        self.assertNotEqual(reports[2], compiled["colors"])
        color_offset = 8 + 3 * 17
        self.assertEqual(
            reports[2][color_offset : color_offset + 3],
            bytes((0x00, 0x00, 0xFF)),
        )
        self.assertEqual(
            compiled["colors"][color_offset : color_offset + 3],
            bytes((0xFF, 0x00, 0x00)),
        )

    def test_lighting_scope_replays_the_cached_snapshot_only(self) -> None:
        profile = _profile(colors=True, macro=True)
        reports = profile_reports(
            profile, compile_profile(profile), scopes=["colors"]
        )
        self.assertEqual(_opcodes(reports), [0x02])
        self.assertEqual(reports[0], rgb_effect_report(**DEFAULT_LIGHTING))
        self.assertNotIn(0x03, _opcodes(reports))
        self.assertNotIn(0x05, _opcodes(reports))
        self.assertNotIn(0x07, _opcodes(reports))

    def test_lighting_scope_preserves_the_exact_cached_custom_snapshot(self) -> None:
        profile = _profile(
            colors=True,
            lighting={
                "effect": "custom",
                "brightness": 2,
                "speed": 3,
                "color_index": 6,
                "multicolor": True,
                "colors": {"esc": "#0000ff"},
            },
        )
        compiled = compile_profile(profile)
        reports = profile_reports(
            profile, compiled, scopes=["colors"]
        )
        self.assertEqual(_opcodes(reports), [0x02, 0x07])
        self.assertEqual(
            reports[0],
            rgb_effect_report(
                "custom",
                brightness=2,
                speed=3,
                color_index=6,
                multicolor=True,
            ),
        )
        self.assertEqual(reports[0][12], 7)
        self.assertNotEqual(reports[1], compiled["colors"])
        color_offset = 8 + 3 * 17
        self.assertEqual(
            reports[1][color_offset : color_offset + 3],
            bytes((0x00, 0x00, 0xFF)),
        )
        self.assertEqual(
            compiled["colors"][color_offset : color_offset + 3],
            bytes((0xFF, 0x00, 0x00)),
        )

    def test_macros_scope_does_not_rewrite_unrelated_lighting(self) -> None:
        profile = _profile(bound=True)
        reports = profile_reports(
            profile, compile_profile(profile), scopes=["macros"]
        )
        self.assertEqual(_opcodes(reports), [0x05])

    def test_lighting_scope_does_not_require_a_per_key_draft(self) -> None:
        profile = _profile()
        reports = profile_reports(
            profile, compile_profile(profile), scopes=["colors"]
        )
        self.assertEqual(_opcodes(reports), [0x02])
        self.assertEqual(reports[0], rgb_effect_report(**DEFAULT_LIGHTING))

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
        self.assertEqual(_opcodes(reports), [0x03, 0x05, 0x02])

    def test_a_keymap_without_macro_bindings_may_go_alone(self) -> None:
        profile = _profile(macro=True)
        reports = profile_reports(
            profile, compile_profile(profile), scopes=["keymap"]
        )
        self.assertEqual(_opcodes(reports), [0x03, 0x02])

    def test_template_and_legacy_profiles_use_the_vendor_default_lighting(self) -> None:
        template = profile_template()
        self.assertEqual(template["lighting"], DEFAULT_LIGHTING)
        self.assertIsNot(template["lighting"], DEFAULT_LIGHTING)

        expected = rgb_effect_report(**DEFAULT_LIGHTING)
        for variant in ("template", "missing", "null"):
            with self.subTest(variant=variant):
                profile = _profile()
                if variant == "missing":
                    profile.pop("lighting")
                elif variant == "null":
                    profile["lighting"] = None
                reports = profile_reports(
                    profile, compile_profile(profile), scopes=["keymap"]
                )
                self.assertEqual(_opcodes(reports), [0x03, 0x02])
                self.assertEqual(reports[1], expected)

    def test_legacy_per_key_color_draft_does_not_become_active_lighting(self) -> None:
        profile = _profile(colors=True)
        profile.pop("lighting")
        compiled = compile_profile(profile)
        reports = profile_reports(profile, compiled, scopes=["keymap"])

        self.assertEqual(_opcodes(reports), [0x03, 0x02])
        self.assertEqual(reports[1], rgb_effect_report(**DEFAULT_LIGHTING))
        self.assertNotIn(compiled["colors"], reports)

        # Explicit null is not the legacy shape and deliberately requests the
        # documented vendor default even when a colour draft exists.
        profile["lighting"] = None
        explicit = profile_reports(
            profile, compile_profile(profile), scopes=["keymap"]
        )
        self.assertEqual(_opcodes(explicit), [0x03, 0x02])
        self.assertEqual(explicit[1], rgb_effect_report(**DEFAULT_LIGHTING))

    def test_malformed_non_null_lighting_is_rejected(self) -> None:
        cases = (
            ([], "object or null"),
            ({"effect": "fixed"}, "missing fields"),
            (
                {**DEFAULT_LIGHTING, "extra": 1},
                "unknown profile lighting fields",
            ),
            ({**DEFAULT_LIGHTING, "effect": 1}, "effect must be a string"),
            (
                {**DEFAULT_LIGHTING, "brightness": True},
                "brightness must be an integer",
            ),
            (
                {**DEFAULT_LIGHTING, "multicolor": 1},
                "multicolor must be true or false",
            ),
            ({**DEFAULT_LIGHTING, "brightness": 5}, "brightness must be between"),
            ({**DEFAULT_LIGHTING, "effect": "not-an-effect"}, "unknown RGB effect"),
            ({**DEFAULT_LIGHTING, "effect": "custom"}, "missing fields: colors"),
        )
        for lighting, message in cases:
            with self.subTest(lighting=lighting):
                with self.assertRaisesRegex(ValueError, message):
                    compile_profile(_profile(lighting=lighting))

    def test_an_empty_or_unknown_scope_is_rejected(self) -> None:
        profile = _profile()
        compiled = compile_profile(profile)
        with self.assertRaisesRegex(ValueError, "at least one"):
            profile_reports(profile, compiled, scopes=[])
        with self.assertRaisesRegex(ValueError, "unknown profile scope"):
            profile_reports(profile, compiled, scopes=["lighting"])

    def test_scope_order_does_not_change_the_write_order(self) -> None:
        # Reports must always go keymap, macros, then the compensating lighting
        # report regardless of the order in which scopes were supplied.
        profile = _profile(bound=True)
        reports = profile_reports(
            profile,
            compile_profile(profile),
            scopes=["macros", "keymap"],
        )
        self.assertEqual(_opcodes(reports), [0x03, 0x05, 0x02])

    def test_all_scopes_never_activate_the_top_level_color_draft(self) -> None:
        profile = _profile(
            colors=True,
            bound=True,
            lighting={
                "effect": "fixed",
                "brightness": 3,
                "speed": 2,
                "color_index": 4,
                "multicolor": False,
            },
        )
        compiled = compile_profile(profile)
        reports = profile_reports(
            profile,
            compiled,
            scopes=["colors", "macros", "keymap"],
        )
        self.assertEqual(_opcodes(reports), [0x03, 0x05, 0x02])
        self.assertEqual(
            reports[-1],
            rgb_effect_report(
                "fixed",
                brightness=3,
                speed=2,
                color_index=4,
                multicolor=False,
            ),
        )
        self.assertNotIn(compiled["colors"], reports)

    def test_recovery_is_only_the_post_keymap_lighting_suffix(self) -> None:
        profile = _profile(
            bound=True,
            lighting={
                "effect": "custom",
                "brightness": 4,
                "speed": 5,
                "color_index": 0,
                "multicolor": False,
                "colors": {"esc": "#123456"},
            },
        )
        reports = profile_reports(profile, compile_profile(profile))
        recovery = profile_lighting_recovery_reports(
            reports, compile_profile(profile)["lighting"]
        )
        self.assertEqual(_opcodes(reports), [0x03, 0x05, 0x02, 0x07])
        self.assertEqual(_opcodes(recovery), [0x02, 0x07])
        self.assertEqual(recovery, reports[-2:])

        macro_only = profile_reports(
            profile, compile_profile(profile), scopes=["macros"]
        )
        self.assertEqual(
            profile_lighting_recovery_reports(
                macro_only, compile_profile(profile)["lighting"]
            ),
            (),
        )

    def test_all_scopes_and_recovery_use_the_previous_snapshot(self) -> None:
        profile = _profile(
            colors=True,
            lighting={
                "effect": "fixed",
                "brightness": 3,
                "speed": 2,
                "color_index": 4,
                "multicolor": False,
            },
        )
        compiled = compile_profile(profile)
        planned = profile_reports(
            profile, compiled, scopes=["keymap", "colors"]
        )
        recovery = profile_lighting_recovery_reports(
            planned, compiled["lighting"]
        )
        self.assertEqual(_opcodes(planned), [0x03, 0x02])
        self.assertEqual(_opcodes(recovery), [0x02])
        self.assertEqual(
            recovery[0],
            rgb_effect_report(
                "fixed",
                brightness=3,
                speed=2,
                color_index=4,
                multicolor=False,
            ),
        )
        colors_only = profile_reports(
            profile, compiled, scopes=["colors"]
        )
        self.assertEqual(_opcodes(colors_only), [0x02])
        self.assertEqual(colors_only, recovery)
        self.assertEqual(
            profile_lighting_recovery_reports(
                colors_only, compiled["lighting"]
            ),
            recovery,
        )


def _main_device() -> Device:
    return Device(
        path=Path("/dev/hidraw-main"),
        vendor_id=VENDOR_ID,
        product_id=0x0351,
        usages={MAIN_USAGE},
        reports=[ReportShape("feature", MAIN_REPORT_ID, (MAIN_REPORT_LENGTH - 1) * 8)],
    )


def _short_device() -> Device:
    return Device(
        path=Path("/dev/hidraw-short"),
        vendor_id=VENDOR_ID,
        product_id=0x0351,
        usages={SHORT_USAGE},
        reports=[
            ReportShape(
                "feature", SHORT_REPORT_ID, (SHORT_REPORT_LENGTH - 1) * 8
            )
        ],
    )


def _interfaces() -> list[Device]:
    return [_main_device(), _short_device()]


class ScopedApplyTests(unittest.TestCase):
    """The CLI and the GUI must both honour the scope, not just the helper."""

    def _sent(self, calls) -> list[int]:
        return [call.args[1][1] for call in calls]

    def test_cli_only_keymap_restores_the_lighting(self) -> None:
        sessions = FeatureSessionRecorder()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(_profile(colors=True)), encoding="utf-8")
            with (
                patch("spade65.cli.discover_devices", return_value=_interfaces()),
                patch(
                    "spade65.cli.feature_report_session", new=sessions.session
                ),
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
        self.assertEqual(
            sessions.frames,
            [
                (_main_device().path, MAIN_REPORT_ID, 0x03),
                (_main_device().path, MAIN_REPORT_ID, 0x02),
                (_short_device().path, SHORT_REPORT_ID, 0x09),
            ],
        )
        self.assertEqual(sessions.calls[-1][1], debounce_report(5))
        self.assertEqual(
            [device.path for device in sessions.opened],
            [_main_device().path, _short_device().path],
        )
        self.assertEqual(
            [device.path for device in sessions.closed],
            [_short_device().path, _main_device().path],
        )

    def test_cli_without_only_replays_the_active_lighting_snapshot(self) -> None:
        sessions = FeatureSessionRecorder()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(_profile(colors=True)), encoding="utf-8")
            with (
                patch("spade65.cli.discover_devices", return_value=_interfaces()),
                patch(
                    "spade65.cli.feature_report_session", new=sessions.session
                ),
                redirect_stdout(io.StringIO()),
            ):
                main(
                    [
                        "profile", "apply", str(path),
                        "--confirm", "--i-understand-profile-overwrite",
                    ]
                )
        self.assertEqual(sessions.opcodes, [0x03, 0x02, 0x09])

    def test_cli_colors_and_macros_scopes_do_not_send_a_debounce_tail(self) -> None:
        for scopes, expected in ((["colors"], [0x02]), (["macros"], [0x05])):
            with self.subTest(scopes=scopes), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "profile.json"
                path.write_text(json.dumps(_profile(bound=True)), encoding="utf-8")
                command = [
                    "profile",
                    "apply",
                    str(path),
                    "--only",
                    *scopes,
                    "--confirm",
                    "--i-understand-profile-overwrite",
                ]
                with (
                    patch("spade65.cli.discover_devices", return_value=_interfaces()),
                    patch(
                        "spade65.cli.send_feature_report",
                        side_effect=lambda _device, report: len(report),
                    ) as send,
                    redirect_stdout(io.StringIO()),
                ):
                    self.assertEqual(main(command), 0)
            self.assertEqual(self._sent(send.call_args_list), expected)
            self.assertTrue(
                all(
                    call.args[0].path == _main_device().path
                    for call in send.call_args_list
                )
            )

    def test_cli_rejects_invalid_debounce_before_device_discovery(self) -> None:
        profile = _profile()
        profile["settings"]["debounce_ms"] = 0
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(profile), encoding="utf-8")
            with (
                patch("spade65.cli.discover_devices") as discover,
                patch("spade65.cli.feature_report_session") as session,
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()),
            ):
                self.assertEqual(
                    main(
                        [
                            "profile",
                            "apply",
                            str(path),
                            "--only",
                            "keymap",
                            "--confirm",
                            "--i-understand-profile-overwrite",
                        ]
                    ),
                    1,
                )
        discover.assert_not_called()
        session.assert_not_called()

    def test_cli_per_key_forwards_the_complete_effect_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(_profile(colors=True)), encoding="utf-8")
            with (
                patch("spade65.cli.discover_devices", return_value=_interfaces()),
                patch(
                    "spade65.cli.send_feature_report",
                    side_effect=lambda _device, report: len(report),
                ) as send,
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(
                    main(
                        [
                            "per-key-rgb",
                            str(path),
                            "--brightness",
                            "2",
                            "--speed",
                            "3",
                            "--color-index",
                            "6",
                            "--confirm",
                        ]
                    ),
                    0,
                )
        effect = send.call_args_list[0].args[1]
        self.assertEqual(self._sent(send.call_args_list), [0x02, 0x07])
        self.assertEqual(effect[9:13], bytes((EFFECTS["custom"], 2, 3, 6)))

    def test_macro_report_uses_the_vendor_200ms_follow_up_delay(self) -> None:
        sessions = FeatureSessionRecorder()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(_profile(bound=True)), encoding="utf-8")
            with (
                patch("spade65.cli.discover_devices", return_value=_interfaces()),
                patch(
                    "spade65.cli.feature_report_session", new=sessions.session
                ),
                patch("spade65.cli.time.sleep") as sleep,
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(
                    main(
                        [
                            "profile",
                            "apply",
                            str(path),
                            "--confirm",
                            "--i-understand-profile-overwrite",
                        ]
                    ),
                    0,
                )
        self.assertEqual(
            [call.args[0] for call in sleep.call_args_list],
            [0.1, 0.2, 0.1, 0.01],
        )

    def test_cli_rejects_a_keymap_scope_that_would_strand_a_macro(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(_profile(bound=True)), encoding="utf-8")
            error = io.StringIO()
            with (
                patch("spade65.cli.discover_devices", return_value=[_main_device()]),
                patch("spade65.cli.feature_report_session") as session,
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
        session.assert_not_called()

    def test_gui_only_keymap_restores_the_lighting(self) -> None:
        sessions = FeatureSessionRecorder()
        with (
            patch("spade65.gui.discover_devices", return_value=_interfaces()),
            patch(
                "spade65.gui.feature_report_session", new=sessions.session
            ),
        ):
            result = execute_action(
                "profile",
                {
                    "profile": _profile(colors=True),
                    "confirmed": True,
                    "scopes": ["keymap"],
                },
            )
        self.assertEqual(
            sessions.frames,
            [
                (_main_device().path, MAIN_REPORT_ID, 0x03),
                (_main_device().path, MAIN_REPORT_ID, 0x02),
                (_short_device().path, SHORT_REPORT_ID, 0x09),
            ],
        )
        self.assertEqual(result["scopes"], ["keymap"])

    def test_gui_failure_recovers_the_previous_not_the_candidate_lighting(self) -> None:
        candidate = _profile(
            lighting={
                "effect": "custom",
                "brightness": 4,
                "speed": 5,
                "color_index": 0,
                "multicolor": False,
                "colors": {"esc": "#ff0000"},
            }
        )
        previous = {
            "effect": "fixed",
            "brightness": 2,
            "speed": 3,
            "color_index": 4,
            "multicolor": False,
        }
        results = iter((619, 620))
        sessions = FeatureSessionRecorder(
            lambda _device, _report: next(results)
        )
        with (
            patch("spade65.gui.discover_devices", return_value=_interfaces()),
            patch(
                "spade65.gui.feature_report_session", new=sessions.session
            ),
            patch(
                "spade65.gui.time.sleep",
                side_effect=lambda delay: sessions.events.append(("sleep", delay)),
            ) as sleep,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "cached lighting recovery succeeded"
            ):
                execute_action(
                    "profile",
                    {
                        "profile": candidate,
                        "recovery_lighting": previous,
                        "confirmed": True,
                        "scopes": ["keymap"],
                    },
                )
        self.assertEqual(len(sessions.calls), 2)
        self.assertEqual(
            sessions.calls[1][1], rgb_effect_report(**previous)
        )
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [0.1])
        self.assertEqual(
            sessions.events[-3:],
            [
                ("sleep", 0.1),
                ("close", _short_device().path),
                ("close", _main_device().path),
            ],
        )

    def test_gui_custom_recovery_waits_after_effect_and_palette(self) -> None:
        previous = {
            "effect": "custom",
            "brightness": 3,
            "speed": 4,
            "color_index": 0,
            "multicolor": False,
            "colors": {"esc": "#123456"},
        }
        results = iter((619, 620, 620))
        sessions = FeatureSessionRecorder(
            lambda _device, _report: next(results)
        )
        with (
            patch("spade65.gui.discover_devices", return_value=_interfaces()),
            patch(
                "spade65.gui.feature_report_session", new=sessions.session
            ),
            patch(
                "spade65.gui.time.sleep",
                side_effect=lambda delay: sessions.events.append(("sleep", delay)),
            ) as sleep,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "cached lighting recovery succeeded"
            ):
                execute_action(
                    "profile",
                    {
                        "profile": _profile(),
                        "recovery_lighting": previous,
                        "confirmed": True,
                        "scopes": ["keymap"],
                    },
                )

        self.assertEqual(sessions.opcodes, [0x03, 0x02, 0x07])
        self.assertEqual(
            [call.args[0] for call in sleep.call_args_list],
            [0.1, 0.05],
        )
        self.assertEqual(
            [
                event
                for event in sessions.events
                if event[0] in {"sleep", "close"}
            ][-4:],
            [
                ("sleep", 0.1),
                ("sleep", 0.05),
                ("close", _short_device().path),
                ("close", _main_device().path),
            ],
        )

    def test_gui_colors_and_macros_scopes_do_not_send_a_debounce_tail(self) -> None:
        for scopes, expected in ((["colors"], [0x02]), (["macros"], [0x05])):
            with (
                self.subTest(scopes=scopes),
                patch("spade65.gui.discover_devices", return_value=_interfaces()),
                patch(
                    "spade65.gui.send_feature_report",
                    side_effect=lambda _device, report: len(report),
                ) as send,
            ):
                execute_action(
                    "profile",
                    {
                        "profile": _profile(bound=True),
                        "confirmed": True,
                        "scopes": scopes,
                    },
                )
            self.assertEqual(self._sent(send.call_args_list), expected)
            self.assertTrue(
                all(
                    call.args[0].path == _main_device().path
                    for call in send.call_args_list
                )
            )

    def test_gui_rejects_invalid_debounce_before_device_discovery(self) -> None:
        profile = _profile()
        profile["settings"]["debounce_ms"] = 0
        with (
            patch("spade65.gui.discover_devices") as discover,
            patch("spade65.gui.feature_report_session") as session,
        ):
            with self.assertRaisesRegex(ValueError, "debounce"):
                execute_action(
                    "profile",
                    {
                        "profile": profile,
                        "confirmed": True,
                        "scopes": ["keymap"],
                    },
                )
        discover.assert_not_called()
        session.assert_not_called()

    def test_gui_requires_the_short_companion_before_writing_keymap(self) -> None:
        with (
            patch("spade65.gui.discover_devices", return_value=[_main_device()]),
            patch("spade65.gui.feature_report_session") as session,
        ):
            with self.assertRaisesRegex(RuntimeError, "companion HID interface"):
                execute_action(
                    "profile",
                    {
                        "profile": _profile(),
                        "confirmed": True,
                        "scopes": ["keymap"],
                    },
                )
        session.assert_not_called()

    def test_gui_without_scopes_fails_closed_before_device_discovery(self) -> None:
        with (
            patch("spade65.gui.discover_devices") as discover,
            patch("spade65.gui.feature_report_session") as session,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "profile scopes are required"
            ):
                execute_action(
                    "profile",
                    {
                        "profile": _profile(colors=True),
                        "confirmed": True,
                    },
                )
        discover.assert_not_called()
        session.assert_not_called()

    def test_gui_still_demands_the_confirmation_flag(self) -> None:
        with (
            patch("spade65.gui.discover_devices", return_value=[_main_device()]),
            patch("spade65.gui.feature_report_session") as session,
        ):
            with self.assertRaisesRegex(RuntimeError, "confirm the profile overwrite"):
                execute_action(
                    "profile",
                    {"profile": _profile(), "scopes": ["keymap"]},
                )
        session.assert_not_called()

    def test_gui_rejects_a_malformed_scope_list(self) -> None:
        for scopes in ("keymap", None, ["keymap", None]):
            with (
                self.subTest(scopes=scopes),
                patch("spade65.gui.discover_devices") as discover,
                patch("spade65.gui.feature_report_session") as session,
            ):
                with self.assertRaisesRegex(RuntimeError, "must be a list"):
                    execute_action(
                        "profile",
                        {
                            "profile": _profile(),
                            "confirmed": True,
                            "scopes": scopes,
                        },
                    )
                discover.assert_not_called()
                session.assert_not_called()

    def test_web_defaults_leave_every_apply_scope_unchecked(self) -> None:
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

        self.assertNotIn(" checked", input_tag("scopeKeymap"))
        self.assertNotIn(" checked", input_tag("scopeMacros"))
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
        self.assertIn("Nothing is selected", english["profile.scopeHint"])
        self.assertIn("Tidak ada bagian", indonesian["profile.scopeHint"])

    def test_web_applies_the_current_lighting_intent_and_persists_on_success(self) -> None:
        javascript = (
            files("spade65.web")
            .joinpath("app.js")
            .read_text(encoding="utf-8")
        )
        self.assertIn("function rememberLighting(value, target)", javascript)
        self.assertEqual(javascript.count("rememberLighting(lighting, target)"), 2)
        self.assertEqual(javascript.count("rememberLighting(appliedLighting, target)"), 1)
        self.assertIn(
            "items[name].lighting = cloneJson(lighting)",
            javascript,
        )
        self.assertIn(
            "items[name].colors = cloneJson(lighting.colors)",
            javascript,
        )
        self.assertIn("colors: cloneJson(profile.colors)", javascript)
        self.assertIn("effect: 'custom'", javascript)
        candidate = javascript.split("function lightingForProfileApply()", 1)[
            1
        ].split("function selectBuiltInLightingDraft", 1)[0]
        self.assertIn("colors: cloneJson(draft.colors)", candidate)
        self.assertNotIn("colors: cloneJson(profile.colors)", candidate)
        apply_body = javascript.split("async function applyProfile()", 1)[1].split(
            "async function downloadJson", 1
        )[0]
        self.assertIn(
            "writesLighting = scopes.includes('keymap') || scopes.includes('colors')",
            apply_body,
        )
        self.assertIn(
            "if (appliedLighting) requestProfile.lighting = cloneJson(appliedLighting)",
            apply_body,
        )
        self.assertIn("rememberLighting(appliedLighting, target)", apply_body)
        self.assertIn(
            "requestProfile.settings.debounce_ms = debounceMs",
            apply_body,
        )
        self.assertIn(
            "payload.recovery_lighting = cloneJson(previousLighting)",
            apply_body,
        )
        self.assertIn("rememberDebounce(debounceMs, target)", apply_body)
        self.assertIn("function rememberDebounce(value, target)", javascript)
        self.assertEqual(apply_body.count("confirm("), 1)
        self.assertNotIn("prompt(", apply_body)
        self.assertIn("confirmed: true", apply_body)

    def test_web_keeps_legacy_per_key_colors_as_a_draft(self) -> None:
        javascript = (
            files("spade65.web")
            .joinpath("app.js")
            .read_text(encoding="utf-8")
        )
        migration = javascript.split("function migrateProfileLighting", 1)[1].split(
            "function savedLighting", 1
        )[0]
        self.assertIn("cloneJson(DEFAULT_LIGHTING)", migration)
        self.assertNotIn("effect: 'custom'", migration)
        self.assertNotIn("colors: cloneJson", migration)

    def test_web_represents_custom_lighting_in_the_effect_selector(self) -> None:
        javascript = (
            files("spade65.web")
            .joinpath("app.js")
            .read_text(encoding="utf-8")
        )
        renderer = javascript.split("function renderEffects()", 1)[1].split(
            "function normalizedLighting", 1
        )[0]
        controls = javascript.split("function renderLightingControls()", 1)[
            1
        ].split("function renderUsageList", 1)[0]
        custom = javascript.split("function selectCustomLightingDraft()", 1)[
            1
        ].split("function updateLightingDraftParameters", 1)[0]
        self.assertIn("effects = meta.effects", renderer)
        self.assertIn("lighting.effect", controls)
        self.assertIn("$('effectSelect').value = 'custom'", custom)

    def test_the_web_ui_is_told_the_scope_names(self) -> None:
        from spade65.gui import gui_metadata

        with patch("spade65.gui.discover_devices", return_value=[]):
            self.assertEqual(
                gui_metadata()["profile_scopes"], list(PROFILE_SCOPES)
            )


if __name__ == "__main__":
    unittest.main()
