from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import secrets
import shutil
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PLATFORM_SCHEMA = "circuitlab-platform/v1"
COMPONENT_SCHEMA = "component-package/v1"
FIXTURE_SCHEMA = "fixture-package/v1"
HIL_SCHEMA = "hil-plan/v1"
DRIVER_SCHEMA = "fixture-driver/v1"
MAX_VOLTAGE = 24.0
PHYSICAL_STATUS = "PHYSICAL_UNVERIFIED"
FABRICATION_STATUS = "GENERATED_UNVERIFIED_DO_NOT_FABRICATE"
TERMINAL_STATES = {"PASSED", "FAILED", "ABORTED"}
CHIP_LEVELS = {
    "integrated-circuit", "analog-ic", "digital-ic", "mixed-signal-ic", "interface-ic",
    "memory-ic", "power-management-ic", "sensor-ic", "mems-sensor", "environmental-sensor",
    "six-axis-imu", "isolated-current-sensor", "microcontroller", "wireless-microcontroller",
    "soc", "wireless-soc", "processor", "fpga", "motor-driver-ic", "differential-line-receiver",
    "buck-regulator", "ldo-regulator", "safety-latch-logic",
}
NON_CHIP_MARKERS = {
    "board", "module", "assembly", "computer", "display", "panel", "supply", "motor", "switch",
    "button", "card", "connector", "resistor", "diode", "mosfet", "transistor", "relay", "fixture",
}


def stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: object) -> str:
    return sha256_bytes(stable_json(value).encode("utf-8"))


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(body, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def safe_segment(value: str, label: str) -> str:
    if not value or value in {".", ".."} or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for char in value):
        raise ValueError(f"invalid {label}: {value!r}")
    return value


def package_ref(package: dict[str, Any]) -> str:
    identity = package.get("identity", {})
    return f"{identity.get('assetId', '')}@{identity.get('revision', '')}"


def is_chip_package(package: dict[str, Any]) -> bool:
    identity = package.get("identity", {})
    physical = package.get("physical", {})
    level = str(identity.get("level", "")).casefold().replace("_", "-")
    package_name = str(physical.get("package", "")).casefold().replace("_", "-")
    if level not in CHIP_LEVELS and not level.endswith("-ic"):
        return False
    package_words = set(filter(None, package_name.replace("/", "-").split("-")))
    return not bool(package_words & NON_CHIP_MARKERS)


def require_chip_package(package: dict[str, Any]) -> dict[str, Any]:
    if not is_chip_package(package):
        identity = package.get("identity", {})
        raise ValueError(
            f"chip-only acquisition rejected level {identity.get('level', '')!r} for {identity.get('mpn', '')!r}"
        )
    return package


def component_family(package: dict[str, Any]) -> tuple[str, str]:
    level = str(package.get("identity", {}).get("level", "")).casefold().replace("_", "-")
    if level in {"development-board", "linux-single-board-computer", "controller-board", "motor-driver-board"}:
        return "board", "development-board" if level == "development-board" else "single-board-computer"
    if "display" in level or level in {"operator-panel"}:
        return "display", "display"
    if "resistor" in level:
        return "passive", "resistor"
    if "button" in level or "switch" in level:
        return "control", "button-switch"
    if level == "indicator-led" or level.endswith("-led"):
        return "indicator", "led"
    if any(marker in level for marker in ("distance", "time-of-flight", "tof")):
        return "sensor", "distance"
    if any(marker in level for marker in ("magnetic", "magnetometer")):
        return "sensor", "magnetic"
    if any(marker in level for marker in ("gas", "air-quality", "voc")):
        return "sensor", "gas"
    if any(marker in level for marker in ("sound", "microphone", "audio-sensor")):
        return "sensor", "sound"
    if any(marker in level for marker in ("light", "color", "gesture", "proximity")):
        return "sensor", "light"
    if any(marker in level for marker in ("temperature-humidity", "humidity-temperature", "environmental")):
        return "sensor", "environment"
    if level in {"environmental-sensor"}:
        return "sensor", "environment"
    if any(marker in level for marker in ("motion", "accelerometer", "gyroscope", "imu")) or level == "mems-sensor":
        return "sensor", "motion-imu"
    if "current-sensor" in level:
        return "sensor", "current"
    if level == "sensor-ic" or "sensor" in level:
        return "sensor", "general"
    if level in {"microcontroller", "wireless-microcontroller", "soc", "wireless-soc", "processor", "fpga"}:
        return "controller", "mcu-soc"
    return "support", "support-ic"


