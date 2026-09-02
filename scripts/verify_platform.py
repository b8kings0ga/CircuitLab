#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from _platform import COMPONENT_SCHEMA, HIL_SCHEMA, ComponentRegistry, HilEngine, generate_fixture


def sample_component() -> dict:
    return {
        "schema": COMPONENT_SCHEMA,
        "identity": {"assetId": "circuitlab.demo-sensor", "revision": "1.0.0", "manufacturer": "CircuitLab", "mpn": "DEMO-SENSOR", "level": "sensor-ic", "status": "SOFTWARE_VERIFIED"},
        "electrical": {"status": "DATASHEET_VERIFIED", "pins": [
            {"name": "VCC", "number": "1", "direction": "power"},
            {"name": "GND", "number": "2", "direction": "power"},
            {"name": "SDA", "number": "3", "direction": "bidirectional"},
        ]},
        "visual": {"appearance": "appearance.svg", "appearanceSha256": "a" * 64, "coordinateStatus": "FOOTPRINT_DERIVED", "anchors": [
            {"pin": "VCC", "x": 0.1, "y": 0.2, "status": "FOOTPRINT_DERIVED"},
            {"pin": "GND", "x": 0.1, "y": 0.8, "status": "FOOTPRINT_DERIVED"},
            {"pin": "SDA", "x": 0.9, "y": 0.5, "status": "FOOTPRINT_DERIVED"},
        ]},
        "physical": {"package": "demo", "footprint": "Demo:Sensor"},
        "evidence": {"sources": [{"type": "test-fixture", "url": "https://example.invalid/demo"}]},
    }


def sample_fixture() -> dict:
    return {
        "id": "demo-fixture", "revision": 1, "maximumVoltage": 3.3, "maximumCurrentMa": 250, "minimumSpacingMm": 2.54,
        "testPoints": [
            {"id": "TP1", "pinRef": "sensor:VCC", "visualAnchor": "sensor:VCC", "pad": "J1.1", "logicalNet": "VCC", "xMm": 10, "yMm": 10},
            {"id": "TP2", "pinRef": "sensor:GND", "visualAnchor": "sensor:GND", "pad": "J1.2", "logicalNet": "GND", "xMm": 10, "yMm": 15},
        ],
    }


def sample_hil() -> dict:
    return {
        "driver": "mock", "devices": {"dut": "demo-dut", "fixture": "demo-fixture"},
        "wiringLockSha256": "0" * 64, "assetLockSha256": "1" * 64, "firmwareSha256": "2" * 64,
        "plan": {"schema": HIL_SCHEMA, "id": "software-loop", "safety": {"maximumVoltage": 3.3, "maximumCurrentMa": 250}, "tests": [
            {"id": "gpio", "op": "gpio", "expected": True},
            {"id": "adc", "op": "adc", "sample": 1.65, "minimum": 1.5, "maximum": 1.8},
            {"id": "i2c", "op": "i2c", "expected": "0x68"},
            {"id": "spi", "op": "spi", "expected": "a55a"},
            {"id": "uart", "op": "uart", "expected": "OK"},
            {"id": "heartbeat", "op": "heartbeat", "expected": True},
        ]},
    }


def verify(root: Path) -> dict:
    registry = ComponentRegistry(root / "registry")
    installed = registry.install(sample_component())
    unchanged = registry.install(sample_component())
    calibrated = registry.calibrate("circuitlab.demo-sensor@1.0.0", "a" * 64, {
        "VCC": {"x": 0.12, "y": 0.2}, "GND": {"x": 0.12, "y": 0.8}, "SDA": {"x": 0.88, "y": 0.5},
    })
    procurement = registry.add_procurement_snapshot("circuitlab.demo-sensor@1.0.0", {"provider": "mouser", "sampledAt": "2026-09-02T00:00:00Z", "staleAfter": "2026-09-03T00:00:00Z", "payload": {"stock": 42, "currency": "USD"}})
    fixture = generate_fixture(sample_fixture(), root / "fixtures")
    engine = HilEngine(root / "hil", registry)
    prepared = engine.prepare(sample_hil())
    armed = engine.arm(prepared["jobId"], prepared["nonce"], True)
    report = engine.run(prepared["jobId"])
    voltage_rejected = False
    unsafe = sample_hil(); unsafe["plan"]["safety"]["maximumVoltage"] = 48
    try:
        engine.prepare(unsafe)
    except ValueError:
        voltage_rejected = True
    if report["state"] != "PASSED" or not voltage_rejected:
        raise AssertionError("CircuitLab software loop did not meet acceptance criteria")
    required_fixture = {"fixture-map.json", "test-points.csv", "pogo-plate.dxf", "fixture.kicad_pcb", "fixture-F_Cu.gbr", "fixture-PTH.drl", "bom.csv", "assembly.svg"}
    generated = {path.name for path in Path(fixture["directory"]).iterdir()}
    if not required_fixture <= generated:
        raise AssertionError(f"fixture package is incomplete: {sorted(required_fixture - generated)}")
    return {
        "status": "PASS", "dataRoot": str(root), "component": installed, "idempotentInstall": unchanged,
        "calibrated": calibrated["ref"], "procurement": procurement, "fixtureFiles": sorted(generated),
        "hil": {"prepared": prepared["state"], "armed": armed["state"], "final": report["state"], "reportSha256": report["reportSha256"]},
        "unsafe48VRejected": voltage_rejected,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the complete CircuitLab software-only development loop.")
    parser.add_argument("--data", type=Path)
    args = parser.parse_args()
    if args.data:
        print(json.dumps(verify(args.data.expanduser().resolve()), ensure_ascii=False, indent=2))
    else:
        with tempfile.TemporaryDirectory(prefix="circuitlab-verify-") as temporary:
            print(json.dumps(verify(Path(temporary)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
