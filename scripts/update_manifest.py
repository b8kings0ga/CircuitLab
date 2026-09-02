#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
CORE = SKILL_ROOT / "assets" / "template" / "core"
MANIFEST = SKILL_ROOT / "assets" / "template-manifest.json"


def payload() -> dict[str, object]:
    files = {
        str(path.relative_to(CORE)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(CORE.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }
    return {"templateVersion": 2, "files": files}


def main() -> None:
    parser = argparse.ArgumentParser(description="Update or check the canonical core SHA-256 manifest.")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = json.dumps(payload(), indent=2) + "\n"
    if args.check:
        if not MANIFEST.is_file() or MANIFEST.read_text(encoding="utf-8") != expected:
            raise SystemExit("template manifest is stale")
        print("template manifest is current")
        return
    temporary = MANIFEST.with_name(f".{MANIFEST.name}.tmp")
    temporary.write_text(expected, encoding="utf-8")
    temporary.replace(MANIFEST)
    print(MANIFEST)


if __name__ == "__main__":
    main()
