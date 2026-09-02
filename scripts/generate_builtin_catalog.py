#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
from typing import Any

from _platform import ComponentRegistry, default_data_root


SOURCES = {
    "orange-pi-zero-3": "https://www.orangepi.org/orangepiwiki/index.php/Orange_Pi_Zero_3",
    "vl53l1x": "https://learn.adafruit.com/adafruit-vl53l1x/pinouts",
    "lis3mdl": "https://learn.adafruit.com/lis3mdl-triple-axis-magnetometer/pinouts",
    "bme688": "https://learn.adafruit.com/adafruit-bme680-humidity-temperature-barometic-pressure-voc-gas/pinouts",
    "sph0645": "https://learn.adafruit.com/adafruit-i2s-mems-microphone-breakout/pinouts",
    "oled": "https://www.waveshare.com/wiki/0.96inch_OLED_(B)",
}


def pin(name: str, number: str, x: float, y: float, side: str, direction: str = "bidirectional", functions: list[str] | None = None) -> dict[str, Any]:
    return {"name": name, "number": number, "x": x, "y": y, "side": side, "direction": direction, "functions": functions or []}


def orange_pi_pins() -> list[dict[str, Any]]:
    labels = {
        1: ("P01_3V3", "3V3"), 2: ("P02_5V", "5V"), 3: ("P03_SDA", "PH5 / SDA"), 4: ("P04_5V", "5V"),
        5: ("P05_SCL", "PH4 / SCL"), 6: ("P06_GND", "GND"), 7: ("P07_PC9", "PC9"), 8: ("P08_TX", "PH2 / TX"),
        9: ("P09_GND", "GND"), 10: ("P10_RX", "PH3 / RX"), 11: ("P11_PC6", "PC6"), 12: ("P12_PC11", "PC11"),
        13: ("P13_PC5", "PC5"), 14: ("P14_GND", "GND"), 15: ("P15_PC8", "PC8"), 16: ("P16_PC15", "PC15"),
        17: ("P17_3V3", "3V3"), 18: ("P18_PC14", "PC14"), 19: ("P19_MOSI", "PH7 / MOSI"), 20: ("P20_GND", "GND"),
        21: ("P21_MISO", "PH8 / MISO"), 22: ("P22_PC7", "PC7"), 23: ("P23_CLK", "PH6 / CLK"), 24: ("P24_CS", "PH9 / CS"),
        25: ("P25_GND", "GND"), 26: ("P26_PC10", "PC10"),
    }
    rows: list[dict[str, Any]] = []
    for number in range(1, 27):
        column = 0 if number % 2 else 1
        row = (number - 1) // 2
        name, label = labels[number]
        direction = "power" if label in {"3V3", "5V", "GND"} else "bidirectional"
        rows.append(pin(name, str(number), 42 + column * 4, 12 + row * 3.0, "right", direction, [label]))
    return rows


