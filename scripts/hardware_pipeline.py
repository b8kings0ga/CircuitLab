#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from _platform import ComponentRegistry, default_data_root, validate_component


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "assets" / "catalog"
STYLE_SCHEMA = "circuitlab-top-style/v1"
REPORT_SCHEMA = "hardware-pipeline-report/v1"
APPROVED_DOMAINS = {
    "learn.adafruit.com", "www.adafruit.com", "cdn-learn.adafruit.com", "cdn-shop.adafruit.com",
    "www.orangepi.org", "orangepi.org", "www.waveshare.com", "files.waveshare.com",
    "wiki.seeedstudio.com", "files.seeedstudio.com", "docs.espressif.com",
    "docs.arduino.cc", "www.raspberrypi.com", "raspberrypi.com", "datasheets.raspberrypi.com",
}
MAX_CAPTURE_BYTES = 4 * 1024 * 1024


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(value)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def latest_catalog_packages() -> list[tuple[Path, dict[str, Any]]]:
    latest: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in CATALOG.glob("*/*/component-package.json"):
        package = json.loads(path.read_text(encoding="utf-8"))
        identity = package.get("identity", {})
        asset_id = str(identity.get("assetId", "")); revision = str(identity.get("revision", ""))
        if not asset_id or not revision:
            continue
        current = latest.get(asset_id)
        if current is None or revision > str(current[1]["identity"]["revision"]):
            latest[asset_id] = (path, package)
    return sorted(latest.values(), key=lambda item: item[1]["identity"]["assetId"])


def official_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").casefold()
    return parsed.scheme == "https" and any(host == domain or host.endswith(f".{domain}") for domain in APPROVED_DOMAINS)


def capture_sources(data_root: Path, *, online: bool) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    cache_root = data_root / "evidence-cache"
    for _, package in latest_catalog_packages():
        identity = package["identity"]
        asset_dir = cache_root / identity["assetId"] / identity["revision"]
        for index, source in enumerate(package.get("evidence", {}).get("sources", [])):
            url = str(source.get("url", ""))
            if not url:
                continue
            snapshot_path = asset_dir / f"source-{index + 1}.json"
            body_path = asset_dir / f"source-{index + 1}.body"
            if not official_url(url):
                results.append({"ref": f'{identity["assetId"]}@{identity["revision"]}', "url": url, "status": "REJECTED_NON_OFFICIAL_DOMAIN"})
                continue
            if not online:
                status = "CACHED_OFFLINE" if snapshot_path.is_file() else "NOT_CAPTURED_OFFLINE"
                results.append({"ref": f'{identity["assetId"]}@{identity["revision"]}', "url": url, "status": status})
                continue
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "CircuitLab-Evidence-Capture/1.0"})
                with urllib.request.urlopen(request, timeout=25) as response:
                    body = response.read(MAX_CAPTURE_BYTES + 1)
                    if len(body) > MAX_CAPTURE_BYTES:
                        raise ValueError(f"source exceeds {MAX_CAPTURE_BYTES} byte capture limit")
                    final_url = response.geturl()
                    if not official_url(final_url):
                        raise ValueError(f"redirected outside official domains: {final_url}")
                    snapshot = {
                        "schema": "hardware-source-snapshot/v1", "requestedUrl": url, "finalUrl": final_url,
                        "capturedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "httpStatus": response.status,
                        "contentType": response.headers.get("Content-Type"), "etag": response.headers.get("ETag"),
                        "lastModified": response.headers.get("Last-Modified"), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                        "bodyFile": body_path.name,
                        "redistribution": "LOCAL_ONLY_EVIDENCE_CACHE",
                    }
                    atomic_bytes(body_path, body)
                    atomic_json(snapshot_path, snapshot)
                    results.append({"ref": f'{identity["assetId"]}@{identity["revision"]}', "url": url, "status": "CAPTURED", "sha256": snapshot["sha256"], "bytes": len(body)})
            except (OSError, ValueError, urllib.error.URLError) as error:
                results.append({
                    "ref": f'{identity["assetId"]}@{identity["revision"]}', "url": url,
                    "status": "CACHED_AFTER_CAPTURE_FAILURE" if snapshot_path.is_file() else "CAPTURE_FAILED",
                    "error": str(error),
                })
    return results


