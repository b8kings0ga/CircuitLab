#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import tempfile
from pathlib import Path
from typing import Any

try:
    from _platform import COMPONENT_SCHEMA, HIL_SCHEMA, ComponentRegistry, HilEngine, generate_fixture, sha256_json
except ModuleNotFoundError:  # Imported as scripts.verify_e2e_scenarios by unittest.
    from scripts._platform import COMPONENT_SCHEMA, HIL_SCHEMA, ComponentRegistry, HilEngine, generate_fixture, sha256_json


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "assets" / "catalog"
SCENARIOS = ROOT / "examples" / "e2e-circuits"
SCHEMA = "circuitlab-e2e-scenario/v1"
REQUIRED_FIXTURE_FILES = {
    "fixture-map.json", "test-points.csv", "pogo-plate.dxf", "fixture.kicad_pcb",
    "fixture-F_Cu.gbr", "fixture-PTH.drl", "bom.csv", "assembly.svg",
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _component_path(reference: str) -> Path:
    if "@" not in reference:
        raise ValueError(f"component reference must use assetId@revision: {reference}")
    asset_id, revision = reference.rsplit("@", 1)
    path = CATALOG / asset_id / revision / "component-package.json"
    if not path.is_file():
        raise ValueError(f"catalog component does not exist: {reference}")
    return path


def _endpoint_parts(endpoint: str) -> tuple[str, str]:
    if not isinstance(endpoint, str) or ":" not in endpoint:
        raise ValueError(f"endpoint must use alias:pin: {endpoint!r}")
    alias, pin = endpoint.split(":", 1)
    if not alias or not pin:
        raise ValueError(f"endpoint must use alias:pin: {endpoint!r}")
    return alias, pin


def validate_scenario(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise ValueError(f"scenario schema must be {SCHEMA}")
    if not isinstance(value.get("id"), str) or not value["id"]:
        raise ValueError("scenario id is required")
    if value.get("verificationStatus") != "SOFTWARE_VERIFIED_PHYSICAL_UNVERIFIED":
        raise ValueError("scenario must retain SOFTWARE_VERIFIED_PHYSICAL_UNVERIFIED status")

    components = value.get("components")
    if not isinstance(components, list) or not components:
        raise ValueError("scenario requires components")
    packages: dict[str, dict[str, Any]] = {}
    paths: dict[str, Path] = {}
    references: set[str] = set()
    for component in components:
        if not isinstance(component, dict):
            raise ValueError("scenario component must be an object")
        alias, reference = component.get("alias"), component.get("ref")
        if not isinstance(alias, str) or not alias or alias in packages:
            raise ValueError(f"component alias must be unique: {alias!r}")
        if not isinstance(reference, str) or reference in references:
            raise ValueError(f"component reference must be unique: {reference!r}")
        path = _component_path(reference)
        package = _load_json(path)
        if package.get("schema") != COMPONENT_SCHEMA:
            raise ValueError(f"catalog component has wrong schema: {reference}")
        expected = f"{package['identity']['assetId']}@{package['identity']['revision']}"
        if reference != expected:
            raise ValueError(f"catalog identity does not match reference: {reference}")
        packages[alias], paths[alias] = package, path
        references.add(reference)

    nets = value.get("nets")
    if not isinstance(nets, list) or not nets:
        raise ValueError("scenario requires nets")
    net_names: set[str] = set()
    endpoint_to_net: dict[str, str] = {}
    for net in nets:
        if not isinstance(net, dict) or not isinstance(net.get("name"), str) or not net["name"]:
            raise ValueError("each net requires a name")
        name = net["name"]
        if name in net_names:
            raise ValueError(f"duplicate net: {name}")
        net_names.add(name)
        endpoints = net.get("endpoints")
        if not isinstance(endpoints, list) or not endpoints:
            raise ValueError(f"net {name} requires endpoints")
        for endpoint in endpoints:
            alias, pin = _endpoint_parts(endpoint)
            if alias not in packages:
                raise ValueError(f"endpoint references unknown component alias: {endpoint}")
            pins = {item["name"] for item in packages[alias].get("electrical", {}).get("pins", [])}
            if pin not in pins:
                raise ValueError(f"endpoint references unknown pin: {endpoint}")
            if endpoint in endpoint_to_net:
                raise ValueError(f"endpoint {endpoint} appears in both {endpoint_to_net[endpoint]} and {name}")
            endpoint_to_net[endpoint] = name

    fixture = value.get("fixture")
    if not isinstance(fixture, dict):
        raise ValueError("scenario requires a fixture")
    for point in fixture.get("testPoints", []):
        if not isinstance(point, dict):
            raise ValueError("fixture test point must be an object")
        pin_ref, visual_anchor, logical_net = point.get("pinRef"), point.get("visualAnchor"), point.get("logicalNet")
        if pin_ref != visual_anchor:
            raise ValueError(f"test point {point.get('id')} pinRef and visualAnchor must identify the same contact")
        if pin_ref not in endpoint_to_net:
            raise ValueError(f"test point references an endpoint outside the netlist: {pin_ref}")
        if endpoint_to_net[pin_ref] != logical_net or logical_net not in net_names:
            raise ValueError(f"test point {point.get('id')} logical net does not match {pin_ref}")
        alias, pin = _endpoint_parts(pin_ref)
        anchors = {item["pin"] for item in packages[alias].get("visual", {}).get("anchors", [])}
        if pin not in anchors:
            raise ValueError(f"test point has no visual contact anchor: {pin_ref}")

    hil = value.get("hil")
    if not isinstance(hil, dict) or hil.get("driver") not in {"mock", "replay"}:
        raise ValueError("E2E scenarios must use mock or replay HIL")
    if not isinstance(hil.get("tests"), list) or not hil["tests"]:
        raise ValueError("scenario HIL requires tests")
    return {"scenario": value, "packages": packages, "paths": paths, "endpointToNet": endpoint_to_net}


def _package_files(package: dict[str, Any], package_path: Path) -> dict[str, bytes]:
    names: set[str] = set()
    visual = package.get("visual", {})
    physical = package.get("physical", {})
    for name in (visual.get("appearance"), visual.get("symbol"), visual.get("geometry"), physical.get("geometry")):
        if isinstance(name, str):
            names.add(name)
    for view in visual.get("views", []):
        if isinstance(view, dict) and isinstance(view.get("path"), str):
            names.add(view["path"])
    files = {}
    for name in sorted(names):
        source = package_path.parent / name
        if source.is_file():
            files[name] = source.read_bytes()
    return files


def build_hil_request(scenario: dict[str, Any], asset_lock: str, wiring_lock: str) -> dict[str, Any]:
    plan = {
        "schema": HIL_SCHEMA,
        "id": f"{scenario['id']}-software-loop",
        "safety": copy.deepcopy(scenario["hil"]["safety"]),
        "tests": copy.deepcopy(scenario["hil"]["tests"]),
    }
    return {
        "driver": scenario["hil"]["driver"],
        "devices": {"dut": f"mock-{scenario['id']}-dut", "fixture": f"mock-{scenario['id']}-fixture"},
        "wiringLockSha256": wiring_lock,
        "assetLockSha256": asset_lock,
        "firmwareSha256": sha256_json({"scenario": scenario["id"], "firmware": "mock"}),
        "plan": plan,
    }


def run_scenario(scenario: dict[str, Any], root: Path) -> dict[str, Any]:
    checked = validate_scenario(copy.deepcopy(scenario))
    scenario = checked["scenario"]
    scenario_root = root / scenario["id"]
    registry = ComponentRegistry(scenario_root / "registry")
    installed = []
    for component in scenario["components"]:
        alias = component["alias"]
        result = registry.install(checked["packages"][alias], _package_files(checked["packages"][alias], checked["paths"][alias]))
        installed.append(result["ref"])

    fixture_result = generate_fixture(scenario["fixture"], scenario_root / "fixtures")
    generated = {path.name for path in Path(fixture_result["directory"]).iterdir()}
    missing = REQUIRED_FIXTURE_FILES - generated
    if missing:
        raise AssertionError(f"{scenario['id']} fixture is incomplete: {sorted(missing)}")

    asset_lock = sha256_json([registry.get(reference).get("packageSha256") for reference in installed])
    wiring_lock = sha256_json(scenario["nets"])
    request = build_hil_request(scenario, asset_lock, wiring_lock)
    engine = HilEngine(scenario_root / "hil", registry)
    prepared = engine.prepare(request)
    armed = engine.arm(prepared["jobId"], prepared["nonce"], True)
    report = engine.run(prepared["jobId"])
    if prepared["state"] != "PREPARED" or armed["state"] != "ARMED" or report["state"] != "PASSED":
        raise AssertionError(f"{scenario['id']} did not complete the mock HIL state machine")
    if report["physicalStatus"] != "PHYSICAL_UNVERIFIED":
        raise AssertionError(f"{scenario['id']} lost the physical verification boundary")

    return {
        "id": scenario["id"],
        "title": scenario["title"],
        "status": "PASS",
        "verificationStatus": scenario["verificationStatus"],
        "components": installed,
        "componentCount": len(installed),
        "netCount": len(scenario["nets"]),
        "testCount": len(request["plan"]["tests"]),
        "fixtureStatus": fixture_result["status"],
        "fixtureFiles": sorted(generated),
        "hilStates": [prepared["state"], armed["state"], report["state"]],
        "wiringLockSha256": wiring_lock,
        "assetLockSha256": asset_lock,
        "reportSha256": report["reportSha256"],
    }


def load_scenarios(directory: Path = SCENARIOS) -> list[dict[str, Any]]:
    paths = sorted(directory.glob("*.json"))
    if not paths:
        raise ValueError(f"no E2E scenarios found in {directory}")
    return [_load_json(path) for path in paths]


def verify_all(root: Path, directory: Path = SCENARIOS) -> dict[str, Any]:
    results = [run_scenario(scenario, root) for scenario in load_scenarios(directory)]
    ids = [result["id"] for result in results]
    if len(ids) != len(set(ids)):
        raise ValueError("E2E scenario ids must be unique")
    return {
        "schema": "circuitlab-e2e-report/v1",
        "status": "PASS",
        "physicalStatus": "PHYSICAL_UNVERIFIED",
        "scenarioCount": len(results),
        "scenarios": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate catalog-backed CircuitLab designs through fixture and mock HIL.")
    parser.add_argument("--data", type=Path)
    parser.add_argument("--scenarios", type=Path, default=SCENARIOS)
    args = parser.parse_args()
    if args.data:
        report = verify_all(args.data.expanduser().resolve(), args.scenarios.expanduser().resolve())
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    with tempfile.TemporaryDirectory(prefix="circuitlab-e2e-") as temporary:
        report = verify_all(Path(temporary), args.scenarios.expanduser().resolve())
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