def validate_component(package: object) -> dict[str, Any]:
    if not isinstance(package, dict) or package.get("schema") != COMPONENT_SCHEMA:
        raise ValueError(f"component package schema must be {COMPONENT_SCHEMA}")
    identity = package.get("identity")
    if not isinstance(identity, dict):
        raise ValueError("component identity must be an object")
    for key in ("assetId", "revision", "manufacturer", "mpn", "level", "status"):
        if not isinstance(identity.get(key), str) or not identity[key].strip():
            raise ValueError(f"component identity.{key} is required")
    safe_segment(identity["assetId"], "assetId")
    safe_segment(identity["revision"], "revision")
    electrical = package.get("electrical", {})
    pins = electrical.get("pins", []) if isinstance(electrical, dict) else []
    if not isinstance(pins, list):
        raise ValueError("component electrical.pins must be an array")
    names: set[str] = set()
    for pin in pins:
        if not isinstance(pin, dict) or not isinstance(pin.get("name"), str) or not pin["name"]:
            raise ValueError("each electrical pin requires a name")
        if pin["name"] in names:
            raise ValueError(f"duplicate electrical pin: {pin['name']}")
        names.add(pin["name"])
    visual = package.get("visual", {})
    anchors = visual.get("anchors", []) if isinstance(visual, dict) else []
    if not isinstance(anchors, list):
        raise ValueError("component visual.anchors must be an array")
    for anchor in anchors:
        if not isinstance(anchor, dict) or anchor.get("pin") not in names:
            raise ValueError(f"visual anchor references unknown electrical pin: {anchor.get('pin') if isinstance(anchor, dict) else anchor}")
        for coordinate in ("x", "y"):
            value = anchor.get(coordinate)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"visual anchor {coordinate} must be normalized to 0..1")
    evidence = package.get("evidence", {})
    if not isinstance(evidence, dict) or not isinstance(evidence.get("sources", []), list):
        raise ValueError("component evidence.sources must be an array")
    return package


