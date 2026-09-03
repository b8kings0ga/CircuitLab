from __future__ import annotations

import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock


CORE = Path(__file__).resolve().parents[1] / "assets" / "template" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from circuitlab_platform import COMPONENT_SCHEMA, HIL_SCHEMA, ComponentRegistry, HilEngine, component_family, generate_fixture


def component() -> dict:
    return {
        "schema": COMPONENT_SCHEMA,
        "identity": {"assetId": "circuitlab.test-chip", "revision": "1.0.0", "manufacturer": "CircuitLab", "mpn": "TEST-CHIP", "level": "microcontroller", "status": "SOFTWARE_VERIFIED"},
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
        with mock.patch("circuitlab_platform.time.strftime", side_effect=["2026-09-03T00:00:00Z", "2026-09-03T00:00:01Z"]):
            self.assertEqual(self.registry.install(component())["status"], "installed")
            self.assertEqual(self.registry.install(component())["status"], "unchanged")
        self.assertEqual(self.registry.list("TEST-CHIP", scope="chips")[0]["ref"], "circuitlab.test-chip@1.0.0")
        changed = component(); changed["identity"]["mpn"] = "OTHER"
        with self.assertRaisesRegex(ValueError, "immutable component revision conflicts"):
            self.registry.install(changed)

    def test_visual_anchor_cannot_invent_electrical_pin(self) -> None:
        invalid = component(); invalid["visual"]["anchors"].append({"pin": "NOT_A_PIN", "x": 0.5, "y": 0.5})
        with self.assertRaisesRegex(ValueError, "unknown electrical pin"):
            self.registry.install(invalid)

    def test_component_visual_files_are_allowlisted(self) -> None:
        self.registry.install(component(), {"appearance.webp": b"image", "board.json": b"{}", "secret.txt": b"secret"})
        package = self.registry.get("circuitlab.test-chip@1.0.0")
        package["visual"]["appearance"] = "appearance.webp"
        package["visual"]["geometry"] = "board.json"
        # The immutable package cannot be rewritten, so install the file-bearing visual as a new revision.
        package.pop("procurement", None); package.pop("packageSha256", None)
        package["identity"]["revision"] = "1.0.1"
        self.registry.install(package, {"appearance.webp": b"image", "board.json": b"{}", "secret.txt": b"secret"})
        self.assertEqual(self.registry.visual_file("circuitlab.test-chip@1.0.1", "appearance.webp").read_bytes(), b"image")
        self.assertEqual(self.registry.visual_file("circuitlab.test-chip@1.0.1", "board.json").read_bytes(), b"{}")
        with self.assertRaises(KeyError):
            self.registry.visual_file("circuitlab.test-chip@1.0.1", "secret.txt")

    def test_component_install_rejects_partial_or_reserved_files_atomically(self) -> None:
        reference_dir = self.root / "registry" / "components" / "circuitlab.test-chip" / "1.0.0"
        with self.assertRaisesRegex(ValueError, "must contain bytes"):
            self.registry.install(component(), {"top.svg": "not-bytes"})  # type: ignore[dict-item]
        self.assertFalse(reference_dir.exists())
        with self.assertRaisesRegex(ValueError, "unsafe component file path"):
            self.registry.install(component(), {"component-package.json": b"{}"})
        self.assertFalse(reference_dir.exists())

    def test_chip_scope_hides_boards_and_returns_latest_revision(self) -> None:
        self.registry.install(component())
        next_chip = component(); next_chip["identity"]["revision"] = "1.1.0"
        self.registry.install(next_chip)
        board = component(); board["identity"].update({"assetId": "circuitlab.board", "mpn": "DEV-BOARD", "level": "development-board"})
        board["physical"]["package"] = "assembled-board"
        self.registry.install(board)
        visible = self.registry.list(scope="chips", latest_only=True)
        self.assertEqual([row["ref"] for row in visible], ["circuitlab.test-chip@1.1.0"])
        self.assertEqual(len(self.registry.list(scope="all")), 3)

    def test_latest_revision_uses_numeric_ordering(self) -> None:
        older = component(); older["identity"]["revision"] = "1.9.0"
        newer = component(); newer["identity"]["revision"] = "1.10.0"
        self.registry.install(newer)
        self.registry.install(older)
        visible = self.registry.list(scope="chips", latest_only=True)
        self.assertEqual([row["ref"] for row in visible], ["circuitlab.test-chip@1.10.0"])

    def test_normal_acquisition_rejects_non_chip_package(self) -> None:
        board = component(); board["identity"].update({"assetId": "circuitlab.board", "mpn": "DEV-BOARD", "level": "development-board"})
        board["physical"]["package"] = "assembled-board"
        with self.assertRaisesRegex(ValueError, "chip-only acquisition rejected"):
            self.registry.install_chip(board)

    def test_sensor_and_controller_taxonomy(self) -> None:
        controller = component()
        self.assertEqual(component_family(controller), ("controller", "mcu-soc"))
        environment = component(); environment["identity"]["level"] = "environmental-sensor"
        self.assertEqual(component_family(environment), ("sensor", "environment"))
        environment["identity"]["level"] = "environmental-sensor-module"
        self.assertEqual(component_family(environment), ("sensor", "environment"))
        motion = component(); motion["identity"]["level"] = "six-axis-imu"
        self.assertEqual(component_family(motion), ("sensor", "motion-imu"))
        current = component(); current["identity"]["level"] = "isolated-current-sensor"
        self.assertEqual(component_family(current), ("sensor", "current"))

    def test_board_display_and_sensor_module_taxonomy(self) -> None:
        def family(level: str) -> tuple[str, str]:
            return component_family({"identity": {"level": level}})

        self.assertEqual(family("development-board"), ("board", "development-board"))
        self.assertEqual(family("linux-single-board-computer"), ("board", "single-board-computer"))
        self.assertEqual(family("oled-display-module"), ("display", "display"))
        self.assertEqual(family("distance-sensor-module"), ("sensor", "distance"))
        self.assertEqual(family("magnetometer-module"), ("sensor", "magnetic"))
        self.assertEqual(family("voc-gas-sensor-module"), ("sensor", "gas"))
        self.assertEqual(family("digital-microphone-module"), ("sensor", "sound"))
        self.assertEqual(family("ambient-light-sensor-module"), ("sensor", "light"))
        self.assertEqual(family("temperature-humidity-sensor-module"), ("sensor", "environment"))
        self.assertEqual(family("through-hole-resistor"), ("passive", "resistor"))
        self.assertEqual(family("momentary-button"), ("control", "button-switch"))
        self.assertEqual(family("indicator-led"), ("indicator", "led"))

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

    def test_fixture_rejects_invalid_revision_current_and_export_text(self) -> None:
        base = {"id": "strict", "testPoints": [{"id": "TP1", "pinRef": "a:1", "visualAnchor": "a:1", "pad": "J1.1", "logicalNet": "A", "xMm": 1, "yMm": 1}]}
        for field, value, message in (
            ("revision", 0, "positive integer"),
            ("maximumCurrentMa", -1, "must be positive"),
            ("maximumVoltage", True, "finite number"),
        ):
            request = {**base, field: value}
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, message):
                generate_fixture(request, self.root / "fixtures")
        injected = {**base, "testPoints": [{**base["testPoints"][0], "logicalNet": 'GND"\n(net 999 "INJECTED")'}]}
        with self.assertRaisesRegex(ValueError, "unsafe for manufacturing exports"):
            generate_fixture(injected, self.root / "fixtures")

    def test_fixture_kicad_reuses_one_net_id_for_shared_logical_net(self) -> None:
        result = generate_fixture({
            "id": "shared-net", "testPoints": [
                {"id": "TP1", "pinRef": "a:GND", "visualAnchor": "a:GND", "pad": "J1.1", "logicalNet": "GND", "xMm": 1, "yMm": 1},
                {"id": "TP2", "pinRef": "b:GND", "visualAnchor": "b:GND", "pad": "J1.2", "logicalNet": "GND", "xMm": 1, "yMm": 5},
            ],
        }, self.root / "fixtures")
        board = (Path(result["directory"]) / "fixture.kicad_pcb").read_text(encoding="utf-8")
        declarations = [line for line in board.splitlines() if line.startswith("  (net ")]
        self.assertEqual(declarations, ['  (net 1 "GND")'])
        self.assertEqual(board.count('(net 1 "GND")'), 3)

    def test_fixture_publish_is_atomic_on_generation_failure(self) -> None:
        request = {"id": "atomic", "revision": 2, "testPoints": [{"id": "TP1", "pinRef": "a:1", "visualAnchor": "a:1", "pad": "J1.1", "logicalNet": "A", "xMm": 1, "yMm": 1}]}
        with mock.patch("circuitlab_platform.atomic_json", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                generate_fixture(request, self.root / "fixtures")
        fixture_root = self.root / "fixtures" / "atomic"
        self.assertFalse((fixture_root / "v2").exists())
        self.assertEqual(list(fixture_root.glob(".*.tmp")), [])

    def test_hil_requires_arm_and_retains_pass_report(self) -> None:
        engine = HilEngine(self.root / "hil", self.registry)
        prepared = engine.prepare(hil_request())
        with self.assertRaisesRegex(ValueError, "cannot run"):
            engine.run(prepared["jobId"])
        engine.arm(prepared["jobId"], prepared["nonce"], True)
        report = engine.run(prepared["jobId"])
        self.assertEqual(report["state"], "PASSED")
        self.assertEqual(report["physicalStatus"], "PHYSICAL_UNVERIFIED")

    def test_hil_requires_real_sha256_bindings(self) -> None:
        engine = HilEngine(self.root / "hil", self.registry)
        request = hil_request()
        request["assetLockSha256"] = "not-a-digest"
        with self.assertRaisesRegex(ValueError, "assetLockSha256.*64-character"):
            engine.prepare(request)
        request = hil_request()
        request["firmwareSha256"] = "A" * 64
        prepared = engine.prepare(request)
        self.assertEqual(prepared["binding"]["firmwareSha256"], "a" * 64)

    def test_hil_plan_rejects_ambiguous_test_evidence(self) -> None:
        engine = HilEngine(self.root / "hil", self.registry)
        duplicate = hil_request()
        duplicate["plan"]["tests"][1]["id"] = "gpio"
        with self.assertRaisesRegex(ValueError, "duplicate HIL test id"):
            engine.prepare(duplicate)
        policy = hil_request()
        policy["plan"]["tests"][0]["onFailure"] = "maybe"
        with self.assertRaisesRegex(ValueError, "invalid onFailure"):
            engine.prepare(policy)
        bounds = hil_request()
        bounds["plan"]["tests"][1].update({"minimum": 2, "maximum": 1})
        with self.assertRaisesRegex(ValueError, "minimum cannot exceed maximum"):
            engine.prepare(bounds)
        non_finite = hil_request()
        non_finite["plan"]["safety"]["maximumCurrentMa"] = float("nan")
        with self.assertRaisesRegex(ValueError, "HIL maximum current must be a finite number"):
            engine.prepare(non_finite)
        malformed = hil_request()
        malformed["plan"]["tests"][1]["minimum"] = "not-a-number"
        with self.assertRaisesRegex(ValueError, "minimum must be a finite number"):
            engine.prepare(malformed)

    def test_hil_ttl_is_explicit_and_bounded(self) -> None:
        engine = HilEngine(self.root / "hil", self.registry)
        for invalid in (0, 601, 1.5, True):
            request = hil_request()
            request["ttlSeconds"] = invalid
            with self.subTest(ttl=invalid), self.assertRaisesRegex(ValueError, "ttlSeconds"):
                engine.prepare(request)
        request = hil_request()
        request["ttlSeconds"] = 30
        with mock.patch("circuitlab_platform.time.time", return_value=1000):
            prepared = engine.prepare(request)
        self.assertEqual(prepared["expiresAtEpoch"], 1030)

    def test_abort_during_run_cannot_be_overwritten_by_pass(self) -> None:
        engine = HilEngine(self.root / "hil", self.registry)
        prepared = engine.prepare(hil_request())
        engine.arm(prepared["jobId"], prepared["nonce"], True)
        entered = threading.Event()
        release = threading.Event()
        reports = []

        def delayed_execute(_driver, test, sequence):
            entered.set()
            self.assertTrue(release.wait(timeout=2))
            return {"sequence": sequence, "value": test.get("sample", test.get("expected", True)), "waveform": []}

        with mock.patch("circuitlab_platform.MockFixtureDriver.execute", autospec=True, side_effect=delayed_execute):
            worker = threading.Thread(target=lambda: reports.append(engine.run(prepared["jobId"])))
            worker.start()
            self.assertTrue(entered.wait(timeout=2))
            self.assertEqual(engine.abort(prepared["jobId"])["state"], "ABORTED")
            release.set()
            worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(reports[0]["state"], "ABORTED")
        self.assertEqual(engine.status(prepared["jobId"])["state"], "ABORTED")

    def test_hil_fault_and_abort_are_terminal(self) -> None:
        engine = HilEngine(self.root / "hil", self.registry)
        failed = engine.prepare(hil_request())
        engine.arm(failed["jobId"], failed["nonce"], True)
        self.assertEqual(engine.run(failed["jobId"], {"fault": "gpio"})["state"], "FAILED")
        aborted = engine.prepare(hil_request())
        self.assertEqual(engine.abort(aborted["jobId"])["state"], "ABORTED")


if __name__ == "__main__":
    unittest.main()
