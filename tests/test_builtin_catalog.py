from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from _platform import component_family, validate_component  # noqa: E402
from generate_builtin_catalog import CATALOG, STYLE, package_for, render  # noqa: E402


class BuiltinCatalogTests(unittest.TestCase):
    def test_catalog_vectors_have_pins_evidence_and_valid_packages(self) -> None:
        self.assertEqual(len(CATALOG), 41)
        for spec in CATALOG:
            svg = render(spec).encode("utf-8")
            package = validate_component(package_for(spec, svg))
            self.assertGreater(len(svg), 500)
            self.assertTrue(package["electrical"]["pins"])
            self.assertEqual(len(package["electrical"]["pins"]), len(package["visual"]["anchors"]))
            self.assertTrue(package["evidence"]["sources"][0]["url"].startswith("https://"))
            self.assertEqual(package["visual"]["style"], STYLE["schema"])

    def test_requested_hardware_categories_are_present(self) -> None:
        categories = {component_family(package_for(spec, render(spec).encode("utf-8"))) for spec in CATALOG}
        self.assertIn(("board", "single-board-computer"), categories)
        self.assertIn(("display", "display"), categories)
        for sensor_type in ("distance", "magnetic", "gas", "sound", "light", "environment", "motion-imu", "current"):
            self.assertIn(("sensor", sensor_type), categories)
        self.assertIn(("passive", "resistor"), categories)
        self.assertIn(("control", "button-switch"), categories)
        self.assertIn(("indicator", "led"), categories)

    def test_layout_exceptions_preserve_canonical_pins_and_duplicate_contacts(self) -> None:
        specs = {spec["assetId"]: spec for spec in CATALOG}
        rtc = specs["adafruit.pcf8523-3295"]
        self.assertEqual([pin["name"] for pin in rtc["pins"]], ["VCC", "GND", "SDA", "SCL", "SQW"])
        self.assertTrue(all(pin["side"] == "left" for pin in rtc["pins"]))
        self.assertEqual(len(rtc["mountingHoles"]), 2)

        sensor = specs["adafruit.ina260-4226"]
        package = package_for(sensor, render(sensor).encode("utf-8"))
        self.assertEqual([pin["name"] for pin in sensor["pins"]], ["VCC", "GND", "SCL", "SDA", "ALERT", "VBUS", "VIN+", "VIN-"])
        self.assertTrue(all(pin["side"] == "left" for pin in sensor["pins"]))
        self.assertEqual([contact["net"] for contact in package["physical"]["additionalContacts"]], ["VIN+", "VIN-"])
        self.assertEqual(len(package["electrical"]["pins"]), len(package["visual"]["anchors"]))


if __name__ == "__main__":
    unittest.main()
