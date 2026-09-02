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
        self.assertEqual(report["verified"], 42)
        self.assertEqual(report["remaining"], 58)
        self.assertFalse(report["complete"])
        self.assertEqual(report["families"]["passive/resistor"], 4)
        self.assertEqual(report["families"]["control/button-switch"], 1)
        self.assertEqual(report["families"]["indicator/led"], 2)


if __name__ == "__main__":
    unittest.main()
