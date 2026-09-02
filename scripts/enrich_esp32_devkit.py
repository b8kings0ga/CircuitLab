#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from _platform import ComponentRegistry, default_data_root


SOURCE_REF = "espressif.esp32-s3-devkitc-1-v1.1@1.0.2"
TARGET_REVISION = "1.1.0"
OFFICIAL_GUIDE = "https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.1.html"

J1 = [
    ("3V3", "3.3 V power"), ("3V3", "3.3 V power"), ("RST", "EN reset"), ("GPIO4", "ADC1_CH3 TOUCH4"),
    ("GPIO5", "ADC1_CH4 TOUCH5"), ("GPIO6", "ADC1_CH5 TOUCH6"), ("GPIO7", "ADC1_CH6 TOUCH7"),
    ("GPIO15", "ADC2_CH4 TOUCH15"), ("GPIO16", "ADC2_CH5"), ("GPIO17", "U1TXD ADC2_CH6"),
    ("GPIO18", "U1RXD ADC2_CH7"), ("GPIO8", "ADC1_CH7 TOUCH8"), ("GPIO3", "ADC1_CH2 TOUCH3"),
    ("GPIO46", "GPIO46"), ("GPIO9", "FSPIHD ADC1_CH8"), ("GPIO10", "FSPICS0 ADC1_CH9"),
    ("GPIO11", "FSPID ADC2_CH0"), ("GPIO12", "FSPICLK ADC2_CH1"), ("GPIO13", "FSPIQ ADC2_CH2"),
    ("GPIO14", "FSPIWP ADC2_CH3"), ("5V", "5 V power"), ("GND", "ground"),
]
J3 = [
    ("GND", "ground"), ("GPIO43", "U0TXD"), ("GPIO44", "U0RXD"), ("GPIO1", "ADC1_CH0 TOUCH1"),
    ("GPIO2", "ADC1_CH1 TOUCH2"), ("GPIO42", "MTMS"), ("GPIO41", "MTDI"), ("GPIO40", "MTDO"),
    ("GPIO39", "MTCK"), ("GPIO38", "RGB LED FSPIWP"), ("GPIO37", "SPIDQS FSPIQ"),
    ("GPIO36", "SPIIO7 FSPICLK"), ("GPIO35", "SPIIO6 FSPID"), ("GPIO0", "BOOT"),
    ("GPIO45", "GPIO45"), ("GPIO48", "SPICLK_N"), ("GPIO47", "SPICLK_P"), ("GPIO21", "GPIO21"),
    ("GPIO20", "USB_D+ ADC2_CH9"), ("GPIO19", "USB_D- ADC2_CH8"), ("GND", "ground"), ("GND", "ground"),
]


def rows(header: str, values: list[tuple[str, str]]) -> list[dict[str, object]]:
    result = []
    for number, (label, functions) in enumerate(values, 1):
        power = label in {"3V3", "5V", "GND"}
        result.append({
            "name": f"{header}.{number}:{label}",
            "number": f"{header}.{number}",
            "direction": "power" if power else ("input" if label == "RST" else "bidirectional"),
            "functions": functions.split(),
        })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Add the official ESP32-S3-DevKitC-1 v1.1 J1/J3 pin table without changing imported media.")
    parser.add_argument("--data", type=Path, default=default_data_root())
    args = parser.parse_args()
    registry = ComponentRegistry(args.data.expanduser().resolve() / "registry")
    source = registry.get(SOURCE_REF)
    target = copy.deepcopy(source)
    target.pop("packageSha256", None); target.pop("procurement", None)
    target["identity"]["revision"] = TARGET_REVISION
    target["identity"]["status"] = "OFFICIAL_PIN_TABLE_DERIVED_UNVERIFIED"
    target["electrical"] = {"status": "OFFICIAL_PIN_TABLE_DERIVED_UNVERIFIED", "pins": rows("J1", J1) + rows("J3", J3)}
    target["evidence"].setdefault("sources", []).append({"type": "manufacturer-pin-table", "url": OFFICIAL_GUIDE, "boardRevision": "v1.1"})
    target["evidence"]["enrichment"] = "PIN_TABLE_ONLY_MEDIA_BYTES_PRESERVED"
    source_dir = registry.package_path(SOURCE_REF).parent
    visual = target.get("visual", {})
    names = {visual.get("appearance"), visual.get("symbol"), visual.get("geometry")}
    names.update(row.get("path") for row in visual.get("views", []) if isinstance(row, dict))
    files = {name: (source_dir / name).read_bytes() for name in names if isinstance(name, str) and (source_dir / name).is_file()}
    print(json.dumps(registry.install(target, files), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
