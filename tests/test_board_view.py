from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("generate_board_view", SCRIPTS / "generate_board_view.py")
board_view = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(board_view)


class BoardViewTests(unittest.TestCase):
    def test_xiao_spec_generates_svg_geometry_and_component_anchors(self) -> None:
        source = board_view.load_spec(ROOT / "assets" / "board-specs" / "seeed-xiao-esp32s3.json")
        with tempfile.TemporaryDirectory(prefix="circuitlab-board-view-") as temporary:
            output = Path(temporary)
            package, geometry = board_view.build(source, output)
            self.assertEqual(len(geometry["pins"]), 14)
            self.assertEqual(len(package["visual"]["anchors"]), 14)
            self.assertEqual(package["visual"]["coordinateStatus"], "OFFICIAL_DESIGN_DERIVED_UNVERIFIED")
            self.assertIn('data-pin="D0"', (output / "board.svg").read_text(encoding="utf-8"))
            self.assertEqual(json.loads((output / "board.json").read_text())["pins"]["GND"]["number"], "13")

    def test_duplicate_pin_names_fail_closed(self) -> None:
        source = json.loads((ROOT / "assets" / "board-specs" / "seeed-xiao-esp32s3.json").read_text())
        source["pins"][1]["name"] = source["pins"][0]["name"]
        with tempfile.TemporaryDirectory(prefix="circuitlab-bad-board-") as temporary:
            path = Path(temporary) / "spec.json"
            path.write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError, "duplicate pin"):
                board_view.load_spec(path)


if __name__ == "__main__":
    unittest.main()
