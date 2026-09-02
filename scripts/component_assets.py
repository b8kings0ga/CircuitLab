#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _platform import ComponentRegistry, default_data_root


def main() -> None:
    parser = argparse.ArgumentParser(description="Search, inspect, acquire, or snapshot CircuitLab component assets.")
    parser.add_argument("--data", type=Path, default=default_data_root())
    sub = parser.add_subparsers(dest="command", required=True)
    search = sub.add_parser("search")
    search.add_argument("query", nargs="?", default="")
    show = sub.add_parser("show")
    show.add_argument("reference")
    acquire = sub.add_parser("acquire")
    acquire.add_argument("package", type=Path)
    acquire.add_argument("--confirm-exact-mpn", action="store_true")
    snapshot = sub.add_parser("snapshot")
    snapshot.add_argument("reference")
    snapshot.add_argument("document", type=Path)
    args = parser.parse_args()
    registry = ComponentRegistry(args.data.expanduser().resolve() / "registry")
    if args.command == "search":
        result = {"components": registry.list(args.query)}
    elif args.command == "show":
        result = registry.get(args.reference)
    elif args.command == "acquire":
        if not args.confirm_exact_mpn:
            raise SystemExit("acquire requires --confirm-exact-mpn")
        result = registry.install(json.loads(args.package.read_text(encoding="utf-8")))
    else:
        result = registry.add_procurement_snapshot(args.reference, json.loads(args.document.read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

