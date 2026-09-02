#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _platform import ComponentRegistry, default_data_root, import_sindri_assets


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only import of immutable Sindri electronics assets into CircuitLab.")
    parser.add_argument("source", type=Path, help="Sindri assets/electronics directory")
    parser.add_argument("--data", type=Path, default=default_data_root())
    args = parser.parse_args()
    registry = ComponentRegistry(args.data.expanduser().resolve() / "registry")
    result = import_sindri_assets(args.source.expanduser().resolve(), registry)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["conflicts"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

