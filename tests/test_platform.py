from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


CORE = Path(__file__).resolve().parents[1] / "assets" / "template" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from circuitlab_platform import COMPONENT_SCHEMA, HIL_SCHEMA, ComponentRegistry, HilEngine, generate_fixture


def component() -> dict:
    return {
        "schema": COMPONENT_SCHEMA,
        "identity": {"assetId": "circuitlab.test-board", "revision": "1.0.0", "manufacturer": "CircuitLab", "mpn": "TEST-BOARD", "level": "development-board", "status": "SOFTWARE_VERIFIED"},
        "electrical": {"status": "VERIFIED", "pins": [{"name": "D0", "number": "1", "direction": "bidirectional"}, {"name": "GND", "number": "2", "direction": "power"}]},
        "visual": {"appearanceSha256": "a" * 64, "coordinateStatus": "FOOTPRINT_DERIVED", "anchors": [{"pin": "D0", "x": 0.2, "y": 0.2}, {"pin": "GND", "x": 0.2, "y": 0.8}]},
        "physical": {"package": "test"},
        "evidence": {"capturedAt": "2026-09-02T00:00:00Z", "sources": []},
    }


def hil_request() -> dict:
    return {
        "driver": "mock", "devices": {"dut": "test-dut", "fixture": "test-fixture"},
        "wiringLockSha256": "0" * 64, "assetLockSha256": "1" * 64, "firmwareSha256": "2" * 64,
        "plan": {"schema": HIL_SCHEMA, "id": "test", "safety": {"maximumVoltage": 3.3, "maximumCurrentMa": 250}, "tests": [
            {"id": "gpio", "op": "gpio", "expected": True},
            {"id": "adc", "op": "adc", "sample": 1.65, "minimum": 1.5, "maximum": 1.8},
        ]},
    }


class CircuitLabPlatformTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="circuitlab-test-")
        self.root = Path(self.temporary.name)
        self.registry = ComponentRegistry(self.root / "registry")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_component_revision_is_immutable_and_searchable(self) -> None:
        self.assertEqual(self.registry.install(component())["status"], "installed")
        self.assertEqual(self.registry.install(component())["status"], "unchanged")
        self.assertEqual(self.registry.list("TEST-BOARD")[0]["ref"], "circuitlab.test-board@1.0.0")
        changed = component(); changed["identity"]["mpn"] = "OTHER"
        with self.assertRaisesRegex(ValueError, "immutable component revision conflicts"):
            self.registry.install(changed)

    def test_visual_anchor_cannot_invent_electrical_pin(self) -> None:
        invalid = component(); invalid["visual"]["anchors"].append({"pin": "NOT_A_PIN", "x": 0.5, "y": 0.5})
        with self.assertRaisesRegex(ValueError, "unknown electrical pin"):
            self.registry.install(invalid)

    def test_fixture_emits_complete_unverified_package(self) -> None:
        result = generate_fixture({
            "id": "reference", "revision": 1, "maximumVoltage": 3.3, "minimumSpacingMm": 2.54,
            "testPoints": [
                {"id": "TP1", "pinRef": "dev:D0", "visualAnchor": "dev:D0", "pad": "J1.1", "logicalNet": "D0", "xMm": 10, "yMm": 10},
                {"id": "TP2", "pinRef": "dev:GND", "visualAnchor": "dev:GND", "pad": "J1.7", "logicalNet": "GND", "xMm": 10, "yMm": 15},
            ],
        }, self.root / "fixtures")
        self.assertEqual(result["status"], "GENERATED_UNVERIFIED_DO_NOT_FABRICATE")
        files = {path.name for path in Path(result["directory"]).iterdir()}
        self.assertTrue({"fixture-map.json", "fixture.kicad_pcb", "fixture-F_Cu.gbr", "fixture-PTH.drl"} <= files)

    def test_fixture_rejects_voltage(self) -> None:
        request = {"id": "unsafe", "maximumVoltage": 48, "testPoints": [{"id": "TP1", "pinRef": "a:1", "visualAnchor": "a:1", "pad": "1", "logicalNet": "A", "xMm": 1, "yMm": 1}]}
        with self.assertRaisesRegex(ValueError, "maximumVoltage"):
            generate_fixture(request, self.root / "fixtures")

    def test_hil_requires_arm_and_retains_pass_report(self) -> None:
        engine = HilEngine(self.root / "hil", self.registry)
        prepared = engine.prepare(hil_request())
        with self.assertRaisesRegex(ValueError, "cannot run"):
            engine.run(prepared["jobId"])
        engine.arm(prepared["jobId"], prepared["nonce"], True)
        report = engine.run(prepared["jobId"])
        self.assertEqual(report["state"], "PASSED")
        self.assertEqual(report["physicalStatus"], "PHYSICAL_UNVERIFIED")

    def test_hil_fault_and_abort_are_terminal(self) -> None:
        engine = HilEngine(self.root / "hil", self.registry)
        failed = engine.prepare(hil_request())
        engine.arm(failed["jobId"], failed["nonce"], True)
        self.assertEqual(engine.run(failed["jobId"], {"fault": "gpio"})["state"], "FAILED")
        aborted = engine.prepare(hil_request())
        self.assertEqual(engine.abort(aborted["jobId"])["state"], "ABORTED")


if __name__ == "__main__":
    unittest.main()
