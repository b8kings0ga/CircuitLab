#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from _platform import ComponentRegistry, default_data_root


SKILL_ROOT = Path(__file__).resolve().parents[1]
WOKWI_ROOT = SKILL_ROOT / "assets/template/core/web/vendor/wokwi"
STEP_ORIGIN = "https://api.step.parts"
USER_AGENT = "CircuitLab/2.0 component discovery"


def request(url: str, timeout: float) -> bytes:
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout
    ) as response:
        return response.read()


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    value = json.loads(request(url, timeout))
    if not isinstance(value, dict):
        raise ValueError("provider response must be a JSON object")
    return value


def step_search(query: str, limit: int, timeout: float) -> dict[str, Any]:
    params = urllib.parse.urlencode({"q": query, "page": 1, "pageSize": min(max(limit, 1), 100)})
    value = fetch_json(f"{STEP_ORIGIN}/v1/parts?{params}", timeout)
    fields = ("id", "name", "category", "family", "standard", "attributes", "pageUrl", "sha256")
    return {
        "provider": "step.parts",
        "status": "CANDIDATES_SELECTION_REQUIRED",
        "items": [{key: row.get(key) for key in fields} for row in value.get("items", []) if isinstance(row, dict)],
    }


def step_acquire(part_id: str, asset_id: str, revision: str, timeout: float, data: Path) -> dict[str, Any]:
    encoded = urllib.parse.quote(part_id, safe="")
    record = fetch_json(f"{STEP_ORIGIN}/v1/parts/{encoded}", timeout)
    if str(record.get("id")) != part_id:
        raise ValueError("exact step.parts part ID did not resolve")
    expected = str(record.get("sha256") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("step.parts record has no authoritative SHA-256")
    model_url = urllib.parse.urljoin(f"{STEP_ORIGIN}/", str(record.get("stepUrl") or ""))
    model = request(model_url, timeout)
    actual = hashlib.sha256(model).hexdigest()
    if actual != expected:
        raise ValueError(f"STEP checksum mismatch: expected {expected}, got {actual}")
    package = {
        "schema": "component-package/v1",
        "identity": {
            "assetId": asset_id,
            "revision": revision,
            "manufacturer": "step.parts catalog",
            "mpn": str(record.get("name") or part_id),
            "level": "mechanical-part",
            "status": "PHYSICAL_UNVERIFIED",
        },
        "electrical": {"pins": []},
        "visual": {"anchors": [], "coordinateStatus": "NOT_APPLICABLE"},
        "physical": {
            "format": "STEP",
            "model": "model.step",
            "attributes": record.get("attributes") or {},
            "verification": "CHECKSUM_VERIFIED_SOURCE_GEOMETRY_ONLY",
        },
        "evidence": {
            "capturedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "sources": [{
                "type": "step-parts",
                "providerPartId": part_id,
                "apiUrl": f"{STEP_ORIGIN}/v1/parts/{encoded}",
                "pageUrl": record.get("pageUrl"),
                "sha256": actual,
                "license": "REVIEW_REQUIRED_BEFORE_REDISTRIBUTION",
            }],
        },
    }
    registry = ComponentRegistry(data.expanduser().resolve() / "registry")
    return registry.install(package, {"model.step": model})


def wokwi_search(query: str) -> dict[str, Any]:
    needle = query.casefold()
    items: list[dict[str, Any]] = []
    for kind, path in (
        ("element", WOKWI_ROOT / "elements/catalog.json"),
        ("board", WOKWI_ROOT / "boards/catalog.json"),
    ):
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("components", payload.get("boards", []))
        for row in rows:
            if needle in json.dumps(row, ensure_ascii=False).casefold():
                items.append({"kind": kind, **row})
    return {"provider": "pinned-wokwi", "status": "LOCAL_PINNED_CANDIDATES", "items": items}


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover CircuitLab engineering component candidates.")
    parser.add_argument("--data", type=Path, default=default_data_root())
    sub = parser.add_subparsers(dest="command", required=True)
    step = sub.add_parser("step-search")
    step.add_argument("query")
    step.add_argument("--limit", type=int, default=10)
    step.add_argument("--timeout", type=float, default=30)
    wokwi = sub.add_parser("wokwi-search")
    wokwi.add_argument("query")
    acquire = sub.add_parser("step-acquire")
    acquire.add_argument("part_id")
    acquire.add_argument("--asset-id", required=True)
    acquire.add_argument("--revision", required=True)
    acquire.add_argument("--confirm-exact-part", action="store_true")
    acquire.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    if args.command == "step-search":
        result = step_search(args.query, args.limit, args.timeout)
    elif args.command == "wokwi-search":
        result = wokwi_search(args.query)
    else:
        if not args.confirm_exact_part:
            raise SystemExit("step-acquire requires --confirm-exact-part")
        result = step_acquire(args.part_id, args.asset_id, args.revision, args.timeout, args.data)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