def validate_catalog() -> list[dict[str, Any]]:
    results = []
    seen_refs: set[str] = set()
    for path, raw in latest_catalog_packages():
        package = validate_component(raw)
        identity = package["identity"]
        reference = f'{identity["assetId"]}@{identity["revision"]}'
        if reference in seen_refs:
            raise ValueError(f"duplicate catalog reference: {reference}")
        seen_refs.add(reference)
        visual = package.get("visual", {})
        appearance_name = visual.get("appearance")
        appearance = path.parent / str(appearance_name)
        if not appearance.is_file():
            raise ValueError(f"missing appearance for {reference}: {appearance_name}")
        digest = hashlib.sha256(appearance.read_bytes()).hexdigest()
        if digest != visual.get("appearanceSha256"):
            raise ValueError(f"appearance hash mismatch for {reference}")
        pins = package.get("electrical", {}).get("pins", [])
        anchors = visual.get("anchors", [])
        if len(pins) != len(anchors) or not pins:
            raise ValueError(f"pin/anchor coverage mismatch for {reference}: {len(pins)} pins, {len(anchors)} anchors")
        for source in package.get("evidence", {}).get("sources", []):
            source_url = source.get("url")
            if source_url and not official_url(str(source_url)):
                raise ValueError(f"non-official source in {reference}: {source_url}")
        style = visual.get("style", "legacy-board-style")
        results.append({"ref": reference, "status": "VALID", "pins": len(pins), "appearanceSha256": digest, "style": style})
    return results


def install_catalog(data_root: Path) -> list[dict[str, Any]]:
    registry = ComponentRegistry(data_root / "registry")
    results = []
    for path, package in latest_catalog_packages():
        visual = package.get("visual", {}); physical = package.get("physical", {})
        names = {visual.get("appearance"), visual.get("symbol"), visual.get("geometry"), physical.get("geometry")}
        names.update(row.get("path") for row in visual.get("views", []) if isinstance(row, dict))
        files = {name: (path.parent / name).read_bytes() for name in names if isinstance(name, str) and (path.parent / name).is_file()}
        results.append(registry.install(package, files))
    return results


def render_catalog() -> dict[str, Any]:
    process = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_builtin_catalog.py")],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    return json.loads(process.stdout)


def write_report(data_root: Path, stages: dict[str, Any]) -> dict[str, Any]:
    failed_capture = any(row.get("status") in {"CAPTURE_FAILED", "REJECTED_NON_OFFICIAL_DOMAIN"} for row in stages.get("capture", []))
    report = {
        "schema": REPORT_SCHEMA, "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "PASS_WITH_CAPTURE_WARNINGS" if failed_capture else "PASS", "style": STYLE_SCHEMA, "stages": stages,
    }
    report["reportSha256"] = hashlib.sha256(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    reports = data_root / "pipeline-reports"
    atomic_json(reports / f'{time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())}-{report["reportSha256"][:10]}.json', report)
    atomic_json(reports / "latest.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture official evidence, render consistent top views, validate touchpoints, and install immutable CircuitLab assets.")
    parser.add_argument("command", choices=("capture", "render", "validate", "install", "run"))
    parser.add_argument("--data", type=Path, default=default_data_root())
    parser.add_argument("--online", action="store_true", help="Fetch official pages; otherwise use or report the local evidence cache.")
    args = parser.parse_args()
    data_root = args.data.expanduser().resolve(); stages: dict[str, Any] = {}
    if args.command in {"render", "run"}:
        stages["render"] = render_catalog()
    if args.command in {"capture", "run"}:
        stages["capture"] = capture_sources(data_root, online=args.online)
    if args.command in {"validate", "run"}:
        stages["validate"] = validate_catalog()
    if args.command in {"install", "run"}:
        stages["install"] = install_catalog(data_root)
    report = write_report(data_root, stages)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
