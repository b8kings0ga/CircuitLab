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
        self.assertEqual(len(CATALOG), 75)
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

        imu = specs["adafruit.icm20948-4554"]
        package = package_for(imu, render(imu).encode("utf-8"))
        self.assertEqual(len(package["electrical"]["pins"]), 11)
        self.assertEqual(package["physical"]["additionalContacts"][0]["net"], "GND")

        haptic = specs["adafruit.drv2605l-2305-stemma-qt"]
        package = package_for(haptic, render(haptic).encode("utf-8"))
        self.assertEqual([contact["net"] for contact in package["physical"]["additionalContacts"]], ["MOTOR-", "MOTOR+"])

        touch = specs["adafruit.mpr121-1982-stemma-qt"]
        package = package_for(touch, render(touch).encode("utf-8"))
        self.assertEqual([pin["name"] for pin in touch["pins"][:12]], [f"ELEC{index}" for index in range(11, -1, -1)])
        self.assertEqual(len(touch["pins"]), 19)
        self.assertEqual(package["physical"]["additionalContacts"][0]["net"], "GND")

        mux = specs["adafruit.tca9548a-2717"]
        self.assertEqual(len(mux["pins"]), 24)
        self.assertEqual({pin["name"] for pin in mux["pins"] if pin["name"].startswith("SD")}, {f"SD{index}" for index in range(8)} | {"SDA"})
        self.assertEqual({pin["name"] for pin in mux["pins"] if pin["name"].startswith("SC")}, {f"SC{index}" for index in range(8)} | {"SCL"})

        microsd = specs["adafruit.microsd-254"]
        self.assertEqual([pin["name"] for pin in microsd["pins"]], ["5V", "3V", "GND", "CLK", "DO", "DI", "CS", "CD"])

        gps = specs["adafruit.ultimate-gps-pa1616s-746"]
        self.assertEqual([pin["name"] for pin in gps["pins"]], ["PPS", "VIN", "GND", "RX", "TX", "FIX", "VBAT", "EN", "3.3V"])

        thermocouple = specs["adafruit.max31855k-269-v2"]
        self.assertEqual([pin["name"] for pin in thermocouple["pins"][:2]], ["TC-", "TC+"])
        self.assertEqual(len(thermocouple["terminalBlocks"]), 1)

        dht = specs["adafruit.dht22-am2302-385"]
        self.assertEqual([pin["name"] for pin in dht["pins"]], ["VCC", "DATA", "NC", "GND"])
        self.assertEqual(dht["lifecycle"], "not-stocked")

    def test_common_resistors_leds_and_switches_preserve_documented_contacts(self) -> None:
        specs = {spec["assetId"]: spec for spec in CATALOG}
        resistor_bands = {
            "adafruit.resistor-cf-470r-2781": ["#f0cf38", "#7b4fa3", "#7a3b1e", "#c7a329"],
            "adafruit.resistor-cf-2k2-2782": ["#d71920", "#d71920", "#d71920", "#c7a329"],
            "adafruit.resistor-cf-4k7-2783": ["#f0cf38", "#7b4fa3", "#d71920", "#c7a329"],
            "adafruit.resistor-cf-22k-2785": ["#d71920", "#d71920", "#f28c28", "#c7a329"],
            "adafruit.resistor-cf-47k-2786": ["#f0cf38", "#7b4fa3", "#f28c28", "#c7a329"],
            "adafruit.resistor-cf-100k-2787": ["#7a3b1e", "#111111", "#f0cf38", "#c7a329"],
        }
        for asset_id, bands in resistor_bands.items():
            self.assertEqual(specs[asset_id]["bands"], bands)
            self.assertEqual([pin["name"] for pin in specs[asset_id]["pins"]], ["T1", "T2"])

        button = specs["adafruit.tactile-button-12mm-1119"]
        self.assertEqual([pin["name"] for pin in button["pins"]], ["1", "2", "3", "4"])
        self.assertEqual([pin["functions"][0] for pin in button["pins"]], ["contact-A", "contact-B", "contact-A", "contact-B"])

        slide = specs["adafruit.spdt-slide-switch-805"]
        self.assertEqual([pin["name"] for pin in slide["pins"]], ["A", "COM", "B"])
        self.assertEqual([pin["functions"][0] for pin in slide["pins"]], ["throw-A", "common", "throw-B"])

        for asset_id in (
            "adafruit.diffused-green-led-5mm-298",
            "adafruit.super-bright-yellow-led-5mm-2700",
            "adafruit.super-bright-white-led-5mm-754",
            "adafruit.ir333-a-led-940nm-387",
            "adafruit.uv-led-400nm-1793",
        ):
            self.assertEqual([pin["name"] for pin in specs[asset_id]["pins"]], ["A", "K"])
            self.assertEqual(specs[asset_id]["pins"][0]["functions"], ["anode", "long-lead"])
            self.assertEqual(specs[asset_id]["pins"][1]["functions"], ["cathode", "short-lead"])

        documented_discretes = {
            "adafruit.photoresistor-mj5516-161": ["T1", "T2"],
            "analog-devices.tmp36-to92-165": ["+VS", "VOUT", "GND"],
            "melexis.us5881lua-158": ["VDD", "GND", "OUT"],
            "tdk.ps1240-piezo-160": ["T1", "T2"],
            "adafruit.fast-vibration-switch-1766": ["T1", "T2"],
            "adafruit.tilt-ball-switch-173": ["T1", "T2"],
            "tt-electronics.p160-10k-pot-562": ["CCW", "W", "CW"],
            "adafruit.pn2222-to92-756": ["E", "B", "C"],
            "infineon.irlb8721pbf-355": ["G", "D", "S"],
            "onsemi.1n4001-755": ["A", "K"],
            "vishay.tsop38238-157": ["OUT", "GND", "VS"],
        }
        for asset_id, expected_pins in documented_discretes.items():
            self.assertEqual([pin["name"] for pin in specs[asset_id]["pins"]], expected_pins)

        mosfet = specs["infineon.irlb8721pbf-355"]
        self.assertIn("tab", mosfet["pins"][1]["functions"])
        diode = specs["onsemi.1n4001-755"]
        self.assertIn("banded-end", diode["pins"][1]["functions"])


if __name__ == "__main__":
    unittest.main()
