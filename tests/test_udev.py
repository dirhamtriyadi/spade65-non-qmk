import re
import unittest
from pathlib import Path

from spade65.protocol import OBSERVED_PRODUCT_IDS, PRODUCT_IDS, VENDOR_ID

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "udev" / "99-spade65.rules"


def _rules() -> list[str]:
    return [
        line
        for line in RULES.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


class UdevRuleTests(unittest.TestCase):
    def test_the_rules_cover_exactly_the_identities_this_project_opens(self) -> None:
        # /dev/hidrawN is opened only on the report-send paths, and those are
        # gated to PRODUCT_IDS. Discovery and probe read descriptors through
        # world-readable sysfs and need no rule at all, so the read-only
        # receiver must NOT appear here: a rule for it would hand out device
        # access that nothing in this project ever asks for.
        covered = {
            int(match, 16)
            for line in _rules()
            for match in re.findall(r'ATTRS\{idProduct\}=="([0-9a-f]{4})"', line)
        }
        self.assertEqual(covered, set(PRODUCT_IDS))
        for read_only in set(OBSERVED_PRODUCT_IDS) - set(PRODUCT_IDS):
            with self.subTest(pid=f"0x{read_only:04x}"):
                self.assertNotIn(read_only, covered)

    def test_every_rule_is_scoped_to_this_vendor_and_hidraw(self) -> None:
        # Without both filters the rule would widen access to other hardware.
        self.assertTrue(_rules(), "the rule file is empty")
        for line in _rules():
            with self.subTest(line=line):
                self.assertIn(f'ATTRS{{idVendor}}=="{VENDOR_ID:04x}"', line)
                self.assertIn('SUBSYSTEM=="hidraw"', line)
                self.assertIn('KERNEL=="hidraw*"', line)

    def test_access_is_granted_the_same_way_for_every_identity(self) -> None:
        # uaccess covers the signed-in user on a logind system; the group and
        # mode keep it working where uaccess is unavailable.
        for line in _rules():
            with self.subTest(line=line):
                self.assertIn('TAG+="uaccess"', line)
                self.assertIn('GROUP="input"', line)
                self.assertIn('MODE="0660"', line)


if __name__ == "__main__":
    unittest.main()
