#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _platform import default_data_root, generate_fixture


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an unverified CircuitLab pogo fixture package.")
    parser.add_argument("request", type=Path)
    parser.add_argument("--data", type=Path, default=default_data_root())
    args = parser.parse_args()
    result = generate_fixture(json.loads(args.request.read_text(encoding="utf-8")), args.data.expanduser().resolve() / "fixtures")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

