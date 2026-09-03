#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from _platform import ComponentRegistry, sha256_json
from verify_e2e_scenarios import _package_files, build_hil_request, load_scenarios, validate_scenario


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "assets" / "template"


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _request(base: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"{base}{path}",
        data=body,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method="POST" if body is not None else "GET",
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def _wait_for_server(base: str, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
            raise RuntimeError(f"CircuitLab test server stopped early: {stderr}")
        try:
            status, payload = _request(base, "/healthz")
            if status == 200 and payload.get("ok") is True:
                return
        except (URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(0.05)
    raise TimeoutError("CircuitLab test server did not become ready")


def _oversized_request(port: int) -> bytes:
    request = (
        "POST /api/hil/prepare HTTP/1.0\r\n"
        "Host: 127.0.0.1\r\n"
        "Content-Type: application/json\r\n"
        "Content-Length: 1048577\r\n\r\n"
    ).encode("ascii")
    with socket.create_connection(("127.0.0.1", port), timeout=5) as connection:
        connection.sendall(request)
        connection.shutdown(socket.SHUT_WR)
        chunks = []
        while chunk := connection.recv(65536):
            chunks.append(chunk)
    return b"".join(chunks)


def verify_http_api(root: Path) -> dict[str, Any]:
    project = root / "project"
    data = root / "data"
    shutil.copytree(TEMPLATE / "core", project)
    shutil.copytree(TEMPLATE / "starter", project, dirs_exist_ok=True)
    scenarios = load_scenarios()
    checked = [validate_scenario(scenario) for scenario in scenarios]
    registry = ComponentRegistry(data / "registry")
    installed: set[str] = set()
    for scenario in checked:
        for component in scenario["scenario"]["components"]:
            if component["ref"] in installed:
                continue
            alias = component["alias"]
            registry.install(scenario["packages"][alias], _package_files(scenario["packages"][alias], scenario["paths"][alias]))
            installed.add(component["ref"])

    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    environment = os.environ.copy()
    environment["CIRCUITLAB_DATA_DIR"] = str(data)
    environment["CIRCUITLAB_LAYOUT_DIR"] = str(root / "layout")
    process = subprocess.Popen(
        [sys.executable, str(project / "server.py"), "--config", str(project / "circuit-lab.json"), "--host", "127.0.0.1", "--port", str(port)],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    results = []
    try:
        _wait_for_server(base, process)
        status, platform = _request(base, "/api/platform")
        if status != 200 or platform.get("componentCount") != len(installed):
            raise AssertionError("HTTP platform endpoint did not expose the installed E2E catalog")

        for item in checked:
            scenario = item["scenario"]
            reference = scenario["components"][0]["ref"]
            status, component = _request(base, f"/api/components/{quote(reference, safe='@')}")
            if status != 200 or component.get("identity", {}).get("assetId") != reference.rsplit("@", 1)[0]:
                raise AssertionError(f"HTTP component detail failed for {reference}")

            status, fixture = _request(base, "/api/fixture/generate", scenario["fixture"])
            if status != 200 or fixture.get("status") != "GENERATED_UNVERIFIED_DO_NOT_FABRICATE":
                raise AssertionError(f"HTTP fixture generation failed for {scenario['id']}")

            asset_lock = sha256_json([registry.get(component["ref"]).get("packageSha256") for component in scenario["components"]])
            request = build_hil_request(scenario, asset_lock, sha256_json(scenario["nets"]))
            status, prepared = _request(base, "/api/hil/prepare", request)
            if status != 200 or prepared.get("state") != "PREPARED":
                raise AssertionError(f"HTTP HIL prepare failed for {scenario['id']}")
            status, armed = _request(base, "/api/hil/arm", {"jobId": prepared["jobId"], "nonce": prepared["nonce"], "acknowledged": True})
            if status != 200 or armed.get("state") != "ARMED":
                raise AssertionError(f"HTTP HIL arm failed for {scenario['id']}")
            status, report = _request(base, "/api/hil/run", {"jobId": prepared["jobId"]})
            if status != 200 or report.get("state") != "PASSED" or report.get("physicalStatus") != "PHYSICAL_UNVERIFIED":
                raise AssertionError(f"HTTP HIL run failed for {scenario['id']}")
            results.append({"id": scenario["id"], "fixture": fixture["status"], "hil": [prepared["state"], armed["state"], report["state"]]})

        unsafe = build_hil_request(scenarios[0], "1" * 64, "2" * 64)
        unsafe["plan"]["safety"]["maximumVoltage"] = 48
        status, rejected = _request(base, "/api/hil/prepare", unsafe)
        if status != 400 or "0..24.0V" not in rejected.get("error", ""):
            raise AssertionError("HTTP API did not reject a 48V HIL plan")
        oversized_response = _oversized_request(port)
        if b" 413 " not in oversized_response.split(b"\r\n", 1)[0] or b"exceeds" not in oversized_response:
            raise AssertionError("HTTP API did not reject an oversized JSON body")
        status, reports = _request(base, "/api/reports")
        if status != 200 or len(reports.get("reports", [])) != len(scenarios):
            raise AssertionError("HTTP reports endpoint did not retain every E2E run")
        return {
            "schema": "circuitlab-http-e2e-report/v1",
            "status": "PASS",
            "physicalStatus": "PHYSICAL_UNVERIFIED",
            "componentCount": len(installed),
            "scenarioCount": len(results),
            "unsafe48VRejected": True,
            "oversizedBodyRejected": True,
            "scenarios": results,
        }
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="circuitlab-http-e2e-") as temporary:
        print(json.dumps(verify_http_api(Path(temporary)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
