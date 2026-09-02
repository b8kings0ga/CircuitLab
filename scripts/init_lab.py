#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = SKILL_ROOT / "assets" / "template"


def require_empty(target: Path) -> None:
    if target.exists() and any(target.iterdir()):
        raise SystemExit(f"refusing to overwrite non-empty directory: {target}")
    target.mkdir(parents=True, exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an offline CircuitLab project.")
    parser.add_argument("target", type=Path)
    parser.add_argument("--board-svg", type=Path)
    parser.add_argument("--board-json", type=Path)
    parser.add_argument("--skip-catalog", action="store_true", help="Do not install the bundled offline hardware catalog.")
    args = parser.parse_args()
    if bool(args.board_svg) != bool(args.board_json):
        parser.error("--board-svg and --board-json must be provided together")

    target = args.target.expanduser().resolve()
    require_empty(target)
    shutil.copytree(TEMPLATE / "core", target, dirs_exist_ok=True)
    shutil.copytree(TEMPLATE / "starter", target, dirs_exist_ok=True)

    if args.board_svg:
        asset_dir = target / "web" / "assets" / "custom-board"
        asset_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.board_svg.expanduser(), asset_dir / "board.svg")
        shutil.copy2(args.board_json.expanduser(), asset_dir / "board.json")
        config_path = target / "circuit-lab.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        boards = config["frontend"]["boards"]
        if len(boards) != 1:
            raise SystemExit("custom board replacement requires a starter with exactly one board")
        board = next(iter(boards.values()))
        board.update({
            "asset": "/assets/custom-board/board.svg",
            "geometry": "/assets/custom-board/board.json",
        })
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    if not args.skip_catalog:
        subprocess.run([sys.executable, str(SKILL_ROOT / "scripts" / "generate_builtin_catalog.py"), "--install"], check=True, stdout=subprocess.DEVNULL)

    print(target)


if __name__ == "__main__":
    main()
