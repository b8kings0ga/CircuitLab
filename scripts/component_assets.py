#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _platform import ComponentRegistry, default_data_root


def audit_chips(registry: ComponentRegistry) -> dict:
    items = []
    gap_counts: dict[str, int] = {}
    for row in registry.list(scope="chips", latest_only=True):
        package = registry.get(row["ref"])
        sources = package.get("evidence", {}).get("sources", [])
        source_text = json.dumps(sources, ensure_ascii=False).casefold()
        pins = package.get("electrical", {}).get("pins", [])
        physical = package.get("physical", {})
        visual = package.get("visual", {})
        gaps = []
        if not physical.get("package"):
            gaps.append("MISSING_PACKAGE")
        if not pins:
            gaps.append("MISSING_PINOUT")
        if "datasheet" not in source_text and ".pdf" not in source_text:
            gaps.append("MISSING_DATASHEET_EVIDENCE")
        if not physical.get("footprint"):
            gaps.append("MISSING_FOOTPRINT")
        if not visual.get("appearance"):
            gaps.append("MISSING_PACKAGE_APPEARANCE")
        for gap in gaps:
            gap_counts[gap] = gap_counts.get(gap, 0) + 1
        items.append({
            "ref": row["ref"], "manufacturer": row["manufacturer"], "mpn": row["mpn"], "level": row["level"],
            "package": physical.get("package"), "pinCount": len(pins), "status": "READY_FOR_REVIEW" if not gaps else "INCOMPLETE",
            "gaps": gaps,
        })
    return {"schema": "chip-catalog-audit/v1", "scope": "chips", "latestOnly": True, "count": len(items), "gapCounts": gap_counts, "items": items}


def main() -> None:
    parser = argparse.ArgumentParser(description="Search, inspect, acquire, or snapshot CircuitLab component assets.")
    parser.add_argument("--data", type=Path, default=default_data_root())
    sub = parser.add_subparsers(dest="command", required=True)
    search = sub.add_parser("search")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--all-history", action="store_true")
    search.add_argument("--all-revisions", action="store_true")
    show = sub.add_parser("show")
    show.add_argument("reference")
    acquire = sub.add_parser("acquire")
    acquire.add_argument("package", type=Path)
    acquire.add_argument("--confirm-exact-mpn", action="store_true")
    snapshot = sub.add_parser("snapshot")
    snapshot.add_argument("reference")
    snapshot.add_argument("document", type=Path)
    sub.add_parser("audit-chips")
    args = parser.parse_args()
    registry = ComponentRegistry(args.data.expanduser().resolve() / "registry")
    if args.command == "search":
        scope = "all" if args.all_history else "chips"
        result = {"components": registry.list(args.query, scope=scope, latest_only=not args.all_revisions), "scope": scope}
    elif args.command == "show":
        result = registry.get(args.reference)
    elif args.command == "acquire":
        if not args.confirm_exact_mpn:
            raise SystemExit("acquire requires --confirm-exact-mpn")
        result = registry.install_chip(json.loads(args.package.read_text(encoding="utf-8")))
    elif args.command == "snapshot":
        result = registry.add_procurement_snapshot(args.reference, json.loads(args.document.read_text(encoding="utf-8")))
    else:
        result = audit_chips(registry)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
