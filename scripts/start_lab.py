#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Start a CircuitLab project with the canonical portable server.")
    parser.add_argument("project", type=Path, help="Directory containing circuit-lab.json")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default="8765")
    args = parser.parse_args()
    project = args.project.expanduser().resolve()
    server = project / "server.py"
    config = project / "circuit-lab.json"
    if not server.is_file() or not config.is_file():
        raise SystemExit(f"not a standalone CircuitLab project: {project}")
    os.execv(sys.executable, [sys.executable, str(server), "--config", str(config), "--host", args.host, "--port", str(args.port)])


if __name__ == "__main__":
    main()

