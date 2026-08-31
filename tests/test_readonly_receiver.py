import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from spade65.device import Device, ReportShape
from spade65.cli import main
from spade65.gui import execute_action, gui_metadata
from spade65.keymap import profile_template
from spade65.service import apply_profile, stream_colors
from spade65.protocol import (
    MAIN_REPORT_ID,
    MAIN_REPORT_LENGTH,
    MAIN_USAGE,
    OBSERVED_PRODUCT_IDS,
    OUTPUT_USAGE,
    PRODUCT_IDS,
    READ_ONLY_PRODUCT_IDS,
    SHORT_REPORT_ID,
    SHORT_REPORT_LENGTH,
    SHORT_USAGE,
    VENDOR_ID,
    configuration_status,
)
from spade65.transport import discover_hidapi


class _ReceiverHandle:
    def __init__(self) -> None:
        self.closed = False

    def open_path(self, _path: bytes) -> None:
        pass

    def get_report_descriptor(self) -> list[int]:
        return []

    def close(self) -> None:
        self.closed = True


class _ReceiverHid:
    def __init__(self) -> None:
        self.handles: list[_ReceiverHandle] = []

    def enumerate(self, vendor_id: int, product_id: int):
        self.enumerated = (vendor_id, product_id)
        return [{
            "path": b"receiver-output",
            "vendor_id": VENDOR_ID,
            "product_id": 0x0352,
            "product_string": "JP Spade65",
            "usage_page": OUTPUT_USAGE[0],
            "usage": OUTPUT_USAGE[1],
        }]

    def device(self) -> _ReceiverHandle:
        handle = _ReceiverHandle()
        self.handles.append(handle)
        return handle


def _adversarial_receiver() -> Device:
    """A 0352 receiver that advertises every configuration shape.

    Usage and descriptor checks cannot reject this device, so the product-ID
    allowlist is the only term left that can — which is what the safety
    invariant is actually stated in terms of.
    """

    return Device(
        path=Path("/dev/hidraw-receiver"),
        vendor_id=VENDOR_ID,
        product_id=0x0352,
        name="JP Spade65",
        usages={MAIN_USAGE, SHORT_USAGE, OUTPUT_USAGE},
        reports=[
            ReportShape("feature", MAIN_REPORT_ID, (MAIN_REPORT_LENGTH - 1) * 8),
            ReportShape("feature", SHORT_REPORT_ID, (SHORT_REPORT_LENGTH - 1) * 8),
            ReportShape("output", 0x06, 63 * 8),
        ],
    )


def _receiver() -> Device:
    return Device(
        path=Path("/dev/hidraw-receiver"),
        vendor_id=VENDOR_ID,
        product_id=0x0352,
        name="JP Spade65",
        usages={OUTPUT_USAGE},
        reports=[ReportShape("output", 6, 63 * 8)],
    )


