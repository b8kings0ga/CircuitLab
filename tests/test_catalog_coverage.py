from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from catalog_coverage import coverage  # noqa: E402


class CatalogCoverageTests(unittest.TestCase):
    def test_reports_truthful_progress_to_one_hundred(self) -> None:
        report = coverage(ROOT / "assets" / "catalog", 100)
        self.assertEqual(report["verified"], 100)
        self.assertEqual(report["remaining"], 0)
        self.assertTrue(report["complete"])
        self.assertEqual(report["families"]["passive/resistor"], 11)
        self.assertEqual(report["families"]["control/button-switch"], 7)
        self.assertEqual(report["families"]["indicator/led"], 7)
        self.assertEqual(report["families"]["sensor/environment"], 5)
        self.assertEqual(report["families"]["sensor/general"], 12)
        self.assertEqual(report["families"]["sensor/light"], 7)
        self.assertEqual(report["families"]["sensor/magnetic"], 2)
        self.assertEqual(report["families"]["support/support-ic"], 23)


if __name__ == "__main__":
    unittest.main()
