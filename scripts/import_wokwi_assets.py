#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = SKILL_ROOT / "assets" / "template" / "core" / "web" / "vendor" / "wokwi"


def run(*command: str, cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def revision(source: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()


def component_tags(source: Path) -> list[str]:
    pattern = re.compile(r"@customElement\(['\"]([^'\"]+)['\"]\)")
    tags = set()
    for path in (source / "src").glob("*-element.ts"):
        tags.update(pattern.findall(path.read_text(encoding="utf-8")))
    return sorted(tags)


def component_catalog(bundle: Path, tags: list[str]) -> list[dict[str, Any]]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page()
        page.set_content("<!doctype html><body></body>")
        page.add_script_tag(path=str(bundle))
        catalog = page.evaluate(
            """async (tags) => {
              const result = [];
              for (const tag of tags) {
                const row = { type: tag, pins: [], geometry: null, error: null };
                try {
                  const element = document.createElement(tag);
                  document.body.appendChild(element);
                  if (element.updateComplete) await element.updateComplete;
                  await new Promise(resolve => requestAnimationFrame(resolve));
                  const svg = element.shadowRoot?.querySelector('svg');
                  const pins = [...(element.pinInfo || [])].map(pin => ({
                    name: String(pin.name),
                    x: Number.isFinite(pin.x) ? pin.x : null,
                    y: Number.isFinite(pin.y) ? pin.y : null,
                    signals: pin.signals || null,
                    visible: Number.isFinite(pin.x) && Number.isFinite(pin.y),
                  }));
                  row.pins = pins;
                  if (svg) {
                    const box = svg.viewBox?.baseVal;
                    row.geometry = {
                      width: svg.width?.baseVal?.value || box?.width || null,
                      height: svg.height?.baseVal?.value || box?.height || null,
                      viewBox: box ? [box.x, box.y, box.width, box.height] : null,
                    };
                  }
                  element.remove();
                } catch (error) {
                  row.error = String(error?.message || error);
                }
                result.push(row);
              }
              return result;
            }""",
            tags,
        )
        browser.close()
        return catalog


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def board_catalog(board_id: str, definition: dict[str, Any]) -> dict[str, Any]:
    pins = definition.get("pins", {})
    if isinstance(pins, dict):
        entries = [{"name": name, **value} for name, value in pins.items()]
    else:
        entries = list(pins)
    normalized = []
    for pin in entries:
        x, y = pin.get("x"), pin.get("y")
        normalized.append({
            "name": str(pin.get("name", "")),
            "x": x if isinstance(x, (int, float)) else None,
            "y": y if isinstance(y, (int, float)) else None,
            "target": pin.get("target"),
            "visible": isinstance(x, (int, float)) and isinstance(y, (int, float)),
        })
    return {
        "id": board_id,
        "name": definition.get("name", board_id),
        "width": definition.get("width"),
        "height": definition.get("height"),
        "pins": normalized,
        "visiblePinCount": sum(pin["visible"] for pin in normalized),
    }


def build_manifest(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import and catalog official Wokwi local assets.")
    parser.add_argument("--elements-source", type=Path, required=True)
    parser.add_argument("--boards-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    elements = args.elements_source.expanduser().resolve()
    boards = args.boards_source.expanduser().resolve()
    output = args.output.expanduser().resolve()

    if not args.skip_build:
        run("npm", "ci", cwd=elements)
        run("npm", "run", "build", cwd=elements)
        run("npm", "ci", cwd=boards / "tools")
    for generated in (boards / "boards" / "bundle.json", boards / "boards" / "boards.json"):
        generated.unlink(missing_ok=True)
    run("node", "tools/make-bundle.js", cwd=boards)

    temporary = output.with_name(f".{output.name}.tmp")
    shutil.rmtree(temporary, ignore_errors=True)
    element_out = temporary / "elements"
    board_out = temporary / "boards"
    element_out.mkdir(parents=True)
    board_out.mkdir(parents=True)

    bundle = elements / "dist" / "wokwi-elements.bundle.min.js"
    tags = component_tags(elements)
    components = component_catalog(bundle, tags)
    shutil.copy2(bundle, element_out / "wokwi-elements.bundle.min.js")
    shutil.copy2(elements / "LICENSE", element_out / "LICENSE")
    write_json(element_out / "catalog.json", {
        "schemaVersion": 1,
        "package": "@wokwi/elements",
        "version": json.loads((elements / "package.json").read_text())["version"],
        "revision": revision(elements),
        "components": components,
    })

    board_bundle = json.loads((boards / "boards" / "bundle.json").read_text(encoding="utf-8"))
    board_rows = []
    for board_id, payload in sorted(board_bundle.items()):
        destination = board_out / board_id
        destination.mkdir()
        write_json(destination / "board.json", payload["def"])
        (destination / "board.svg").write_text(payload["svg"], encoding="utf-8")
        row = board_catalog(board_id, payload["def"])
        row["revision"] = payload.get("rev")
        board_rows.append(row)
    write_json(board_out / "catalog.json", {
        "schemaVersion": 1,
        "license": "local-only; upstream repository has no root LICENSE",
        "revision": revision(boards),
        "boards": board_rows,
    })
    write_json(temporary / "sources.json", {
        "schemaVersion": 1,
        "elements": {
            "url": "https://github.com/wokwi/wokwi-elements",
            "revision": revision(elements),
            "license": "MIT",
        },
        "boards": {
            "url": "https://github.com/wokwi/wokwi-boards",
            "revision": revision(boards),
            "license": "local-only; review before redistribution",
        },
    })
    (temporary / "README.md").write_text(
        "# Managed Wokwi assets\n\n"
        "- `elements/` contains the MIT-licensed `@wokwi/elements` browser bundle and a runtime-generated component/pin catalog.\n"
        "- `boards/` contains normalized local copies of official board SVG/JSON definitions and a visible/virtual pin catalog.\n"
        "- `sources.json` pins both upstream Git revisions.\n"
        "- `manifest.json` contains SHA-256 checksums for every imported file.\n\n"
        "The upstream `wokwi-boards` repository has no root license file. Treat all board assets as local-only and review licensing before redistribution.\n",
        encoding="utf-8",
    )
    write_json(temporary / "manifest.json", {
        "schemaVersion": 1,
        "files": build_manifest(temporary),
    })
    shutil.rmtree(output, ignore_errors=True)
    temporary.replace(output)
    print(json.dumps({
        "output": str(output),
        "components": len(components),
        "componentPins": sum(len(row["pins"]) for row in components),
        "boards": len(board_rows),
        "boardPins": sum(len(row["pins"]) for row in board_rows),
    }))


if __name__ == "__main__":
    main()
