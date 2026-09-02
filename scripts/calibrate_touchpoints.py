#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _platform import ComponentRegistry, default_data_root


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an immutable human-calibrated CircuitLab component revision.")
    parser.add_argument("reference")
    parser.add_argument("appearance_sha256")
    parser.add_argument("points", type=Path, help="JSON object mapping every electrical pin to normalized x/y")
    parser.add_argument("--data", type=Path, default=default_data_root())
    args = parser.parse_args()
    registry = ComponentRegistry(args.data.expanduser().resolve() / "registry")
    result = registry.calibrate(args.reference, args.appearance_sha256, json.loads(args.points.read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

