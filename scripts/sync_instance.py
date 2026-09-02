#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
CORE = SKILL_ROOT / "assets" / "template" / "core"
MANIFEST = SKILL_ROOT / "assets" / "template-manifest.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def instance_root(target: Path) -> Path:
    shared_core = target / "simulation" / "circuit_lab"
    projects = target / "simulation" / "projects"
    if (shared_core / "server.py").is_file() and projects.is_dir():
        return shared_core
    legacy_rune = target / "simulation" / "local"
    if (legacy_rune / "circuit-lab.json").is_file():
        return legacy_rune
    if (target / "circuit-lab.json").is_file():
        return target
    raise SystemExit(f"no circuit-lab.json found under {target}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check or sync vendored Circuit Lab core files.")
    parser.add_argument("--target", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files: dict[str, str] = manifest["files"]
    stale_source = [name for name, expected in files.items() if digest(CORE / name) != expected]
    if stale_source:
        raise SystemExit("template manifest is stale: " + ", ".join(stale_source))

    destination = instance_root(args.target.expanduser().resolve())
    legacy_paths = [
        destination / "web" / "vendor" / "wokwi-elements",
        destination / "web" / "assets" / "xiao-esp32-s3",
    ]
    differences = []
    for name in files:
        source = CORE / name
        target = destination / name
        if not target.is_file() or digest(target) != digest(source):
            differences.append(name)
            if args.apply:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

    legacy = [path for path in legacy_paths if path.exists()]
    if legacy and args.apply:
        for path in legacy:
            shutil.rmtree(path)
    elif legacy:
        differences.extend(str(path.relative_to(destination)) for path in legacy)

    if differences and args.check:
        print("core drift:")
        print("\n".join(f"  {name}" for name in differences))
        raise SystemExit(1)
    print("synced" if differences and args.apply else "core is in sync")


if __name__ == "__main__":
    main()
