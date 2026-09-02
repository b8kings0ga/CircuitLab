#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from _platform import ComponentRegistry, default_data_root, validate_component


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "assets" / "catalog"
ART = ROOT / "assets" / "board-art"
STYLE = "circuitlab-ai-top-style/v1"


def edge(names: list[str], *, y: float, left: float = .12, right: float = .88) -> list[tuple[str, float, float]]:
    step = (right - left) / max(1, len(names) - 1)
    return [(name, left + index * step, y) for index, name in enumerate(names)]


def column(names: list[str], *, x: float, top: float = .10, bottom: float = .90) -> list[tuple[str, float, float]]:
    step = (bottom - top) / max(1, len(names) - 1)
    return [(name, x, top + index * step) for index, name in enumerate(names)]


FEATHER_TOP = ["BAT", "EN", "USB", "D13", "D12", "D11", "D10", "D9", "D6", "D5", "SCL", "SDA"]
FEATHER_BOTTOM = ["RST", "3V3", "AREF", "GND", "A0", "A1", "A2", "A3", "A4", "A5", "SCK", "MOSI", "MISO", "RX", "TX", "D2"]
NANO_TOP = ["D13", "3V3", "AREF", "A0", "A1", "A2", "A3", "A4/SDA", "A5/SCL", "A6", "A7", "5V", "RESET-A", "GND-A", "VIN"]
NANO_BOTTOM = ["D12", "D11", "D10", "D9", "D8", "D7", "D6", "D5", "D4", "D3", "D2", "GND-B", "RESET-B", "RX/D0", "TX/D1"]
PI40 = [
    "P1:3V3", "P2:5V", "P3:GPIO2/SDA", "P4:5V", "P5:GPIO3/SCL", "P6:GND", "P7:GPIO4", "P8:GPIO14/TX",
    "P9:GND", "P10:GPIO15/RX", "P11:GPIO17", "P12:GPIO18", "P13:GPIO27", "P14:GND", "P15:GPIO22", "P16:GPIO23",
    "P17:3V3", "P18:GPIO24", "P19:GPIO10/MOSI", "P20:GND", "P21:GPIO9/MISO", "P22:GPIO25", "P23:GPIO11/SCLK", "P24:GPIO8/CE0",
    "P25:GND", "P26:GPIO7/CE1", "P27:GPIO0/ID_SD", "P28:GPIO1/ID_SC", "P29:GPIO5", "P30:GND", "P31:GPIO6", "P32:GPIO12",
    "P33:GPIO13", "P34:GND", "P35:GPIO19", "P36:GPIO16", "P37:GPIO26", "P38:GPIO20", "P39:GND", "P40:GPIO21",
]
PICO_LEFT = ["P1:GP0", "P2:GP1", "P3:GND", "P4:GP2", "P5:GP3", "P6:GP4", "P7:GP5", "P8:GND", "P9:GP6", "P10:GP7", "P11:GP8", "P12:GP9", "P13:GND", "P14:GP10", "P15:GP11", "P16:GP12", "P17:GP13", "P18:GND", "P19:GP14", "P20:GP15"]
PICO_RIGHT = ["P40:VBUS", "P39:VSYS", "P38:GND", "P37:3V3_EN", "P36:3V3", "P35:ADC_VREF", "P34:GP28/ADC2", "P33:AGND", "P32:GP27/ADC1", "P31:GP26/ADC0", "P30:RUN", "P29:GP22", "P28:GND", "P27:GP21", "P26:GP20", "P25:GP19", "P24:GP18", "P23:GND", "P22:GP17", "P21:GP16"]


SPECS = [
    {"asset": "adafruit.feather-nrf52840-express-4062", "from": "1.0.2", "revision": "1.1.0", "art": "adafruit-feather-nrf52840-express.png", "source": "https://learn.adafruit.com/introducing-the-adafruit-nrf52840-feather/pinouts", "points": edge(FEATHER_TOP, y=.145, left=.35, right=.83) + edge(FEATHER_BOTTOM, y=.855, left=.17, right=.84)},
    {"asset": "arduino.nano-33-iot-abx00027", "from": "1.0.2", "revision": "1.1.0", "art": "arduino-nano-33-iot.png", "source": "https://docs.arduino.cc/resources/pinouts/ABX00027-full-pinout.pdf", "points": edge(NANO_TOP, y=.085, left=.10, right=.90) + edge(NANO_BOTTOM, y=.915, left=.10, right=.90)},
    {"asset": "espressif.esp32-s3-devkitc-1-v1.1", "from": "1.1.0", "revision": "1.2.0", "art": "esp32-s3-devkitc-1-v1.1.png", "source": "https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.1.html", "reusePins": True, "layout": "esp"},
    {"asset": "espressif.esp32-s3-devkitc-1-n8r8-rev1.0", "from": "1.0.1", "revision": "1.1.0", "art": "esp32-s3-devkitc-1-n8r8-v1.0.png", "source": "https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.0.html", "copyPins": "espressif.esp32-s3-devkitc-1-v1.1@1.1.0", "layout": "esp"},
    {"asset": "raspberry-pi.zero-2-wh", "from": "1.0.2", "revision": "1.1.0", "art": "raspberry-pi-zero-2-wh.png", "source": "https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio-and-the-40-pin-header", "points": edge(PI40[0::2], y=.115, left=.12, right=.82) + edge(PI40[1::2], y=.205, left=.12, right=.82)},
    {"asset": "raspberry-pi.pico-w-sc0918", "from": "1.0.0", "revision": "1.1.0", "art": "raspberry-pi-pico-w.png", "source": "https://datasheets.raspberrypi.com/picow/PicoW-A4-Pinout.pdf", "points": column(PICO_LEFT, x=.255, top=.105, bottom=.895) + column(PICO_RIGHT, x=.745, top=.105, bottom=.895)},
    {"asset": "sindri-custom.standing-desk-controller", "from": "1.0.0", "revision": "1.1.0", "art": "sindri-standing-desk-controller.png", "source": None, "reusePins": True, "layout": "edge-existing", "status": "AI_CONCEPT_TOP_PROJECT_PIN_MAP_UNVERIFIED"},
    {"asset": "sindri-custom.standing-desk-driver", "from": "1.0.0", "revision": "1.1.0", "art": "sindri-standing-desk-driver.png", "source": None, "reusePins": True, "layout": "edge-existing", "status": "AI_CONCEPT_TOP_PROJECT_PIN_MAP_UNVERIFIED"},
]


