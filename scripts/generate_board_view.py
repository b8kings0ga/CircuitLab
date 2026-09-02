#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
from typing import Any

from _platform import ComponentRegistry, default_data_root


SCALE = 10.0


def load_spec(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "board-view-spec/v1":
        raise ValueError("board view spec must use board-view-spec/v1")
    width = float(value.get("canvas", {}).get("widthMm", 0))
    height = float(value.get("canvas", {}).get("heightMm", 0))
    if not 1 <= width <= 500 or not 1 <= height <= 500:
        raise ValueError("board canvas dimensions must be between 1 and 500 mm")
    pins = value.get("pins")
    if not isinstance(pins, list) or not pins:
        raise ValueError("board view spec requires pins")
    names: set[str] = set()
    for pin in pins:
        name = str(pin.get("name", ""))
        if not name or name in names:
            raise ValueError(f"invalid or duplicate pin name: {name!r}")
        names.add(name)
        for coordinate, maximum in (("xMm", width), ("yMm", height)):
            number = pin.get(coordinate)
            if not isinstance(number, (int, float)) or isinstance(number, bool) or not 0 <= number <= maximum:
                raise ValueError(f"pin {name} {coordinate} is outside the canvas")
    return value


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def mm(value: object) -> float:
    return round(float(value) * SCALE, 4)


def render_svg(spec: dict[str, Any]) -> str:
    canvas = spec["canvas"]
    width = mm(canvas["widthMm"])
    height = mm(canvas["heightMm"])
    pcb = spec.get("pcb", {})
    x = mm(pcb.get("xMm", 0.15)); y = mm(pcb.get("yMm", 2.35))
    board_width = mm(pcb.get("widthMm", float(canvas["widthMm"]) - 0.3))
    board_height = mm(pcb.get("heightMm", float(canvas["heightMm"]) - float(pcb.get("yMm", 2.35))))
    title = esc(spec["identity"]["mpn"])
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:g} {height:g}" role="img" aria-label="{title} interactive top view">',
        '<defs>',
        '<linearGradient id="usb" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#f4f5f4"/><stop offset="1" stop-color="#aeb4b1"/></linearGradient>',
        '<linearGradient id="shield" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#eeeeec"/><stop offset=".55" stop-color="#b9bfbc"/><stop offset="1" stop-color="#8d9490"/></linearGradient>',
        '<filter id="shadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity=".35"/></filter>',
        '</defs>',
        f'<path d="M{x + 9:g} {y:g}H{x + board_width - 9:g}Q{x + board_width:g} {y:g} {x + board_width:g} {y + 9:g}V{y + board_height - 9:g}Q{x + board_width:g} {y + board_height:g} {x + board_width - 9:g} {y + board_height:g}H{x + 9:g}Q{x:g} {y + board_height:g} {x:g} {y + board_height - 9:g}V{y + 9:g}Q{x:g} {y:g} {x + 9:g} {y:g}Z" fill="#f7f8f5" stroke="#c7cdc8" stroke-width="2" filter="url(#shadow)"/>',
    ]
    usb = spec.get("usb", {})
    ux = mm(usb.get("xMm", 4.8)); uy = mm(usb.get("yMm", 0)); uw = mm(usb.get("widthMm", 8.5)); uh = mm(usb.get("heightMm", 3.8))
    lines += [
        f'<rect x="{ux:g}" y="{uy:g}" width="{uw:g}" height="{uh:g}" rx="5" fill="url(#usb)" stroke="#777f7b" stroke-width="1.5"/>',
        f'<rect x="{ux + 10:g}" y="{uy + 8:g}" width="{uw - 20:g}" height="{max(8, uh - 18):g}" rx="3" fill="#202523"/>',
        f'<g fill="#c99019"><rect x="{ux + 20:g}" y="{uy + uh - 7:g}" width="5" height="7"/><rect x="{ux + uw - 25:g}" y="{uy + uh - 7:g}" width="5" height="7"/></g>',
    ]
    shield = spec.get("shield", {})
    sx = mm(shield.get("xMm", 5.2)); sy = mm(shield.get("yMm", 7.5)); sw = mm(shield.get("widthMm", 7.7)); sh = mm(shield.get("heightMm", 8.5))
    lines += [
        f'<rect x="{sx:g}" y="{sy:g}" width="{sw:g}" height="{sh:g}" rx="4" fill="url(#shield)" stroke="#929995" stroke-width="1.2"/>',
        f'<text x="{sx + sw / 2:g}" y="{sy + sh / 2 - 3:g}" text-anchor="middle" fill="#39403c" font-family="ui-monospace,monospace" font-size="8" font-weight="700">ESP32-S3</text>',
        f'<text x="{sx + sw / 2:g}" y="{sy + sh / 2 + 8:g}" text-anchor="middle" fill="#626a65" font-family="ui-monospace,monospace" font-size="5.5">8MB PSRAM · 8MB FLASH</text>',
    ]
    lines += [
        f'<text x="{width / 2:g}" y="{mm(6.25):g}" text-anchor="middle" fill="#101512" font-family="ui-monospace,monospace" font-size="9" font-weight="700">XIAO ESP32-S3</text>',
        f'<text x="{width / 2:g}" y="{mm(17.45):g}" text-anchor="middle" fill="#303732" font-family="ui-monospace,monospace" font-size="6">DESIGN-DOC DERIVED</text>',
        f'<rect x="{mm(5.15):g}" y="{mm(19.1):g}" width="{mm(7.8):g}" height="{mm(2.1):g}" rx="2" fill="#161b19"/>',
    ]
    for index in range(14):
        px = mm(5.55 + index * 0.52)
        lines.append(f'<rect x="{px:g}" y="{mm(19.35):g}" width="3.2" height="{mm(1.6):g}" fill="#d8a91e"/>')
    for pin in spec["pins"]:
        px = mm(pin["xMm"]); py = mm(pin["yMm"])
        name = esc(pin["name"]); side = pin.get("side", "left")
        label_x = px + 13 if side == "left" else px - 13
        anchor = "start" if side == "left" else "end"
        lines += [
            f'<g id="pin-{name}" data-pin="{name}">',
            f'<circle cx="{px:g}" cy="{py:g}" r="8.4" fill="#d5a413" stroke="#ffe37a" stroke-width="1.4"/>',
            f'<circle cx="{px:g}" cy="{py:g}" r="5.2" fill="#fafbf8" stroke="#c5cbc7" stroke-width="1"/>',
            f'<circle cx="{px:g}" cy="{py:g}" r="2.25" fill="#4b5350"/>',
            f'<text x="{label_x:g}" y="{py + 2.5:g}" text-anchor="{anchor}" fill="#111613" font-family="ui-monospace,monospace" font-size="6.5" font-weight="700">{name}</text>',
            '</g>',
        ]
    lines.append('</svg>')
    return "\n".join(lines) + "\n"