CATALOG: list[dict[str, Any]] = [
    {
        "assetId": "orange-pi.zero-3-v1.3", "revision": "1.0.2", "manufacturer": "Shenzhen Xunlong Software", "mpn": "Orange Pi Zero 3 v1.3",
        "level": "linux-single-board-computer", "width": 50, "height": 55, "canvasWidth": 130, "color": "#e86b1f", "accent": "#202421",
        "subtitle": "H618 · 26-PIN GPIO", "source": SOURCES["orange-pi-zero-3"], "pins": orange_pi_pins(),
        "parts": [(8, 9, 27, 27, "H618"), (8, 39, 20, 10, "LPDDR4"), (35, 5, 12, 16, "RJ45"), (35, 26, 12, 8, "USB-C")],
    },
    {
        "assetId": "adafruit.vl53l1x-3967", "revision": "1.0.0", "manufacturer": "Adafruit Industries", "mpn": "VL53L1X ToF #3967",
        "level": "distance-sensor-module", "width": 25.4, "height": 17.8, "canvasWidth": 48, "color": "#161b19", "accent": "#e9e9e4",
        "subtitle": "DISTANCE · I²C 0x29", "source": SOURCES["vl53l1x"],
        "pins": [pin(n, str(i + 1), 2.4 + i * 4.1, 15.4, "bottom", d) for i, (n, d) in enumerate([("VIN", "power"), ("GND", "power"), ("SCL", "input"), ("SDA", "bidirectional"), ("GPIO", "output"), ("XSHUT", "input")])],
        "parts": [(8.6, 4.0, 8.2, 7.2, "TOF")],
    },
    {
        "assetId": "adafruit.lis3mdl-4479", "revision": "1.0.0", "manufacturer": "Adafruit Industries", "mpn": "LIS3MDL #4479",
        "level": "magnetometer-module", "width": 25.4, "height": 17.8, "canvasWidth": 48, "color": "#171c1a", "accent": "#eeeeea",
        "subtitle": "MAGNETIC · I²C / SPI", "source": SOURCES["lis3mdl"],
        "pins": [pin(n, str(i + 1), 2.0 + i * 2.65, 15.4, "bottom", d) for i, (n, d) in enumerate([("VIN", "power"), ("3VO", "power"), ("GND", "power"), ("SCL", "input"), ("SDA", "bidirectional"), ("DO", "output"), ("CS", "input"), ("INT", "output"), ("DRDY", "output")])],
        "parts": [(9.1, 4.4, 7.2, 7.2, "MAG")],
    },
    {
        "assetId": "adafruit.bme688-5046", "revision": "1.0.0", "manufacturer": "Adafruit Industries", "mpn": "BME688 #5046",
        "level": "voc-gas-sensor-module", "width": 25.4, "height": 17.8, "canvasWidth": 48, "color": "#151a18", "accent": "#efefea",
        "subtitle": "GAS / VOC · I²C / SPI", "source": SOURCES["bme688"],
        "pins": [pin(n, str(i + 1), 2.6 + i * 3.35, 15.4, "bottom", d) for i, (n, d) in enumerate([("VIN", "power"), ("3VO", "power"), ("GND", "power"), ("SCK", "input"), ("SDO", "output"), ("SDI", "bidirectional"), ("CS", "input")])],
        "parts": [(9.4, 4.2, 6.6, 6.6, "VOC")],
    },
    {
        "assetId": "adafruit.sph0645lm4h-3421", "revision": "1.0.0", "manufacturer": "Adafruit Industries", "mpn": "SPH0645LM4H #3421",
        "level": "digital-microphone-module", "width": 22.9, "height": 15.2, "canvasWidth": 46, "color": "#171b19", "accent": "#eceee9",
        "subtitle": "SOUND · DIGITAL I²S", "source": SOURCES["sph0645"],
        "pins": [pin(n, str(i + 1), 2.2 + i * 3.7, 13.0, "bottom", d) for i, (n, d) in enumerate([("3V", "power"), ("GND", "power"), ("BCLK", "input"), ("DOUT", "output"), ("LRCLK", "input"), ("SEL", "input")])],
        "parts": [(8.3, 3.3, 6.2, 6.2, "MIC")],
    },
    {
        "assetId": "waveshare.0.96inch-oled-b", "revision": "1.1.0", "manufacturer": "Waveshare", "mpn": "0.96inch OLED (B)",
        "level": "oled-display-module", "width": 33.0, "height": 33.5, "canvasWidth": 58, "color": "#184a7d", "accent": "#09131e",
        "subtitle": "DISPLAY · 128×64 · SPI / I²C", "source": SOURCES["oled"],
        "pins": [pin(n, str(i + 1), 2.5 + i * 3.95, 31.0, "bottom", d) for i, (n, d) in enumerate([("VCC", "power"), ("GND", "power"), ("NC", "input"), ("DIN", "input"), ("CLK", "input"), ("CS", "input"), ("D/C", "input"), ("RES", "input")])],
        "parts": [(5.6, 4.2, 21.7, 14.2, "OLED 128×64")],
    },
]


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def render(spec: dict[str, Any]) -> str:
    scale = 8
    physical_width = spec["width"]
    canvas_width = spec["canvasWidth"]
    height = spec["height"] + 11
    offset_x = (canvas_width - physical_width) / 2
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_width * scale:g} {height * scale:g}" role="img" aria-label="{esc(spec["mpn"])} interactive top view">',
        '<defs><filter id="s" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="3" stdDeviation="3" flood-opacity=".35"/></filter></defs>',
        f'<rect x="{offset_x * scale:g}" y="{3 * scale:g}" width="{physical_width * scale:g}" height="{spec["height"] * scale:g}" rx="9" fill="{spec["color"]}" stroke="#7d867f" stroke-width="2" filter="url(#s)"/>',
        f'<text x="{canvas_width * scale / 2:g}" y="{(spec["height"] + 8) * scale:g}" text-anchor="middle" fill="#dce4de" font-family="ui-monospace,monospace" font-size="11" font-weight="700">{esc(spec["mpn"])}</text>',
        f'<text x="{canvas_width * scale / 2:g}" y="{(spec["height"] + 10) * scale:g}" text-anchor="middle" fill="#77e39d" font-family="ui-monospace,monospace" font-size="7">{esc(spec["subtitle"])}</text>',
    ]
    for x, y, width, part_height, label in spec["parts"]:
        px = (offset_x + x) * scale; py = (3 + y) * scale
        lines.append(f'<rect x="{px:g}" y="{py:g}" width="{width * scale:g}" height="{part_height * scale:g}" rx="5" fill="{spec["accent"]}" stroke="#9ca49f" stroke-width="1.5"/>')
        lines.append(f'<text x="{px + width * scale / 2:g}" y="{py + part_height * scale / 2 + 3:g}" text-anchor="middle" fill="#222925" font-family="ui-monospace,monospace" font-size="8" font-weight="800">{esc(label)}</text>')
    for index, row in enumerate(spec["pins"]):
        x = (offset_x + row["x"]) * scale; y = (3 + row["y"]) * scale
        label = row["functions"][0] if spec["assetId"].startswith("orange-pi") else row["name"]
        lines.extend([
            f'<g id="pin-{esc(row["name"])}" data-pin="{esc(row["name"])}">',
            f'<circle cx="{x:g}" cy="{y:g}" r="7.2" fill="#d3a321" stroke="#ffe580" stroke-width="1.3"/>',
            f'<circle cx="{x:g}" cy="{y:g}" r="3.2" fill="#3e4641"/>',
        ])
        if spec["assetId"].startswith("orange-pi"):
            tx = (offset_x + physical_width + 4 + (index % 2) * 15) * scale
            lines.append(f'<text x="{tx:g}" y="{y + 2.5:g}" fill="#dce4de" font-family="ui-monospace,monospace" font-size="6.5">{esc(row["number"])} {esc(label)}</text>')
        else:
            lines.append(f'<text x="{x:g}" y="{(3 + spec["height"] + 2.2) * scale:g}" text-anchor="middle" fill="#f5d66e" font-family="ui-monospace,monospace" font-size="6.5" font-weight="700">{esc(label)}</text>')
        lines.append('</g>')
    lines.append('</svg>')
    return "\n".join(lines) + "\n"