class ComponentRegistry:
    def __init__(self, root: Path):
        self.root = root
        self.components = root / "components"
        self.database = root / "index.sqlite3"
        self.lock = threading.RLock()
        self.components.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize_database(self) -> None:
        with self._connect() as database:
            database.executescript(
                """
                CREATE TABLE IF NOT EXISTS components (
                  ref TEXT PRIMARY KEY,
                  asset_id TEXT NOT NULL,
                  revision TEXT NOT NULL,
                  manufacturer TEXT NOT NULL,
                  mpn TEXT NOT NULL,
                  level TEXT NOT NULL,
                  status TEXT NOT NULL,
                  package_path TEXT NOT NULL,
                  package_sha256 TEXT NOT NULL,
                  imported_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS procurement_snapshots (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  component_ref TEXT NOT NULL,
                  provider TEXT NOT NULL,
                  sampled_at TEXT NOT NULL,
                  stale_after TEXT,
                  payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS hil_runs (
                  job_id TEXT PRIMARY KEY,
                  state TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  report_path TEXT NOT NULL
                );
                """
            )

    def package_path(self, reference: str) -> Path:
        if "@" not in reference:
            raise ValueError("component reference must use assetId@revision")
        asset_id, revision = reference.rsplit("@", 1)
        return self.components / safe_segment(asset_id, "assetId") / safe_segment(revision, "revision") / "component-package.json"

    def install(self, package: dict[str, Any], files: dict[str, bytes] | None = None) -> dict[str, Any]:
        package = validate_component(package)
        reference = package_ref(package)
        path = self.package_path(reference)
        normalized = json.loads(json.dumps(package))
        with self.lock:
            evidence = normalized.setdefault("evidence", {})
            current = load_json(path) if path.exists() else None
            if not evidence.get("capturedAt"):
                if current is not None:
                    evidence["capturedAt"] = current.get("evidence", {}).get("capturedAt")
                evidence.setdefault("capturedAt", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            normalized["packageSha256"] = sha256_json({key: value for key, value in normalized.items() if key != "packageSha256"})
            if path.exists():
                assert current is not None
                if current.get("packageSha256") == normalized["packageSha256"]:
                    return {"status": "unchanged", "ref": reference, "packageSha256": normalized["packageSha256"]}
                raise ValueError(f"immutable component revision conflicts with existing package: {reference}")
            path.parent.mkdir(parents=True, exist_ok=True)
            for name, body in (files or {}).items():
                relative = Path(name)
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError(f"unsafe component file path: {name}")
                target = path.parent / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(body)
            atomic_json(path, normalized)
            identity = normalized["identity"]
            with self._connect() as database:
                database.execute(
                    "INSERT INTO components VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        reference,
                        identity["assetId"],
                        identity["revision"],
                        identity["manufacturer"],
                        identity["mpn"],
                        identity["level"],
                        identity["status"],
                        str(path),
                        normalized["packageSha256"],
                        normalized["evidence"]["capturedAt"],
                    ),
                )
        return {"status": "installed", "ref": reference, "packageSha256": normalized["packageSha256"]}

    def list(self, query: str = "", scope: str = "all", latest_only: bool = False) -> list[dict[str, Any]]:
        if scope not in {"chips", "all"}:
            raise ValueError("component scope must be chips or all")
        needle = f"%{query.strip()}%"
        with self._connect() as database:
            rows = database.execute(
                """SELECT ref, asset_id, revision, manufacturer, mpn, level, status, package_path, package_sha256, imported_at
                   FROM components
                   WHERE ? = '%%' OR ref LIKE ? OR manufacturer LIKE ? OR mpn LIKE ?
                   ORDER BY manufacturer, mpn, ref""",
                (needle, needle, needle, needle),
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            package = load_json(Path(item["package_path"]))
            item["scope"] = "chip" if is_chip_package(package) else "history"
            item["family"], item["sensor_type"] = component_family(package)
            visual = package.get("visual", {})
            item["preview"] = visual.get("appearance") if isinstance(visual, dict) else None
            if scope == "chips" and item["scope"] != "chip":
                continue
            items.append(item)
        if latest_only:
            latest: dict[str, dict[str, Any]] = {}
            for item in items:
                current = latest.get(item["asset_id"])
                if current is None or item["revision"] > current["revision"]:
                    latest[item["asset_id"]] = item
            items = sorted(latest.values(), key=lambda item: (item["manufacturer"], item["mpn"], item["ref"]))
        for item in items:
            item.pop("package_path", None)
            item.pop("asset_id", None)
            item.pop("revision", None)
        return items

    def install_chip(self, package: dict[str, Any], files: dict[str, bytes] | None = None) -> dict[str, Any]:
        return self.install(require_chip_package(package), files)

    def get(self, reference: str) -> dict[str, Any]:
        path = self.package_path(reference)
        if not path.is_file():
            raise KeyError(reference)
        package = load_json(path)
        with self._connect() as database:
            snapshots = database.execute(
                "SELECT provider, sampled_at, stale_after, payload_json FROM procurement_snapshots WHERE component_ref = ? ORDER BY sampled_at DESC",
                (reference,),
            ).fetchall()
        package["procurement"] = [
            {**dict(row), "payload": json.loads(row["payload_json"])} for row in snapshots
        ]
        for snapshot in package["procurement"]:
            snapshot.pop("payload_json", None)
        return package

    def visual_file(self, reference: str, name: str) -> Path:
        package = self.get(reference)
        visual = package.get("visual", {})
        physical = package.get("physical", {})
        allowed = {visual.get("appearance"), visual.get("symbol"), visual.get("geometry"), physical.get("geometry")}
        allowed.update(row.get("path") for row in visual.get("views", []) if isinstance(row, dict))
        if name not in allowed or not isinstance(name, str):
            raise KeyError(name)
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe component visual path")
        root = self.package_path(reference).parent.resolve()
        target = (root / relative).resolve()
        if root not in target.parents or not target.is_file():
            raise KeyError(name)
        return target

    def calibrate(self, reference: str, appearance_sha256: str, points: dict[str, dict[str, float]]) -> dict[str, Any]:
        current = self.get(reference)
        if current.get("visual", {}).get("appearanceSha256") != appearance_sha256:
            raise ValueError("calibration appearance SHA-256 does not match the component package")
        pin_names = {pin["name"] for pin in current.get("electrical", {}).get("pins", [])}
        if set(points) != pin_names:
            raise ValueError("calibration must provide every electrical pin exactly once")
        next_revision = f"{current['identity']['revision']}.cal1"
        next_package = json.loads(json.dumps(current))
        next_package.pop("procurement", None)
        next_package.pop("packageSha256", None)
        next_package["identity"]["revision"] = next_revision
        next_package["identity"]["status"] = "HUMAN_CALIBRATED"
        anchors = []
        for name, point in sorted(points.items()):
            x, y = point.get("x"), point.get("y")
            if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1 for value in (x, y)):
                raise ValueError(f"calibrated point is outside normalized bounds: {name}")
            anchors.append({"pin": name, "x": round(float(x), 8), "y": round(float(y), 8), "status": "HUMAN_CALIBRATED"})
        next_package.setdefault("visual", {})["anchors"] = anchors
        next_package["visual"]["coordinateStatus"] = "HUMAN_CALIBRATED"
        next_package.setdefault("evidence", {}).setdefault("sources", []).append(
            {"type": "manual-touchpoint-calibration", "appearanceSha256": appearance_sha256}
        )
        result = self.install(next_package)
        return {**result, "anchors": anchors}

    def add_procurement_snapshot(self, reference: str, snapshot: dict[str, Any]) -> dict[str, Any]:
        self.get(reference)
        provider = str(snapshot.get("provider", "")).lower()
        if provider not in {"digikey", "mouser"}:
            raise ValueError("procurement provider must be digikey or mouser")
        sampled_at = str(snapshot.get("sampledAt") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        with self._connect() as database:
            database.execute(
                "INSERT INTO procurement_snapshots(component_ref, provider, sampled_at, stale_after, payload_json) VALUES (?, ?, ?, ?, ?)",
                (reference, provider, sampled_at, snapshot.get("staleAfter"), stable_json(snapshot.get("payload", {}))),
            )
        return {"status": "recorded", "ref": reference, "provider": provider, "sampledAt": sampled_at}


def normalize_sindri_package(directory: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    component = load_json(directory / "component.json")
    pins_document = load_json(directory / component.get("pins", "pins.json"))
    sources_document = load_json(directory / component.get("sources", "sources.json"))
    pins = pins_document.get("pins", [])
    anchors = [
        {"pin": pin["name"], "x": pin["x"], "y": pin["y"], "status": pins_document.get("coordinate_status", "VISUAL_SUGGESTION")}
        for pin in pins
        if isinstance(pin, dict) and isinstance(pin.get("x"), (int, float)) and isinstance(pin.get("y"), (int, float))
    ]
    appearance = directory / component.get("appearance", "appearance.webp")
    package = {
        "schema": COMPONENT_SCHEMA,
        "identity": {
            "assetId": component["asset_id"],
            "revision": component["revision"],
            "manufacturer": component.get("manufacturer", "Unknown"),
            "mpn": component.get("mpn", component["asset_id"]),
            "level": component.get("category", "component"),
            "status": component.get("status", "IMPORTED_UNVERIFIED"),
            "lifecycle": component.get("lifecycle", "unknown"),
        },
        "electrical": {
            "status": pins_document.get("electrical_status", "UNVERIFIED"),
            "pins": [
                {
                    "name": str(pin["name"]),
                    "number": str(pin.get("number", pin["name"])),
                    "direction": pin.get("direction", "unspecified"),
                    "functions": pin.get("functions", []),
                }
                for pin in pins if isinstance(pin, dict) and pin.get("name")
            ],
        },
        "visual": {
            "appearance": component.get("appearance"),
            "appearanceSha256": sha256_bytes(appearance.read_bytes()) if appearance.is_file() else None,
            "coordinateStatus": pins_document.get("coordinate_status", "VISUAL_SUGGESTION"),
            "anchors": anchors,
            "symbol": component.get("symbol"),
            "views": component.get("appearances", []),
        },
        "physical": {
            "package": component.get("package"),
            "footprint": component.get("footprint"),
            "model": component.get("model"),
            "geometry": component.get("geometry"),
        },
        "evidence": {
            "sources": sources_document.get("sources", []),
            "importedFrom": "Sindri",
            "sourceDirectorySha256": sha256_json(sorted(
                (str(path.relative_to(directory)), sha256_bytes(path.read_bytes()))
                for path in directory.rglob("*") if path.is_file()
            )),
        },
    }
    files = {str(path.relative_to(directory)): path.read_bytes() for path in directory.rglob("*") if path.is_file()}
    return package, files


def import_sindri_assets(source: Path, registry: ComponentRegistry) -> dict[str, Any]:
    if not source.is_dir():
        raise ValueError(f"Sindri asset directory does not exist: {source}")
    installed = unchanged = conflicts = 0
    errors: list[dict[str, str]] = []
    for component_file in sorted(source.rglob("component.json")):
        try:
            package, files = normalize_sindri_package(component_file.parent)
            result = registry.install(package, files)
            installed += result["status"] == "installed"
            unchanged += result["status"] == "unchanged"
        except Exception as error:
            conflicts += 1
            errors.append({"path": str(component_file), "error": str(error)})
    return {"source": str(source), "installed": installed, "unchanged": unchanged, "conflicts": conflicts, "errors": errors}


def validate_fixture(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("fixture request must be an object")
    fixture_id = safe_segment(str(payload.get("id", "")), "fixture id")
    points = payload.get("testPoints")
    if not isinstance(points, list) or not points:
        raise ValueError("fixture requires at least one test point")
    minimum_spacing = float(payload.get("minimumSpacingMm", 2.54))
    if not 1.0 <= minimum_spacing <= 25:
        raise ValueError("minimumSpacingMm must be between 1 and 25")
    normalized: list[dict[str, Any]] = []
    ids: set[str] = set()
    positions: list[tuple[str, float, float]] = []
    for point in points:
        if not isinstance(point, dict):
            raise ValueError("test point must be an object")
        point_id = safe_segment(str(point.get("id", "")), "test point id")
        if point_id in ids:
            raise ValueError(f"duplicate test point id: {point_id}")
        ids.add(point_id)
        for key in ("pinRef", "visualAnchor", "pad", "logicalNet"):
            if not isinstance(point.get(key), str) or not point[key]:
                raise ValueError(f"test point {point_id} requires explicit {key}")
        x, y = point.get("xMm"), point.get("yMm")
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= 1000 for value in (x, y)):
            raise ValueError(f"test point {point_id} coordinates must be within 0..1000 mm")
        for other_id, other_x, other_y in positions:
            if math.hypot(float(x) - other_x, float(y) - other_y) < minimum_spacing:
                raise ValueError(f"test points {other_id} and {point_id} violate minimum spacing")
        positions.append((point_id, float(x), float(y)))
        normalized.append({**point, "id": point_id, "xMm": round(float(x), 4), "yMm": round(float(y), 4)})
    voltage = float(payload.get("maximumVoltage", 3.3))
    if voltage <= 0 or voltage > MAX_VOLTAGE:
        raise ValueError(f"fixture maximumVoltage must be within 0..{MAX_VOLTAGE}V")
    return {
        "schema": FIXTURE_SCHEMA,
        "id": fixture_id,
        "revision": int(payload.get("revision", 1)),
        "status": FABRICATION_STATUS,
        "physicalStatus": PHYSICAL_STATUS,
        "minimumSpacingMm": minimum_spacing,
        "maximumVoltage": voltage,
        "maximumCurrentMa": float(payload.get("maximumCurrentMa", 500)),
        "testPoints": normalized,
        "locatingHoles": payload.get("locatingHoles", []),
        "keepouts": payload.get("keepouts", []),
        "protection": payload.get("protection", []),
    }


def _fixture_csv(fixture: dict[str, Any]) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id", "logicalNet", "pinRef", "visualAnchor", "pad", "xMm", "yMm", "probe"])
    writer.writeheader()
    for point in fixture["testPoints"]:
        writer.writerow({key: point.get(key, "P75-B1") if key == "probe" else point.get(key, "") for key in writer.fieldnames})
    return output.getvalue().encode("utf-8")


def _fixture_dxf(fixture: dict[str, Any]) -> bytes:
    lines = ["0", "SECTION", "2", "ENTITIES"]
    for point in fixture["testPoints"]:
        lines += ["0", "CIRCLE", "8", "POGO", "10", str(point["xMm"]), "20", str(point["yMm"]), "40", "0.65"]
    lines += ["0", "ENDSEC", "0", "EOF", ""]
    return "\n".join(lines).encode("ascii")


def _fixture_kicad(fixture: dict[str, Any]) -> bytes:
    pads = "\n".join(
        f'  (footprint "CircuitLab:Pogo" (layer "F.Cu") (at {point["xMm"]} {point["yMm"]}) (property "Reference" "{point["id"]}" (at 0 -2 0) (layer "F.SilkS")) (pad "1" thru_hole circle (at 0 0) (size 1.8 1.8) (drill 1.0) (layers "*.Cu" "*.Mask") (net {index + 1} "{point["logicalNet"]}")))'
        for index, point in enumerate(fixture["testPoints"])
    )
    nets = "\n".join(f'  (net {index + 1} "{point["logicalNet"]}")' for index, point in enumerate(fixture["testPoints"]))
    return f'(kicad_pcb (version 20240108) (generator circuitlab)\n  (general (thickness 1.6))\n{nets}\n{pads}\n)\n'.encode("utf-8")


def _fixture_gerber(fixture: dict[str, Any]) -> bytes:
    rows = ["G04 CircuitLab GENERATED_UNVERIFIED_DO_NOT_FABRICATE*", "%FSLAX46Y46*%", "%MOMM*%", "%ADD10C,1.800000*%", "D10*"]
    for point in fixture["testPoints"]:
        rows.append(f"X{round(point['xMm'] * 1_000_000):010d}Y{round(point['yMm'] * 1_000_000):010d}D03*")
    rows += ["M02*", ""]
    return "\n".join(rows).encode("ascii")


def _fixture_drill(fixture: dict[str, Any]) -> bytes:
    rows = ["M48", ";CircuitLab GENERATED_UNVERIFIED_DO_NOT_FABRICATE", "METRIC,TZ", "T01C1.000", "%", "T01"]
    rows += [f"X{point['xMm']:.4f}Y{point['yMm']:.4f}" for point in fixture["testPoints"]]
    rows += ["M30", ""]
    return "\n".join(rows).encode("ascii")


def generate_fixture(payload: object, output_root: Path) -> dict[str, Any]:
    fixture = validate_fixture(payload)
    destination = output_root / fixture["id"] / f"v{fixture['revision']}"
    if destination.exists():
        raise ValueError(f"immutable fixture revision already exists: {fixture['id']} v{fixture['revision']}")
    destination.mkdir(parents=True)
    files = {
        "test-points.csv": _fixture_csv(fixture),
        "pogo-plate.dxf": _fixture_dxf(fixture),
        "fixture.kicad_pcb": _fixture_kicad(fixture),
        "fixture-F_Cu.gbr": _fixture_gerber(fixture),
        "fixture-PTH.drl": _fixture_drill(fixture),
        "bom.csv": b"item,description,status\nPOGO,P75-B1 spring probe,UNVERIFIED\nPCB,fixture carrier,DO_NOT_FABRICATE\n",
        "assembly.svg": f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="180"><rect width="100%" height="100%" fill="#111312"/><text x="30" y="60" fill="#6dff9d" font-family="monospace" font-size="22">CircuitLab fixture: {fixture["id"]}</text><text x="30" y="100" fill="#ff8b83" font-family="monospace" font-size="16">GENERATED_UNVERIFIED_DO_NOT_FABRICATE</text></svg>\n'.encode("utf-8"),
    }
    records = []
    for name, body in files.items():
        target = destination / name
        target.write_bytes(body)
        records.append({"path": name, "bytes": len(body), "sha256": sha256_bytes(body)})
    fixture["files"] = records
    fixture["packageSha256"] = sha256_json({key: value for key, value in fixture.items() if key != "packageSha256"})
    atomic_json(destination / "fixture-map.json", fixture)
    return {"status": fixture["status"], "fixture": fixture, "directory": str(destination)}


@dataclass
class MockFixtureDriver:
    fault: str | None = None

    schema: str = DRIVER_SCHEMA
    name: str = "mock"
    physical: bool = False

    def discover(self) -> dict[str, Any]:
        return {"driver": self.name, "devices": [{"role": "dut", "fingerprint": "mock-dut"}, {"role": "fixture", "fingerprint": "mock-fixture"}]}

    def preflight(self, plan: dict[str, Any]) -> dict[str, Any]:
        return {"ok": self.fault != "preflight", "physical": False, "maximumVoltage": plan["safety"]["maximumVoltage"]}

    def execute(self, test: dict[str, Any], sequence: int) -> dict[str, Any]:
        if self.fault == "disconnect":
            raise ConnectionError("mock fixture disconnected")
        if self.fault == "timeout":
            raise TimeoutError("mock fixture timed out")
        if self.fault == "out-of-order":
            return {"sequence": sequence + 1, "value": test.get("expected")}
        value = test.get("sample", test.get("expected", True))
        if self.fault == test.get("id"):
            value = False if isinstance(value, bool) else float(value or 0) + 999
        return {"sequence": sequence, "value": value, "waveform": test.get("waveform", [])}


class HilEngine:
    def __init__(self, root: Path, registry: ComponentRegistry):
        self.root = root
        self.registry = registry
        self.jobs = root / "jobs"
        self.reports = root / "reports"
        self.lock = threading.RLock()
        self.jobs.mkdir(parents=True, exist_ok=True)
        self.reports.mkdir(parents=True, exist_ok=True)

    def _job_path(self, job_id: str) -> Path:
        return self.jobs / f"{safe_segment(job_id, 'job id')}.json"

    def _load(self, job_id: str) -> dict[str, Any]:
        path = self._job_path(job_id)
        if not path.is_file():
            raise KeyError(job_id)
        return load_json(path)

    def _save(self, job: dict[str, Any]) -> None:
        job["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        atomic_json(self._job_path(job["id"]), job)

    def prepare(self, payload: object) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("HIL preparation must be an object")
        plan = payload.get("plan")
        if not isinstance(plan, dict) or plan.get("schema") != HIL_SCHEMA:
            raise ValueError(f"HIL plan schema must be {HIL_SCHEMA}")
        safety = plan.get("safety", {})
        voltage = float(safety.get("maximumVoltage", 0))
        current = float(safety.get("maximumCurrentMa", 0))
        if voltage <= 0 or voltage > MAX_VOLTAGE:
            raise ValueError(f"HIL maximum voltage must be within 0..{MAX_VOLTAGE}V")
        if current <= 0:
            raise ValueError("HIL maximum current must be positive")
        tests = plan.get("tests")
        if not isinstance(tests, list) or not tests:
            raise ValueError("HIL plan requires tests")
        allowed = {"gpio", "pwm", "adc", "i2c", "spi", "uart", "interrupt", "pulse", "heartbeat", "reset", "backup", "flash", "restore", "power", "current"}
        for test in tests:
            if not isinstance(test, dict) or test.get("op") not in allowed or not test.get("id"):
                raise ValueError(f"unsupported or malformed HIL test: {test}")
        devices = payload.get("devices", {})
        if not isinstance(devices, dict) or not devices.get("dut") or not devices.get("fixture"):
            raise ValueError("HIL preparation requires dut and fixture fingerprints")
        nonce = secrets.token_urlsafe(24)
        now = int(time.time())
        job = {
            "schema": "hil-job/v1",
            "id": str(uuid.uuid4()),
            "state": "PREPARED",
            "physicalStatus": PHYSICAL_STATUS,
            "driver": payload.get("driver", "mock"),
            "devices": devices,
            "plan": plan,
            "planSha256": sha256_json(plan),
            "wiringLockSha256": str(payload.get("wiringLockSha256", "")),
            "assetLockSha256": str(payload.get("assetLockSha256", "")),
            "firmwareSha256": str(payload.get("firmwareSha256", "")),
            "nonceSha256": sha256_bytes(nonce.encode("utf-8")),
            "createdAtEpoch": now,
            "expiresAtEpoch": now + min(int(payload.get("ttlSeconds", 600)), 600),
            "events": [{"state": "PREPARED", "at": now}],
        }
        self._save(job)
        return {"jobId": job["id"], "state": job["state"], "nonce": nonce, "expiresAtEpoch": job["expiresAtEpoch"], "binding": {key: job[key] for key in ("devices", "planSha256", "wiringLockSha256", "assetLockSha256", "firmwareSha256")}}

    def arm(self, job_id: str, nonce: str, acknowledged: bool) -> dict[str, Any]:
        with self.lock:
            job = self._load(job_id)
            if job["state"] != "PREPARED":
                raise ValueError(f"cannot arm job in state {job['state']}")
            if int(time.time()) >= job["expiresAtEpoch"]:
                raise ValueError("HIL Arm token expired")
            if not acknowledged:
                raise ValueError("HIL Arm requires explicit wiring and safety acknowledgement")
            if sha256_bytes(nonce.encode("utf-8")) != job["nonceSha256"]:
                raise ValueError("HIL Arm nonce does not match")
            job["state"] = "ARMED"
            job["events"].append({"state": "ARMED", "at": int(time.time())})
            self._save(job)
            return self.public_job(job)

    def run(self, job_id: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        options = options or {}
        with self.lock:
            job = self._load(job_id)
            if job["state"] != "ARMED":
                raise ValueError(f"cannot run job in state {job['state']}")
            if job["driver"] not in {"mock", "replay"}:
                raise ValueError("real serial, flash, power and restore drivers remain fail-closed until physical verification")
            job["state"] = "RUNNING"
            job["events"].append({"state": "RUNNING", "at": int(time.time())})
            self._save(job)
        driver = MockFixtureDriver(options.get("fault"))
        results: list[dict[str, Any]] = []
        failure = None
        try:
            preflight = driver.preflight(job["plan"])
            if not preflight["ok"]:
                raise RuntimeError("fixture preflight failed")
            for sequence, test in enumerate(job["plan"]["tests"], 1):
                response = driver.execute(test, sequence)
                if response.get("sequence") != sequence:
                    raise RuntimeError(f"fixture response sequence mismatch for {test['id']}")
                value = response.get("value")
                passed = value == test.get("expected", value)
                if "minimum" in test:
                    passed = passed and float(value) >= float(test["minimum"])
                if "maximum" in test:
                    passed = passed and float(value) <= float(test["maximum"])
                results.append({"id": test["id"], "op": test["op"], "passed": passed, "value": value, "waveform": response.get("waveform", [])})
                if not passed and test.get("onFailure", "stop") == "stop":
                    break
        except Exception as error:
            failure = str(error)
        with self.lock:
            job = self._load(job_id)
            job["state"] = "PASSED" if not failure and results and all(result["passed"] for result in results) else "FAILED"
            job["events"].append({"state": job["state"], "at": int(time.time()), **({"error": failure} if failure else {})})
            report = {
                "schema": "hil-report/v1",
                "jobId": job_id,
                "state": job["state"],
                "physicalStatus": PHYSICAL_STATUS,
                "driver": driver.name,
                "binding": {key: job[key] for key in ("devices", "planSha256", "wiringLockSha256", "assetLockSha256", "firmwareSha256")},
                "results": results,
                "error": failure,
                "events": job["events"],
                "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            report["reportSha256"] = sha256_json(report)
            report_path = self.reports / f"{job_id}.json"
            atomic_json(report_path, report)
            job["reportPath"] = str(report_path)
            self._save(job)
            with self.registry._connect() as database:
                database.execute(
                    "INSERT OR REPLACE INTO hil_runs(job_id, state, updated_at, report_path) VALUES (?, ?, ?, ?)",
                    (job_id, job["state"], job["updatedAt"], str(report_path)),
                )
            return report

    def abort(self, job_id: str) -> dict[str, Any]:
        with self.lock:
            job = self._load(job_id)
            if job["state"] in TERMINAL_STATES:
                return self.public_job(job)
            job["state"] = "ABORTED"
            job["events"].append({"state": "ABORTED", "at": int(time.time())})
            self._save(job)
            return self.public_job(job)

    def public_job(self, job: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in job.items() if key != "nonceSha256"}

    def status(self, job_id: str | None = None) -> dict[str, Any]:
        if job_id:
            return self.public_job(self._load(job_id))
        jobs = []
        for path in sorted(self.jobs.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:30]:
            jobs.append(self.public_job(load_json(path)))
        return {"jobs": jobs, "physicalStatus": PHYSICAL_STATUS, "drivers": ["mock", "replay"], "lockedDrivers": ["serial", "flash", "power", "restore"]}

    def reports_list(self) -> list[dict[str, Any]]:
        return [load_json(path) for path in sorted(self.reports.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:30]]


class CircuitLabPlatform:
    def __init__(self, root: Path, config: dict[str, Any], config_path: Path):
        self.root = root
        self.config = config
        self.config_path = config_path
        self.registry = ComponentRegistry(root / "registry")
        self.fixtures = root / "fixtures"
        self.hil = HilEngine(root / "hil", self.registry)

    def info(self) -> dict[str, Any]:
        return {
            "schema": PLATFORM_SCHEMA,
            "name": "CircuitLab",
            "project": self.config["id"],
            "physicalStatus": PHYSICAL_STATUS,
            "maximumVoltage": MAX_VOLTAGE,
            "componentCount": len(self.registry.list(scope="all", latest_only=True)),
            "componentScope": "hardware",
            "capabilities": ["projects", "components", "workbench", "touchpoints", "fixture", "hil", "reports"],
        }

    def projects(self) -> list[dict[str, Any]]:
        return [{
            "id": self.config["id"],
            "name": self.config.get("frontend", {}).get("name", self.config["id"]),
            "schema": f"lab-project/v{self.config.get('schemaVersion', 1)}",
            "configPath": str(self.config_path),
            "active": True,
        }]

    def pipeline_latest(self) -> dict[str, Any]:
        path = self.root / "pipeline-reports" / "latest.json"
        if not path.is_file():
            return {"schema": "hardware-pipeline-report/v1", "status": "NOT_RUN", "stages": {}}
        return load_json(path)
