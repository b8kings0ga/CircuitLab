from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hardware_pipeline import capture_sources, official_url, validate_catalog  # noqa: E402


class HardwarePipelineTests(unittest.TestCase):
    def test_official_source_allowlist_is_fail_closed(self) -> None:
        self.assertTrue(official_url("https://learn.adafruit.com/example"))
        self.assertTrue(official_url("https://sub.files.seeedstudio.com/example"))
        self.assertFalse(official_url("http://learn.adafruit.com/example"))
        self.assertFalse(official_url("https://learn.adafruit.com.example.net/example"))

    def test_latest_catalog_has_complete_pin_anchor_coverage(self) -> None:
        rows = validate_catalog()
        self.assertEqual(len(rows), 42)
        self.assertTrue(all(row["status"] == "VALID" for row in rows))
        self.assertTrue(all(row["pins"] > 0 for row in rows))
        drawn = [row for row in rows if row["style"] == "circuitlab-ai-top-style/v1"]
        self.assertEqual(len(drawn), 6)
        self.assertEqual(sorted(row["pins"] for row in drawn), [28, 30, 40, 43, 44, 44])

    def test_offline_capture_never_opens_the_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch("urllib.request.urlopen") as urlopen:
            rows = capture_sources(Path(directory), online=False)
        urlopen.assert_not_called()
        self.assertTrue(rows)
        self.assertTrue(all(row["status"] == "NOT_CAPTURED_OFFLINE" for row in rows))


if __name__ == "__main__":
    unittest.main()
