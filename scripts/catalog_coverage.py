#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from _platform import component_family


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "assets" / "catalog"


def latest_packages(catalog: Path) -> list[dict]:
    latest: dict[str, tuple[str, dict]] = {}
    for path in catalog.glob("*/*/component-package.json"):
        package = json.loads(path.read_text(encoding="utf-8"))
        identity = package["identity"]
        current = latest.get(identity["assetId"])
        if current is None or identity["revision"] > current[0]:
            latest[identity["assetId"]] = (identity["revision"], package)
    return [row[1] for row in latest.values()]


def coverage(catalog: Path, target: int) -> dict:
    packages = latest_packages(catalog)
    families = Counter("/".join(component_family(package)) for package in packages)
    return {
        "schema": "circuitlab-catalog-coverage/v1",
        "target": target,
        "verified": len(packages),
        "remaining": max(0, target - len(packages)),
        "complete": len(packages) >= target,
        "families": dict(sorted(families.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit reviewed CircuitLab catalog coverage.")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--target", type=int, default=100)
    parser.add_argument("--require-target", action="store_true")
    args = parser.parse_args()
    report = coverage(args.catalog.expanduser().resolve(), args.target)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if args.require_target and not report["complete"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
