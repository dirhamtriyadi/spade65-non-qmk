import json
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

if not sys.platform.startswith("linux"):  # pragma: no cover - Linux only
    raise unittest.SkipTest("BlueZ probing is Linux-only")

from spade65.hidraw import BATTERY_LEVEL_UUID, bluez_battery_probe

ADDRESS = "AA:BB:CC:DD:EE:FF"
DEVICE = "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"
CHAR = f"{DEVICE}/service0010/char0011"
OTHER_CHAR = f"{DEVICE}/service0010/char0013"

TREE = "\n".join(
    [
        "/",
        "/org",
        "/org/bluez",
        "/org/bluez/hci0",
        "/org/bluez/hci0/dev_11_22_33_44_55_66",
        DEVICE,
        f"{DEVICE}/service0010",
        OTHER_CHAR,
        CHAR,
        "",
    ]
)


def _ok(stdout: str) -> SimpleNamespace:
    return SimpleNamespace(returncode=0, stdout=stdout, stderr="")


def _fail(stderr: str = "Call failed") -> SimpleNamespace:
    # busctl prints a diagnostic on stdout and still exits non-zero, so a
    # reader that trusts stdout alone would parse the failure as a value.
    return SimpleNamespace(
        returncode=1, stdout='{"type":"y","data":7}', stderr=stderr
    )


def _responder(**overrides):
    """Answer each busctl invocation the probe is allowed to make."""

    def run(command, **_kwargs):
        if "tree" in command:
            return _ok(overrides.get("tree", TREE))
        if "get-property" in command:
            path, interface, member = command[-3], command[-2], command[-1]
            if member == "UUID":
                uuid = BATTERY_LEVEL_UUID if path == CHAR else "00002a00-0000-1000-8000-00805f9b34fb"
                return _ok(json.dumps({"type": "s", "data": uuid}))
            if member == "Percentage":
                if "cached" in overrides and overrides["cached"] is None:
                    return _fail("Unknown interface")
                return _ok(json.dumps({"type": "y", "data": overrides.get("cached", 100)}))
        if "call" in command:
            if "fresh" in overrides and overrides["fresh"] is None:
                return _fail("Not connected")
            return _ok(json.dumps({"type": "ay", "data": [overrides.get("fresh", 62)]}))
        raise AssertionError(f"unexpected busctl call: {command}")

    return run


class BluezProbeTests(unittest.TestCase):
    def _probe(self, **overrides):
        with (
            patch("spade65.hidraw.shutil.which", return_value="/usr/bin/busctl"),
            patch("spade65.hidraw.subprocess.run", side_effect=_responder(**overrides)),
        ):
            return bluez_battery_probe(ADDRESS)

    def test_it_reports_the_cached_property_and_a_fresh_read_separately(self) -> None:
        # The whole point is the comparison: BlueZ caches the last value the
        # keyboard notified, while ReadValue asks the keyboard now.
        result = self._probe(cached=100, fresh=62)
        self.assertEqual(result["cached_percent"], 100)
        self.assertEqual(result["fresh_percent"], 62)
        self.assertEqual(result["characteristic"], CHAR)
        self.assertTrue(result["differs"])

    def test_matching_values_are_not_reported_as_a_difference(self) -> None:
        result = self._probe(cached=62, fresh=62)
        self.assertFalse(result["differs"])

    def test_it_picks_the_battery_characteristic_and_not_a_neighbour(self) -> None:
        # Several characteristics live under the same device; only 0x2A19 is
        # the battery level.
        self.assertEqual(self._probe()["characteristic"], CHAR)

    def test_the_device_is_matched_by_its_own_path_not_a_child(self) -> None:
        # Every characteristic path contains the device path as a prefix, so a
        # substring match would happily pick a service object as the device.
        # Listing a child first makes that mistake visible.
        shuffled = "\n".join(
            [
                "/org/bluez/hci0",
                f"{DEVICE}/service0010",
                CHAR,
                DEVICE,
                "",
            ]
        )

        def run(command, **kwargs):
            if "tree" in command:
                return _ok(shuffled)
            return _responder()(command, **kwargs)

        with (
            patch("spade65.hidraw.shutil.which", return_value="/usr/bin/busctl"),
            patch("spade65.hidraw.subprocess.run", side_effect=run),
        ):
            result = bluez_battery_probe(ADDRESS)
        self.assertEqual(result["device_path"], DEVICE)
        self.assertEqual(result["characteristic"], CHAR)

    def test_an_unknown_address_finds_no_device(self) -> None:
        with (
            patch("spade65.hidraw.shutil.which", return_value="/usr/bin/busctl"),
            patch("spade65.hidraw.subprocess.run", side_effect=_responder()),
        ):
            result = bluez_battery_probe("99:99:99:99:99:99")
        self.assertIsNone(result["device_path"])
        self.assertIsNone(result["cached_percent"])
        self.assertIsNone(result["fresh_percent"])
        self.assertIn("no BlueZ device", result["note"])

    def test_a_missing_battery_interface_is_not_an_error(self) -> None:
        # A keyboard that never notified has no Battery1 interface at all.
        result = self._probe(cached=None)
        self.assertIsNone(result["cached_percent"])
        self.assertEqual(result["fresh_percent"], 62)
        self.assertFalse(result["differs"])

    def test_a_refused_read_is_not_an_error(self) -> None:
        result = self._probe(fresh=None)
        self.assertEqual(result["cached_percent"], 100)
        self.assertIsNone(result["fresh_percent"])
        self.assertFalse(result["differs"])

    def test_a_multi_byte_response_uses_the_first_byte(self) -> None:
        # The characteristic is one byte, but a padded or batched reply must
        # not be read from the wrong end.
        def run(command, **kwargs):
            if "call" in command:
                return _ok(json.dumps({"type": "ay", "data": [41, 99, 7]}))
            return _responder()(command, **kwargs)

        with (
            patch("spade65.hidraw.shutil.which", return_value="/usr/bin/busctl"),
            patch("spade65.hidraw.subprocess.run", side_effect=run),
        ):
            result = bluez_battery_probe(ADDRESS)
        self.assertEqual(result["fresh_percent"], 41)

    def test_it_never_reports_a_percentage_outside_the_range(self) -> None:
        for bogus in (101, 255, -1):
            with self.subTest(value=bogus):
                self.assertIsNone(self._probe(fresh=bogus)["fresh_percent"])

    def test_without_busctl_it_says_so_instead_of_failing(self) -> None:
        with patch("spade65.hidraw.shutil.which", return_value=None):
            result = bluez_battery_probe(ADDRESS)
        self.assertIsNone(result["cached_percent"])
        self.assertIn("busctl", result["note"])

    def test_no_address_is_refused_before_any_subprocess_runs(self) -> None:
        with patch("spade65.hidraw.subprocess.run") as run:
            result = bluez_battery_probe(None)
        run.assert_not_called()
        self.assertIsNone(result["device_path"])

    def test_it_never_writes_to_the_device(self) -> None:
        # ReadValue is a read. Nothing here may reach a write method.
        seen: list[list[str]] = []

        def record(command, **kwargs):
            seen.append(command)
            return _responder()(command, **kwargs)

        with (
            patch("spade65.hidraw.shutil.which", return_value="/usr/bin/busctl"),
            patch("spade65.hidraw.subprocess.run", side_effect=record),
        ):
            bluez_battery_probe(ADDRESS)
        self.assertTrue(seen)
        for command in seen:
            joined = " ".join(command)
            self.assertNotIn("WriteValue", joined)
            self.assertNotIn("set-property", joined)


if __name__ == "__main__":
    unittest.main()
