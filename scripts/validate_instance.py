#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def web_path(web_root: Path, project_root: Path, url: str, asset_directory: str | None) -> Path:
    if not url.startswith("/") or ".." in Path(url).parts:
        raise ValueError(f"invalid local resource URL: {url}")
    if url.startswith("/project-assets/"):
        if not asset_directory:
            raise ValueError(f"project asset URL requires top-level assets: {url}")
        return project_root / asset_directory / url.removeprefix("/project-assets/")
    return web_root / url.lstrip("/")


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    config_path = root / "circuit-lab.json"
    try:
        config = load(config_path)
        if config.get("schemaVersion") not in {1, 2}:
            errors.append("schemaVersion must be 1 or 2")
        frontend = config["frontend"]
        diagram_path = (root / config["diagram"]).resolve()
        diagram = load(diagram_path)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        return [str(error)]

    shared_web = root.parents[1] / "circuit_lab" / "web" if len(root.parents) > 1 else root / "web"
    web_root = shared_web if shared_web.is_dir() else root / "web"
    parts = {part.get("id"): part for part in diagram.get("parts", [])}
    if None in parts or len(parts) != len(diagram.get("parts", [])):
        errors.append("diagram part IDs must be unique strings")
    connections = {
        f"{connection[0]}>{connection[1]}"
        for connection in diagram.get("connections", [])
        if isinstance(connection, list) and len(connection) >= 2
    }
    expected = {
        f"{pair[0]}>{pair[1]}" for pair in frontend.get("wiring", {}).get("expectedConnections", [])
    }
    for item in sorted(expected - connections):
        errors.append(f"missing expected connection: {item}")
    for item in sorted(connections - expected):
        errors.append(f"unexpected connection: {item}")
    for connection in diagram.get("connections", []):
        for reference in connection[:2]:
            if reference.split(":", 1)[0] not in parts:
                errors.append(f"unknown part in pin reference: {reference}")

    wiring = frontend.get("wiring", {})
    usage: dict[str, int] = {}
    for connection in diagram.get("connections", []):
        for reference in connection[:2]:
            if reference.split(":", 1)[0] in wiring.get("boardPartIds", []):
                usage[reference] = usage.get(reference, 0) + 1
    shared = set(wiring.get("sharedPins", []))
    for reference, count in usage.items():
        if count > 1 and reference not in shared:
            errors.append(f"duplicate board pin: {reference}")

    for part_id in frontend.get("controls", {}):
        if part_id not in parts:
            errors.append(f"control references unknown part: {part_id}")
    for board in frontend.get("boards", {}).values():
        for key in ("asset", "geometry"):
            try:
                resource = web_path(web_root, root, board[key], config.get("assets"))
                if not resource.is_file():
                    errors.append(f"missing board {key}: {resource}")
            except (KeyError, ValueError) as error:
                errors.append(str(error))

    try:
        module_name, factory_name = config["adapter"].split(":", 1)
        sys.path.insert(0, str(root))
        module = importlib.import_module(module_name)
        adapter = getattr(module, factory_name)(config)
        for method in ("snapshot", "apply"):
            if not callable(getattr(adapter, method, None)):
                errors.append(f"adapter is missing {method}()")
    except Exception as error:  # Adapter imports should be reported, not hide other checks.
        errors.append(f"adapter load failed: {error}")
    finally:
        if sys.path and sys.path[0] == str(root):
            sys.path.pop(0)
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a CircuitLab instance.")
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    root = args.target.expanduser().resolve()
    if not (root / "circuit-lab.json").is_file():
        project = root / "simulation" / "projects" / "rune"
        legacy = root / "simulation" / "local"
        if (project / "circuit-lab.json").is_file():
            root = project
        elif (legacy / "circuit-lab.json").is_file():
            root = legacy
    errors = validate(root)
    if errors:
        print("validation failed:")
        print("\n".join(f"  - {error}" for error in errors))
        raise SystemExit(1)
    print(f"valid: {root}")


if __name__ == "__main__":
    main()