class ReadonlyReceiverTests(unittest.TestCase):
    def test_observed_receiver_is_not_in_the_write_identity_allowlist(self) -> None:
        self.assertEqual(set(PRODUCT_IDS), {0x0351, 0x0356})
        self.assertIn(0x0352, OBSERVED_PRODUCT_IDS)
        self.assertNotIn(0x0352, PRODUCT_IDS)

    def test_read_only_identities_are_the_single_source_of_truth(self) -> None:
        # Adding an identity here must change what every surface reports, so the
        # constant cannot drift away from the classification it names.
        self.assertEqual(set(READ_ONLY_PRODUCT_IDS), {0x0352})
        self.assertEqual(
            set(OBSERVED_PRODUCT_IDS),
            set(PRODUCT_IDS) | set(READ_ONLY_PRODUCT_IDS),
        )
        self.assertFalse(set(PRODUCT_IDS) & set(READ_ONLY_PRODUCT_IDS))
        for product_id in PRODUCT_IDS:
            self.assertEqual(configuration_status(product_id), "descriptor-gated")
        for product_id in READ_ONLY_PRODUCT_IDS:
            self.assertEqual(
                configuration_status(product_id), "unsupported-read-only"
            )
        # An identity in neither table must fail closed, not inherit the
        # writable label just because it is absent from the read-only table.
        self.assertEqual(configuration_status(0x9999), "unsupported-read-only")
        self.assertEqual(
            OBSERVED_PRODUCT_IDS[0x0352], READ_ONLY_PRODUCT_IDS[0x0352]
        )

    def test_cli_and_gui_agree_on_the_label_for_every_identity(self) -> None:
        # Both surfaces must classify an identity that is not in the write
        # allowlist as read-only, including one that exists only at test time.
        unlisted = _receiver()
        unlisted.product_id = 0x0399
        with (
            patch.dict(
                "spade65.protocol.OBSERVED_PRODUCT_IDS",
                {0x0399: "test receiver"},
            ),
            patch.dict(
                "spade65.protocol.READ_ONLY_PRODUCT_IDS",
                {0x0399: "test receiver"},
            ),
        ):
            with patch("spade65.gui.discover_devices", return_value=[unlisted]):
                gui_summary = gui_metadata()["devices"][0]
            probe_output = io.StringIO()
            with (
                patch("spade65.cli.discover_devices", return_value=[unlisted]),
                redirect_stdout(probe_output),
            ):
                self.assertEqual(main(["probe", "--json"]), 0)
            cli_summary = json.loads(probe_output.getvalue())[0]
        self.assertEqual(gui_summary["pid"], "0399")
        self.assertEqual(cli_summary["pid"], "0399")
        for summary in (gui_summary, cli_summary):
            self.assertEqual(
                summary["configuration_status"], "unsupported-read-only"
            )

        # And a writable identity is still labelled writable on both surfaces.
        wired = _receiver()
        wired.product_id = 0x0351
        with patch("spade65.gui.discover_devices", return_value=[wired]):
            self.assertEqual(
                gui_metadata()["devices"][0]["configuration_status"],
                "descriptor-gated",
            )
        probe_output = io.StringIO()
        with (
            patch("spade65.cli.discover_devices", return_value=[wired]),
            redirect_stdout(probe_output),
        ):
            main(["probe", "--json"])
        self.assertEqual(
            json.loads(probe_output.getvalue())[0]["configuration_status"],
            "descriptor-gated",
        )

    def test_hidapi_discovers_receiver_for_read_only_diagnostics(self) -> None:
        hid = _ReceiverHid()
        devices = discover_hidapi(hid)  # type: ignore[arg-type]
        self.assertEqual(hid.enumerated, (VENDOR_ID, 0))
        self.assertEqual([device.product_id for device in devices], [0x0352])
        self.assertIn(OUTPUT_USAGE, devices[0].usages)
        self.assertTrue(hid.handles[0].closed)

    def test_gui_reports_receiver_as_unsupported_read_only(self) -> None:
        with patch("spade65.gui.discover_devices", return_value=[_receiver()]):
            metadata = gui_metadata()
        self.assertEqual(len(metadata["devices"]), 1)
        summary = metadata["devices"][0]
        self.assertEqual(summary["pid"], "0352")
        self.assertEqual(summary["transport"], "2.4 GHz receiver")
        self.assertEqual(
            summary["configuration_status"], "unsupported-read-only"
        )

    def test_probe_and_info_report_receiver_without_enabling_writes(self) -> None:
        probe_output = io.StringIO()
        with (
            patch("spade65.cli.discover_devices", return_value=[_receiver()]),
            redirect_stdout(probe_output),
        ):
            self.assertEqual(main(["probe", "--json"]), 0)
        probe = json.loads(probe_output.getvalue())
        self.assertEqual(probe[0]["pid"], "0352")
        self.assertEqual(
            probe[0]["configuration_status"], "unsupported-read-only"
        )

        info_output = io.StringIO()
        with (
            patch("spade65.cli.discover_devices", return_value=[_receiver()]),
            patch(
                "spade65.cli.readonly_device_info",
                return_value={"usb_revision": "01.00"},
            ),
            redirect_stdout(info_output),
        ):
            self.assertEqual(main(["info"]), 0)
        info = json.loads(info_output.getvalue())
        self.assertEqual(info[0]["pid"], "0352")
        self.assertEqual(info[0]["usb_revision"], "01.00")
        self.assertEqual(
            info[0]["configuration_status"], "unsupported-read-only"
        )

    def test_no_gui_write_action_can_select_receiver(self) -> None:
        profile = profile_template()
        actions = [
            ("rgb", {"effect": "fixed"}),
            ("per-key", {"profile": profile}),
            (
                "profile",
                {"profile": profile, "confirmation": "APPLY PROFILE"},
            ),
            ("stream", {"profile": profile}),
            ("debounce", {"milliseconds": 5}),
            ("sleep", {"light_off": 1, "hibernate": 3}),
            ("reset", {"confirmation": "RESET SPADE65"}),
        ]
        for action, payload in actions:
            with (
                self.subTest(action=action),
                patch("spade65.gui.discover_devices", return_value=[_receiver()]),
                patch("spade65.gui.send_feature_report") as feature_write,
                patch("spade65.gui.send_output_report") as output_write,
            ):
                with self.assertRaisesRegex(RuntimeError, "no matching HID interface"):
                    execute_action(
                        action,
                        {"device": "/dev/hidraw-receiver", **payload},
                    )
                feature_write.assert_not_called()
                output_write.assert_not_called()


    def test_the_product_id_allowlist_alone_refuses_every_cli_write(self) -> None:
        receiver = _adversarial_receiver()
        profile = profile_template()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(profile), encoding="utf-8")
            commands = [
                ["rgb", "fixed"],
                ["debounce", "5"],
                ["sleep", "--light-off", "5", "--hibernate", "10"],
                ["reset", "--i-understand-reset"],
                [
                    "profile", "apply", str(path),
                    "--i-understand-profile-overwrite",
                ],
                ["per-key-rgb", str(path)],
                ["stream-rgb", str(path)],
            ]
            for command in commands:
                with (
                    self.subTest(command=command[0]),
                    patch(
                        "spade65.cli.discover_devices", return_value=[receiver]
                    ),
                    patch("spade65.cli.send_feature_report") as feature,
                    patch("spade65.cli.send_output_report") as output,
                    redirect_stdout(io.StringIO()),
                    redirect_stderr(io.StringIO()),
                ):
                    # Pin the device explicitly: an explicit path must narrow
                    # the match, never bypass the allowlist.
                    result = main(
                        [*command, "--confirm", "--device", str(receiver.path)]
                    )
                self.assertEqual(result, 1)
                feature.assert_not_called()
                output.assert_not_called()

    def test_the_product_id_allowlist_alone_refuses_every_service_write(self) -> None:
        receiver = _adversarial_receiver()
        with (
            patch("spade65.service.discover_devices", return_value=[receiver]),
            patch("spade65.service.send_feature_report") as feature,
            patch("spade65.service.send_output_report") as output,
        ):
            with self.assertRaisesRegex(RuntimeError, "no matching HID interface"):
                apply_profile(profile_template(), path=receiver.path)
            with self.assertRaisesRegex(RuntimeError, "no matching HID interface"):
                stream_colors({"esc": "#ff0000"}, path=receiver.path)
        feature.assert_not_called()
        output.assert_not_called()

    def test_the_product_id_allowlist_alone_refuses_every_gui_write(self) -> None:
        receiver = _adversarial_receiver()
        profile = profile_template()
        actions = [
            ("rgb", {"effect": "fixed"}),
            ("per-key", {"profile": profile}),
            ("profile", {"profile": profile, "confirmation": "APPLY PROFILE"}),
            ("stream", {"profile": profile}),
            ("debounce", {"milliseconds": 5}),
            ("sleep", {"light_off": 1, "hibernate": 3}),
            ("reset", {"confirmation": "RESET SPADE65"}),
        ]
        for action, payload in actions:
            with (
                self.subTest(action=action),
                patch("spade65.gui.discover_devices", return_value=[receiver]),
                patch("spade65.gui.send_feature_report") as feature,
                patch("spade65.gui.send_output_report") as output,
            ):
                with self.assertRaisesRegex(RuntimeError, "no matching HID interface"):
                    execute_action(
                        action, {"device": str(receiver.path), **payload}
                    )
                feature.assert_not_called()
                output.assert_not_called()


if __name__ == "__main__":
    unittest.main()