def build(spec: dict[str, Any], output: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    output.mkdir(parents=True, exist_ok=True)
    svg = render_svg(spec).encode("utf-8")
    width = float(spec["canvas"]["widthMm"]); height = float(spec["canvas"]["heightMm"])
    geometry = {
        "schema": "interactive-board/v1",
        "name": spec["identity"]["mpn"],
        "width": width,
        "height": height,
        "units": "mm",
        "orientation": spec.get("orientation", "FRONT · USB"),
        "coordinateStatus": "OFFICIAL_DESIGN_DERIVED_UNVERIFIED",
        "pins": {pin["name"]: {"x": pin["xMm"], "y": pin["yMm"], "number": str(pin.get("number", pin["name"]))} for pin in spec["pins"]},
    }
    svg_path = output / "board.svg"; json_path = output / "board.json"
    svg_path.write_bytes(svg)
    json_path.write_text(json.dumps(geometry, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    package = {
        "schema": "component-package/v1",
        "identity": {**spec["identity"], "status": "DESIGN_DOC_DERIVED_UNVERIFIED"},
        "electrical": {
            "status": "UNVERIFIED",
            "pins": [{"name": pin["name"], "number": str(pin.get("number", pin["name"])), "direction": pin.get("direction", "bidirectional"), "functions": pin.get("functions", [])} for pin in spec["pins"]],
        },
        "visual": {
            "appearance": "board.svg",
            "appearanceSha256": hashlib.sha256(svg).hexdigest(),
            "coordinateStatus": "OFFICIAL_DESIGN_DERIVED_UNVERIFIED",
            "anchors": [{"pin": pin["name"], "x": round(float(pin["xMm"]) / width, 8), "y": round(float(pin["yMm"]) / height, 8), "status": "OFFICIAL_DESIGN_DERIVED_UNVERIFIED"} for pin in spec["pins"]],
            "views": [{"name": "interactive-top", "view": "interactive-top", "path": "board.svg"}],
            "geometry": "board.json",
        },
        "physical": {"widthMm": spec.get("pcb", {}).get("widthMm"), "heightMm": spec.get("pcb", {}).get("heightMm"), "geometry": "board.json"},
        "evidence": {"sources": spec.get("evidence", {}).get("sources", []), "rendering": "ORIGINAL_CIRCUITLAB_VECTOR_FROM_EXPLICIT_DESIGN_COORDINATES", "specSha256": hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()).hexdigest()},
    }
    package_path = output / "component-package.json"
    package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return package, geometry


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a CircuitLab interactive board SVG from explicit design coordinates.")
    parser.add_argument("spec", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--install", action="store_true", help="Install the generated immutable component revision.")
    parser.add_argument("--data-root", type=Path, default=default_data_root())
    args = parser.parse_args()
    spec = load_spec(args.spec.expanduser().resolve())
    output = args.output.expanduser().resolve()
    package, geometry = build(spec, output)
    result: dict[str, Any] = {"output": str(output), "pins": len(geometry["pins"]), "coordinateStatus": geometry["coordinateStatus"]}
    if args.install:
        registry = ComponentRegistry(args.data_root.expanduser().resolve() / "registry")
        installed = registry.install(package, {"board.svg": (output / "board.svg").read_bytes(), "board.json": (output / "board.json").read_bytes()})
        result["install"] = installed
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