def package_for(spec: dict[str, Any], svg: bytes) -> dict[str, Any]:
    canvas_width = float(spec["canvasWidth"]); height = float(spec["height"] + 11); offset_x = (canvas_width - float(spec["width"])) / 2
    return {
        "schema": "component-package/v1",
        "identity": {"assetId": spec["assetId"], "revision": spec["revision"], "manufacturer": spec["manufacturer"], "mpn": spec["mpn"], "level": spec["level"], "status": "DESIGN_DOC_DERIVED_UNVERIFIED", "lifecycle": "active"},
        "electrical": {"status": "OFFICIAL_PIN_TABLE_DERIVED_UNVERIFIED", "pins": [{key: row[key] for key in ("name", "number", "direction", "functions")} for row in spec["pins"]]},
        "visual": {"appearance": "top.svg", "appearanceSha256": hashlib.sha256(svg).hexdigest(), "coordinateStatus": "DOCUMENTED_PIN_TABLE_VISUAL_LAYOUT_UNVERIFIED", "anchors": [{"pin": row["name"], "x": round((offset_x + row["x"]) / canvas_width, 8), "y": round((3 + row["y"]) / height, 8), "status": "DOCUMENTED_PIN_TABLE_VISUAL_LAYOUT_UNVERIFIED"} for row in spec["pins"]], "views": [{"name": "interactive-top", "view": "original-vector-top", "path": "top.svg"}]},
        "physical": {"widthMm": spec["width"], "heightMm": spec["height"], "package": "assembled-module"},
        "evidence": {"capturedAt": "2026-09-02T00:00:00Z", "sources": [{"type": "manufacturer-pinout-documentation", "url": spec["source"]}], "rendering": "ORIGINAL_CIRCUITLAB_VECTOR_FROM_OFFICIAL_PIN_TABLE_NOT_PHOTO_TRACE"},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the redistributable CircuitLab starter hardware catalog.")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "assets" / "catalog")
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--data", type=Path, default=default_data_root())
    args = parser.parse_args()
    output = args.output.expanduser().resolve(); output.mkdir(parents=True, exist_ok=True)
    registry = ComponentRegistry(args.data.expanduser().resolve() / "registry") if args.install else None
    results = []
    for spec in CATALOG:
        directory = output / spec["assetId"] / spec["revision"]
        directory.mkdir(parents=True, exist_ok=True)
        svg = render(spec).encode("utf-8")
        package = package_for(spec, svg)
        (directory / "top.svg").write_bytes(svg)
        (directory / "component-package.json").write_text(json.dumps(package, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result = {"ref": f'{spec["assetId"]}@{spec["revision"]}', "pins": len(spec["pins"])}
        if registry is not None:
            result["install"] = registry.install(package, {"top.svg": svg})["status"]
        results.append(result)
    xiao_source = Path(__file__).resolve().parents[1] / "docs" / "generated" / "xiao-esp32s3"
    xiao_package = json.loads((xiao_source / "component-package.json").read_text(encoding="utf-8"))
    xiao_package["identity"]["revision"] = "1.2.0"
    xiao_package["evidence"]["capturedAt"] = "2026-09-02T00:00:00Z"
    xiao_files = {name: (xiao_source / name).read_bytes() for name in ("board.svg", "board.json")}
    xiao_directory = output / xiao_package["identity"]["assetId"] / xiao_package["identity"]["revision"]
    xiao_directory.mkdir(parents=True, exist_ok=True)
    for name, body in xiao_files.items():
        (xiao_directory / name).write_bytes(body)
    (xiao_directory / "component-package.json").write_text(json.dumps(xiao_package, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    xiao_result = {"ref": "seeed.xiao-esp32s3@1.2.0", "pins": len(xiao_package["electrical"]["pins"])}
    if registry is not None:
        xiao_result["install"] = registry.install(xiao_package, xiao_files)["status"]
    results.append(xiao_result)
    catalog_rows = [{"ref": row["ref"], "pins": row["pins"]} for row in results]
    (output / "index.json").write_text(json.dumps({"schema": "circuitlab-catalog/v1", "components": catalog_rows}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "components": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
