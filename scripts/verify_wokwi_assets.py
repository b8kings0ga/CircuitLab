#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = SKILL_ROOT / "assets" / "template" / "core" / "web" / "vendor" / "wokwi"


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the managed Wokwi asset registry.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    errors = []
    for name, expected in manifest["files"].items():
        path = root / name
        if not path.is_file():
            errors.append(f"missing {name}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            errors.append(f"checksum {name}")

    elements = json.loads((root / "elements" / "catalog.json").read_text(encoding="utf-8"))
    for component in elements["components"]:
        if component["error"]:
            errors.append(f"component {component['type']}: {component['error']}")
        for pin in component["pins"]:
            if pin["visible"] and not all(isinstance(pin[key], (int, float)) for key in ("x", "y")):
                errors.append(f"component pin coordinates {component['type']}:{pin['name']}")

    boards_path = root / "boards" / "catalog.json"
    boards = json.loads(boards_path.read_text(encoding="utf-8")) if boards_path.is_file() else {"boards": []}
    for board in boards["boards"]:
        directory = root / "boards" / board["id"]
        if not (directory / "board.svg").is_file() or not (directory / "board.json").is_file():
            errors.append(f"board files {board['id']}")
        for pin in board["pins"]:
            if pin["visible"] and not all(isinstance(pin[key], (int, float)) for key in ("x", "y")):
                errors.append(f"board pin coordinates {board['id']}:{pin['name']}")

    if errors:
        print("asset registry invalid:")
        print("\n".join(f"  - {error}" for error in errors))
        raise SystemExit(1)
    print(json.dumps({
        "components": len(elements["components"]),
        "componentPins": sum(len(item["pins"]) for item in elements["components"]),
        "boards": len(boards["boards"]),
        "boardPins": sum(len(item["pins"]) for item in boards["boards"]),
        "files": len(manifest["files"]),
        "boardAssetsDistributed": bool(boards["boards"]),
    }))


if __name__ == "__main__":
    main()