def direction(name: str) -> str:
    upper = name.upper()
    if any(token in upper for token in ("GND", "3V3", "5V", "VBUS", "VSYS", "VIN", "BAT", "AREF", "VREF")):
        return "power"
    if any(token in upper for token in ("RST", "RESET", "EN", "RUN")):
        return "input"
    return "bidirectional"


def load_package(root: Path, reference: str) -> dict:
    asset, revision = reference.rsplit("@", 1)
    return json.loads((root / asset / revision / "component-package.json").read_text(encoding="utf-8"))


def art_path(spec: dict) -> Path:
    working = ART / spec["art"]
    if working.is_file():
        return working
    installed = CATALOG / spec["asset"] / spec["revision"] / "top-view.png"
    if installed.is_file():
        return installed
    raise FileNotFoundError(f'missing generated board body: {working}')


def esp_points(pins: list[dict]) -> list[tuple[str, float, float]]:
    j1 = [pin["name"] for pin in pins if pin["name"].startswith("J1.")]
    j3 = [pin["name"] for pin in pins if pin["name"].startswith("J3.")]
    return edge(j1, y=.105, left=.14, right=.87) + edge(j3, y=.895, left=.14, right=.87)


def existing_edge_points(pins: list[dict]) -> list[tuple[str, float, float]]:
    names = [pin["name"] for pin in pins]
    split = (len(names) + 1) // 2
    return edge(names[:split], y=.10, left=.12, right=.88) + edge(names[split:], y=.90, left=.12, right=.88)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create one generated orthographic top view with complete deterministic touchpoints for each photo-backed board.")
    parser.add_argument("--registry", type=Path, default=default_data_root() / "registry" / "components")
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--data", type=Path, default=default_data_root())
    args = parser.parse_args()
    source_root = args.registry.expanduser().resolve()
    registry = ComponentRegistry(args.data.expanduser().resolve() / "registry") if args.install else None
    results = []
    for spec in SPECS:
        package = load_package(source_root, f'{spec["asset"]}@{spec["from"]}')
        if spec.get("copyPins"):
            package["electrical"]["pins"] = load_package(source_root, spec["copyPins"])["electrical"]["pins"]
        points = spec.get("points")
        if points is None:
            points = existing_edge_points(package["electrical"]["pins"]) if spec.get("layout") == "edge-existing" else esp_points(package["electrical"]["pins"])
        if not spec.get("reusePins") and not spec.get("copyPins"):
            package["electrical"] = {
                "status": "OFFICIAL_PIN_TABLE_DERIVED_UNVERIFIED",
                "pins": [{"number": str(index + 1), "name": name, "direction": direction(name), "functions": [name.split(":", 1)[-1]]} for index, (name, _, _) in enumerate(points)],
            }
        package["identity"]["revision"] = spec["revision"]
        package["identity"]["status"] = spec.get("status", "AI_DRAWN_TOP_OFFICIAL_PINS_UNVERIFIED")
        anchors = [{"pin": name, "x": round(x, 8), "y": round(y, 8), "status": "OFFICIAL_PIN_TABLE_VISUAL_ALIGNMENT_UNVERIFIED"} for name, x, y in points]
        source_art = art_path(spec)
        art = source_art.read_bytes()
        package["visual"] = {
            "appearance": "top-view.png", "appearanceSha256": hashlib.sha256(art).hexdigest(),
            "style": STYLE, "coordinateStatus": "OFFICIAL_PIN_TABLE_VISUAL_ALIGNMENT_UNVERIFIED",
            "anchors": anchors, "views": [{"name": "interactive-top", "view": "ai-drawn-orthographic-top", "path": "top-view.png"}],
        }
        if spec.get("source"):
            package.setdefault("evidence", {}).setdefault("sources", []).append({"type": "manufacturer-pin-table", "url": spec["source"]})
        package["evidence"].update({
            "rendering": "IMAGEGEN_BOARD_BODY_WITH_DETERMINISTIC_OFFICIAL_PIN_OVERLAY",
            "generatedBodySha256": hashlib.sha256(art).hexdigest(),
            "physicalStatus": "PHYSICAL_UNVERIFIED",
        })
        validate_component(package)
        output = CATALOG / spec["asset"] / spec["revision"]
        output.mkdir(parents=True, exist_ok=True)
        destination = output / "top-view.png"
        if source_art.resolve() != destination.resolve():
            shutil.copy2(source_art, destination)
        (output / "component-package.json").write_text(json.dumps(package, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result = {"ref": f'{spec["asset"]}@{spec["revision"]}', "pins": len(package["electrical"]["pins"]), "anchors": len(anchors)}
        if registry:
            result["install"] = registry.install(package, {"top-view.png": art})["status"]
        results.append(result)
    print(json.dumps({"style": STYLE, "boards": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
