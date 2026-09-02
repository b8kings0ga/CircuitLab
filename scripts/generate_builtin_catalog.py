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
    "veml7700": "https://learn.adafruit.com/adafruit-veml7700?view=all",
    "apds9960": "https://learn.adafruit.com/adafruit-apds9960-breakout?view=all",
    "sht45": "https://learn.adafruit.com/adafruit-sht40-temperature-humidity-sensor?view=all",
    "scd40": "https://learn.adafruit.com/adafruit-scd-40-and-scd-41/pinouts",
    "bme280": "https://learn.adafruit.com/adafruit-bme280-humidity-barometric-pressure-temperature-sensor-breakout/pinouts",
    "aht20": "https://learn.adafruit.com/adafruit-aht20/pinouts",
    "mpu6050": "https://learn.adafruit.com/mpu6050-6-dof-accelerometer-and-gyro/pinouts",
    "lis3dh": "https://learn.adafruit.com/adafruit-lis3dh-triple-axis-accelerometer-breakout/pinouts",
    "ltr390": "https://learn.adafruit.com/adafruit-ltr390-uv-sensor/pinouts-2",
    "vl53l0x": "https://learn.adafruit.com/adafruit-vl53l0x-micro-lidar-distance-sensor-breakout/pinouts",
    "sgp30": "https://learn.adafruit.com/adafruit-sgp30-gas-tvoc-eco2-mox-sensor/pinouts",
    "ina219": "https://learn.adafruit.com/adafruit-ina219-current-sensor-breakout/pinouts",
    "max9814": "https://learn.adafruit.com/adafruit-agc-electret-microphone-amplifier-max9814?view=all",
    "pir189": "https://learn.adafruit.com/pir-passive-infrared-proximity-motion-sensor/connecting-to-a-pir",
    "st7789": "https://learn.adafruit.com/adafruit-1-3-and-1-54-240-x-240-wide-angle-tft-lcd-displays/pinouts",
}


def pin(name: str, number: str, x: float, y: float, side: str, direction: str = "bidirectional", functions: list[str] | None = None) -> dict[str, Any]:
    return {"name": name, "number": number, "x": x, "y": y, "side": side, "direction": direction, "functions": functions or []}


def bottom_pins(width: float, height: float, rows: list[tuple[str, str]]) -> list[dict[str, Any]]:
    """Lay out a documented pin table without claiming photo-derived coordinates."""
    step = (width - 4.8) / max(1, len(rows) - 1)
    return [pin(name, str(index + 1), 2.4 + index * step, height - 2.4, "bottom", direction) for index, (name, direction) in enumerate(rows)]


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
        "assetId": "orange-pi.zero-3-v1.3", "revision": "1.1.0", "manufacturer": "Shenzhen Xunlong Software", "mpn": "Orange Pi Zero 3 v1.3",
        "level": "linux-single-board-computer", "width": 50, "height": 55, "canvasWidth": 130, "color": "#e86b1f", "accent": "#202421",
        "subtitle": "H618 · 26-PIN GPIO", "source": SOURCES["orange-pi-zero-3"], "pins": orange_pi_pins(),
        "parts": [(8, 9, 27, 27, "H618"), (8, 39, 20, 10, "LPDDR4"), (35, 5, 12, 16, "RJ45"), (35, 26, 12, 8, "USB-C")],
    },
    {
        "assetId": "adafruit.vl53l1x-3967", "revision": "1.1.0", "manufacturer": "Adafruit Industries", "mpn": "VL53L1X ToF #3967",
        "level": "distance-sensor-module", "width": 25.4, "height": 17.8, "canvasWidth": 48, "color": "#161b19", "accent": "#e9e9e4",
        "subtitle": "DISTANCE · I²C 0x29", "source": SOURCES["vl53l1x"],
        "pins": [pin(n, str(i + 1), 2.4 + i * 4.1, 15.4, "bottom", d) for i, (n, d) in enumerate([("VIN", "power"), ("GND", "power"), ("SCL", "input"), ("SDA", "bidirectional"), ("GPIO", "output"), ("XSHUT", "input")])],
        "parts": [(8.6, 4.0, 8.2, 7.2, "TOF")],
    },
    {
        "assetId": "adafruit.lis3mdl-4479", "revision": "1.1.0", "manufacturer": "Adafruit Industries", "mpn": "LIS3MDL #4479",
        "level": "magnetometer-module", "width": 25.4, "height": 17.8, "canvasWidth": 48, "color": "#171c1a", "accent": "#eeeeea",
        "subtitle": "MAGNETIC · I²C / SPI", "source": SOURCES["lis3mdl"],
        "pins": [pin(n, str(i + 1), 2.0 + i * 2.65, 15.4, "bottom", d) for i, (n, d) in enumerate([("VIN", "power"), ("3VO", "power"), ("GND", "power"), ("SCL", "input"), ("SDA", "bidirectional"), ("DO", "output"), ("CS", "input"), ("INT", "output"), ("DRDY", "output")])],
        "parts": [(9.1, 4.4, 7.2, 7.2, "MAG")],
    },
    {
        "assetId": "adafruit.bme688-5046", "revision": "1.1.0", "manufacturer": "Adafruit Industries", "mpn": "BME688 #5046",
        "level": "voc-gas-sensor-module", "width": 25.4, "height": 17.8, "canvasWidth": 48, "color": "#151a18", "accent": "#efefea",
        "subtitle": "GAS / VOC · I²C / SPI", "source": SOURCES["bme688"],
        "pins": [pin(n, str(i + 1), 2.6 + i * 3.35, 15.4, "bottom", d) for i, (n, d) in enumerate([("VIN", "power"), ("3VO", "power"), ("GND", "power"), ("SCK", "input"), ("SDO", "output"), ("SDI", "bidirectional"), ("CS", "input")])],
        "parts": [(9.4, 4.2, 6.6, 6.6, "VOC")],
    },
    {
        "assetId": "adafruit.sph0645lm4h-3421", "revision": "1.1.0", "manufacturer": "Adafruit Industries", "mpn": "SPH0645LM4H #3421",
        "level": "digital-microphone-module", "width": 22.9, "height": 15.2, "canvasWidth": 46, "color": "#171b19", "accent": "#eceee9",
        "subtitle": "SOUND · DIGITAL I²S", "source": SOURCES["sph0645"],
        "pins": [pin(n, str(i + 1), 2.2 + i * 3.7, 13.0, "bottom", d) for i, (n, d) in enumerate([("3V", "power"), ("GND", "power"), ("BCLK", "input"), ("DOUT", "output"), ("LRCLK", "input"), ("SEL", "input")])],
        "parts": [(8.3, 3.3, 6.2, 6.2, "MIC")],
    },
    {
        "assetId": "waveshare.0.96inch-oled-b", "revision": "1.2.0", "manufacturer": "Waveshare", "mpn": "0.96inch OLED (B)",
        "level": "oled-display-module", "width": 33.0, "height": 33.5, "canvasWidth": 58, "color": "#184a7d", "accent": "#09131e",
        "subtitle": "DISPLAY · 128×64 · SPI / I²C", "source": SOURCES["oled"],
        "pins": [pin(n, str(i + 1), 2.5 + i * 3.95, 31.0, "bottom", d) for i, (n, d) in enumerate([("VCC", "power"), ("GND", "power"), ("NC", "input"), ("DIN", "input"), ("CLK", "input"), ("CS", "input"), ("D/C", "input"), ("RES", "input")])],
        "parts": [(5.6, 4.2, 21.7, 14.2, "OLED 128×64")],
    },
    {
        "assetId": "adafruit.veml7700-4162", "revision": "1.0.0", "manufacturer": "Adafruit Industries", "mpn": "VEML7700 #4162",
        "level": "ambient-light-sensor-module", "width": 25.4, "height": 17.8, "canvasWidth": 48, "color": "#151a18", "accent": "#f0eee8",
        "subtitle": "AMBIENT LIGHT · I²C 0x10", "source": SOURCES["veml7700"],
        "pins": [pin(n, str(i + 1), 2.4 + i * 4.1, 15.4, "bottom", d) for i, (n, d) in enumerate([("VIN", "power"), ("3VO", "power"), ("GND", "power"), ("SCL", "input"), ("SDA", "bidirectional"), ("INT", "output")])],
        "parts": [(9.0, 4.3, 7.4, 7.0, "LIGHT")],
    },
    {
        "assetId": "adafruit.apds9960-4060", "revision": "1.0.0", "manufacturer": "Adafruit Industries", "mpn": "APDS9960 #4060",
        "level": "proximity-light-color-gesture-sensor-module", "width": 25.4, "height": 17.8, "canvasWidth": 48, "color": "#151a18", "accent": "#e8e8e1",
        "subtitle": "LIGHT / COLOR / PROXIMITY · I²C 0x39", "source": SOURCES["apds9960"],
        "pins": [pin(n, str(i + 1), 2.4 + i * 4.1, 15.4, "bottom", d) for i, (n, d) in enumerate([("VIN", "power"), ("3VO", "power"), ("GND", "power"), ("SCL", "input"), ("SDA", "bidirectional"), ("INT", "output")])],
        "parts": [(8.7, 4.0, 8.0, 7.6, "RGB+IR")],
    },
    {
        "assetId": "adafruit.sht45-5665", "revision": "1.0.0", "manufacturer": "Adafruit Industries", "mpn": "SHT45 #5665",
        "level": "temperature-humidity-sensor-module", "width": 25.4, "height": 17.8, "canvasWidth": 48, "color": "#151a18", "accent": "#e9e6dd",
        "subtitle": "TEMP / HUMIDITY · I²C 0x44", "source": SOURCES["sht45"],
        "pins": [pin(n, str(i + 1), 4.2 + i * 4.25, 15.4, "bottom", d) for i, (n, d) in enumerate([("VIN", "power"), ("3V", "power"), ("GND", "power"), ("SCL", "input"), ("SDA", "bidirectional")])],
        "parts": [(9.2, 4.1, 7.0, 7.2, "SHT45")],
    },
    {
        "assetId": "adafruit.scd40-5187", "revision": "1.0.0", "manufacturer": "Adafruit Industries", "mpn": "SCD-40 #5187",
        "level": "co2-gas-sensor-module", "width": 25.5, "height": 22.8, "canvasWidth": 50, "color": "#151a18", "accent": "#e7e8df",
        "subtitle": "TRUE CO₂ · I²C 0x62", "source": SOURCES["scd40"],
        "pins": [pin(n, str(i + 1), 4.25 + i * 4.25, 20.4, "bottom", d) for i, (n, d) in enumerate([("VIN", "power"), ("3VO", "power"), ("GND", "power"), ("SCL", "input"), ("SDA", "bidirectional")])],
        "parts": [(7.6, 4.0, 10.1, 10.1, "CO₂")],
    },
    {
        "assetId": "adafruit.bme280-2652", "revision": "1.0.0", "manufacturer": "Adafruit Industries", "mpn": "BME280 #2652",
        "level": "environmental-sensor-module", "width": 25.4, "height": 17.8, "canvasWidth": 48, "color": "#151a18", "accent": "#e8e7df",
        "subtitle": "TEMP / HUMIDITY / PRESSURE · I²C / SPI", "source": SOURCES["bme280"],
        "pins": bottom_pins(25.4, 17.8, [("VIN", "power"), ("3VO", "power"), ("GND", "power"), ("SCK", "input"), ("SDO", "output"), ("SDI", "bidirectional"), ("CS", "input")]),
        "parts": [(9.0, 4.0, 7.4, 7.4, "BME280")],
    },
    {
        "assetId": "adafruit.aht20-4566", "revision": "1.0.0", "manufacturer": "Adafruit Industries", "mpn": "AHT20 #4566",
        "level": "temperature-humidity-sensor-module", "width": 25.4, "height": 17.8, "canvasWidth": 48, "color": "#151a18", "accent": "#e8e7df",
        "subtitle": "TEMP / HUMIDITY · I²C 0x38", "source": SOURCES["aht20"],
        "pins": bottom_pins(25.4, 17.8, [("VIN", "power"), ("GND", "power"), ("SCL", "input"), ("SDA", "bidirectional")]),
        "parts": [(9.1, 4.0, 7.2, 7.4, "AHT20")],
    },
    {
        "assetId": "adafruit.mpu6050-3886", "revision": "1.0.1", "manufacturer": "Adafruit Industries", "mpn": "MPU-6050 #3886",
        "level": "six-axis-imu-module", "width": 25.4, "height": 17.8, "canvasWidth": 54, "color": "#151a18", "accent": "#e6e6df",
        "subtitle": "6-DOF IMU · I²C 0x68 / 0x69", "source": SOURCES["mpu6050"],
        "densePins": True, "pins": bottom_pins(25.4, 17.8, [("VIN", "power"), ("3VO", "power"), ("GND", "power"), ("SCL", "input"), ("SDA", "bidirectional"), ("INT", "output"), ("AD0", "input"), ("FS", "bidirectional"), ("SCE", "bidirectional"), ("SDE", "bidirectional"), ("CLKIN", "input")]),
        "parts": [(8.9, 4.0, 7.6, 7.6, "IMU")],
    },
    {
        "assetId": "adafruit.lis3dh-2809", "revision": "1.0.1", "manufacturer": "Adafruit Industries", "mpn": "LIS3DH #2809",
        "level": "accelerometer-module", "width": 25.4, "height": 19.0, "canvasWidth": 56, "color": "#151a18", "accent": "#e6e6df",
        "subtitle": "3-AXIS ACCEL · I²C / SPI / ADC", "source": SOURCES["lis3dh"],
        "densePins": True, "pins": bottom_pins(25.4, 19.0, [("VIN", "power"), ("3VO", "power"), ("GND", "power"), ("SCL", "input"), ("SDA", "bidirectional"), ("SDO", "output"), ("CS", "input"), ("INT", "output"), ("A1", "input"), ("A2", "input"), ("A3", "input"), ("I2", "output")]),
        "parts": [(9.0, 4.6, 7.4, 7.4, "ACCEL")],
    },
    {
        "assetId": "adafruit.ltr390-4831", "revision": "1.0.0", "manufacturer": "Adafruit Industries", "mpn": "LTR390 #4831",
        "level": "uv-light-sensor-module", "width": 25.4, "height": 17.8, "canvasWidth": 48, "color": "#151a18", "accent": "#e8e7df",
        "subtitle": "UV / AMBIENT LIGHT · I²C 0x53", "source": SOURCES["ltr390"],
        "pins": bottom_pins(25.4, 17.8, [("VIN", "power"), ("3VO", "power"), ("GND", "power"), ("SCL", "input"), ("SDA", "bidirectional"), ("INT", "output")]),
        "parts": [(9.0, 4.0, 7.4, 7.4, "UV")],
    },
    {
        "assetId": "adafruit.vl53l0x-3317", "revision": "1.0.0", "manufacturer": "Adafruit Industries", "mpn": "VL53L0X #3317",
        "level": "distance-sensor-module", "width": 25.4, "height": 17.8, "canvasWidth": 48, "color": "#151a18", "accent": "#e8e7df",
        "subtitle": "DISTANCE · I²C 0x29", "source": SOURCES["vl53l0x"],
        "pins": bottom_pins(25.4, 17.8, [("VIN", "power"), ("2V8", "power"), ("GND", "power"), ("SCL", "input"), ("SDA", "bidirectional"), ("GPIO", "output"), ("SHDN", "input")]),
        "parts": [(8.8, 4.0, 7.8, 7.4, "TOF")],
    },
    {
        "assetId": "adafruit.sgp30-3709", "revision": "1.0.0", "manufacturer": "Adafruit Industries", "mpn": "SGP30 #3709",
        "level": "voc-gas-sensor-module", "width": 25.4, "height": 17.8, "canvasWidth": 48, "color": "#151a18", "accent": "#deded7",
        "subtitle": "TVOC / eCO₂ · I²C 0x58", "source": SOURCES["sgp30"],
        "pins": bottom_pins(25.4, 17.8, [("VIN", "power"), ("1V8", "power"), ("GND", "power"), ("SCL", "input"), ("SDA", "bidirectional")]),
        "parts": [(8.5, 3.8, 8.4, 8.0, "VOC")],
    },
    {
        "assetId": "adafruit.ina219-904", "revision": "1.0.0", "manufacturer": "Adafruit Industries", "mpn": "INA219 #904",
        "level": "current-sensor-module", "width": 25.4, "height": 22.9, "canvasWidth": 50, "color": "#151a18", "accent": "#e6e3d9",
        "subtitle": "CURRENT / BUS VOLTAGE · I²C 0x40", "source": SOURCES["ina219"],
        "pins": bottom_pins(25.4, 22.9, [("VIN", "power"), ("GND", "power"), ("SCL", "input"), ("SDA", "bidirectional"), ("VIN+", "input"), ("VIN-", "input"), ("A0", "input"), ("A1", "input")]),
        "parts": [(8.7, 5.5, 8.0, 8.0, "CURRENT")],
    },
    {
        "assetId": "adafruit.max9814-1713", "revision": "1.0.0", "manufacturer": "Adafruit Industries", "mpn": "MAX9814 #1713",
        "level": "analog-microphone-module", "width": 26.0, "height": 15.0, "canvasWidth": 48, "color": "#151a18", "accent": "#e3e4dc",
        "subtitle": "SOUND · ANALOG OUT · AGC", "source": SOURCES["max9814"],
        "pins": bottom_pins(26.0, 15.0, [("VDD", "power"), ("GND", "power"), ("OUT", "output"), ("GAIN", "input"), ("A/R", "input")]),
        "parts": [(9.6, 3.0, 6.8, 6.8, "MIC")],
    },
    {
        "assetId": "adafruit.pir-motion-189", "revision": "1.0.0", "manufacturer": "Adafruit Industries", "mpn": "PIR Motion Sensor #189",
        "level": "pir-motion-sensor-module", "width": 32.0, "height": 24.0, "canvasWidth": 52, "color": "#176c4b", "accent": "#f0eee5",
        "subtitle": "MOTION · DIGITAL OUTPUT", "source": SOURCES["pir189"],
        "pins": bottom_pins(32.0, 24.0, [("5V", "power"), ("OUT", "output"), ("GND", "power")]),
        "parts": [(8.0, 3.0, 16.0, 14.0, "PIR")],
    },
    {
        "assetId": "adafruit.st7789-4313", "revision": "1.0.1", "manufacturer": "Adafruit Industries", "mpn": "1.3in ST7789 TFT #4313",
        "level": "tft-display-module", "width": 35.8, "height": 35.8, "canvasWidth": 64, "color": "#151a18", "accent": "#151c24",
        "subtitle": "DISPLAY · 240×240 · SPI", "source": SOURCES["st7789"],
        "densePins": True, "pins": bottom_pins(35.8, 35.8, [("VIN", "power"), ("3V3", "power"), ("GND", "power"), ("SCK", "input"), ("SO", "output"), ("SI", "input"), ("TCS", "input"), ("RST", "input"), ("D/C", "input"), ("CCS", "input"), ("LITE", "input")]) + [pin("TE", "TP1", 31.8, 5.0, "top", "output")],
        "parts": [(4.9, 4.2, 26.0, 26.0, "TFT 240×240")],
    },
]


DECLARATIVE_CATALOG_PATH = Path(__file__).resolve().parents[1] / "assets" / "catalog-specs" / "common-products-v1.json"


def load_declarative_catalog(path: Path = DECLARATIVE_CATALOG_PATH) -> list[dict[str, Any]]:
    """Load reviewed product facts separately from rendering code.

    Keeping exact identities, evidence URLs and pin tables in JSON makes catalog
    growth reviewable and prevents the renderer from becoming a second database.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "circuitlab-common-products/v1":
        raise ValueError(f"unsupported catalog schema in {path}")
    products = payload.get("products")
    if not isinstance(products, list):
        raise ValueError(f"products must be a list in {path}")
    required = {"assetId", "revision", "manufacturer", "mpn", "level", "width", "height", "canvasWidth", "subtitle", "pins", "sources"}
    for product in products:
        missing = sorted(required - set(product))
        if missing:
            raise ValueError(f"{product.get('assetId', '<unknown>')} missing {', '.join(missing)}")
        if len({row["name"] for row in product["pins"]}) != len(product["pins"]):
            raise ValueError(f"{product['assetId']} has duplicate pin names")
        if not product["pins"] or not all(str(url).startswith("https://") for url in product["sources"]):
            raise ValueError(f"{product['assetId']} requires pins and HTTPS evidence")
    return products


CATALOG.extend(load_declarative_catalog())


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


STYLE = {
    "schema": "circuitlab-top-style/v1",
    "name": "CircuitLab Technical Top",
    "boardStroke": "#738079",
    "silk": "#eef4ef",
    "trace": "#7c8c82",
    "pin": {"power": "#ff6b6b", "ground": "#707873", "clock": "#f3c94f", "data": "#69a7ff", "signal": "#ae7bff"},
}
BOARD_Y = 6.0
FOOTER = 13.0


def pin_colour(row: dict[str, Any]) -> str:
    name = str(row["name"]).upper()
    if "GND" in name:
        return STYLE["pin"]["ground"]
    if row["direction"] == "power" or name in {"VIN", "VCC", "3V", "3VO", "3V3", "5V"}:
        return STYLE["pin"]["power"]
    if any(marker in name for marker in ("SCL", "CLK", "BCLK", "LRCLK", "SCK")):
        return STYLE["pin"]["clock"]
    if any(marker in name for marker in ("SDA", "DIN", "DOUT", "SDI", "SDO", "MOSI", "MISO")):
        return STYLE["pin"]["data"]
    return STYLE["pin"]["signal"]


def render(spec: dict[str, Any]) -> str:
    if spec.get("shape", "module") != "module":
        return render_primitive(spec)
    scale = 8
    physical_width = spec["width"]
    canvas_width = spec["canvasWidth"]
    footer = 19.0 if spec.get("densePins") else FOOTER
    height = spec["height"] + BOARD_Y + footer
    offset_x = (canvas_width - physical_width) / 2
    board_x = offset_x * scale; board_y = BOARD_Y * scale
    board_width = physical_width * scale; board_height = spec["height"] * scale
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_width * scale:g} {height * scale:g}" role="img" aria-label="{esc(spec["mpn"])} interactive top view">',
        '<defs><filter id="s" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="3" stdDeviation="3" flood-opacity=".35"/></filter><linearGradient id="metal" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#fafafa"/><stop offset=".55" stop-color="#b8c0bc"/><stop offset="1" stop-color="#7b8580"/></linearGradient></defs>',
        f'<rect x="{board_x:g}" y="{board_y:g}" width="{board_width:g}" height="{board_height:g}" rx="9" fill="{spec["color"]}" stroke="{STYLE["boardStroke"]}" stroke-width="2" filter="url(#s)"/>',
        f'<text x="{canvas_width * scale / 2:g}" y="17" text-anchor="middle" fill="#53615a" font-family="ui-monospace,monospace" font-size="8" font-weight="800" letter-spacing="1.2">↑ FRONT · TOP · CIRCUITLAB STYLE V1</text>',
    ] + ([] if spec.get("mechanicalPads") else [
        f'<text x="{board_x + 10:g}" y="{board_y + 15:g}" fill="{STYLE["silk"]}" font-family="ui-monospace,monospace" font-size="6.5" font-weight="700">{esc(spec["manufacturer"])}</text>',
        f'<text x="{board_x + 10:g}" y="{board_y + 25:g}" fill="#9eb0a6" font-family="ui-monospace,monospace" font-size="5.5">{esc(spec["mpn"])}</text>',
    ]) + [
        f'<text x="{canvas_width * scale / 2:g}" y="{(BOARD_Y + spec["height"] + (13 if spec.get("densePins") else 7)) * scale:g}" text-anchor="middle" fill="#26332c" font-family="ui-monospace,monospace" font-size="11" font-weight="800">{esc(spec["mpn"])}</text>',
        f'<text x="{canvas_width * scale / 2:g}" y="{(BOARD_Y + spec["height"] + (15.1 if spec.get("densePins") else 9.1)) * scale:g}" text-anchor="middle" fill="#278b50" font-family="ui-monospace,monospace" font-size="7" font-weight="700">{esc(spec["subtitle"])}</text>',
    ]
    for hole_x, hole_y in ((2.3, 2.3), (physical_width - 2.3, 2.3), (2.3, spec["height"] - 2.3), (physical_width - 2.3, spec["height"] - 2.3)):
        hx = (offset_x + hole_x) * scale; hy = (BOARD_Y + hole_y) * scale
        lines.append(f'<circle cx="{hx:g}" cy="{hy:g}" r="6.5" fill="#d7aa26" stroke="#f5dc75" stroke-width="1"/><circle cx="{hx:g}" cy="{hy:g}" r="3.4" fill="#e9ece8"/>')
    for pad in spec.get("mechanicalPads", []):
        px = (offset_x + float(pad["x"])) * scale; py = (BOARD_Y + float(pad["y"])) * scale
        lines.append(f'<g data-mechanical-pad="unconnected"><circle cx="{px:g}" cy="{py:g}" r="8.4" fill="#858d88" stroke="#16201a" stroke-width="1.5"/><circle cx="{px:g}" cy="{py:g}" r="5.5" fill="#f5f7f4"/><circle cx="{px:g}" cy="{py:g}" r="2.4" fill="#3e4641"/><title>Mechanical stability hole — no electrical connection</title></g>')
    if spec["manufacturer"] == "Adafruit Industries":
        connector_y = (BOARD_Y + spec["height"] * .43) * scale
        lines.extend([
            f'<rect x="{board_x - 2:g}" y="{connector_y:g}" width="19" height="28" rx="3" fill="#e8dfcd" stroke="#9f9685"/>',
            f'<rect x="{board_x + board_width - 17:g}" y="{connector_y:g}" width="19" height="28" rx="3" fill="#e8dfcd" stroke="#9f9685"/>',
        ])
    for x, y, width, part_height, label in spec["parts"]:
        px = (offset_x + x) * scale; py = (BOARD_Y + y) * scale
        part_width = width * scale; rendered_height = part_height * scale
        for row in spec["pins"]:
            tx = (offset_x + row["x"]) * scale; ty = (BOARD_Y + row["y"]) * scale
            lines.append(f'<path d="M{px + part_width / 2:g} {py + rendered_height / 2:g}L{tx:g} {ty:g}" stroke="{STYLE["trace"]}" stroke-width="1" opacity=".24" fill="none"/>')
        lines.append(f'<rect x="{px:g}" y="{py:g}" width="{part_width:g}" height="{rendered_height:g}" rx="5" fill="{spec["accent"]}" stroke="#9ca49f" stroke-width="1.5"/>')
        if "OLED" in label or "TFT" in label:
            lines.append(f'<rect x="{px + 7:g}" y="{py + 7:g}" width="{part_width - 14:g}" height="{rendered_height - 14:g}" rx="3" fill="#07131d"/><path d="M{px + 12:g} {py + rendered_height * .38:g}H{px + part_width - 12:g}" stroke="#f5d34d" stroke-width="5"/><path d="M{px + 12:g} {py + rendered_height * .68:g}H{px + part_width - 12:g}" stroke="#4ea7ff" stroke-width="9"/>')
        elif any(marker in label for marker in ("TOF", "LIGHT", "RGB", "CO₂")):
            lines.append(f'<circle cx="{px + part_width / 2:g}" cy="{py + rendered_height / 2:g}" r="{min(part_width, rendered_height) * .22:g}" fill="#161c19" stroke="#6b7770" stroke-width="2"/>')
        part_text = "#f3f6f2" if "OLED" in label or "TFT" in label else "#222925"
        lines.append(f'<text x="{px + width * scale / 2:g}" y="{py + part_height * scale / 2 + 3:g}" text-anchor="middle" fill="{part_text}" font-family="ui-monospace,monospace" font-size="8" font-weight="800">{esc(label)}</text>')
    for index, row in enumerate(spec["pins"]):
        x = (offset_x + row["x"]) * scale; y = (BOARD_Y + row["y"]) * scale
        label = row["functions"][0] if spec["assetId"].startswith("orange-pi") else row["name"]
        colour = pin_colour(row)
        lines.extend([
            f'<g id="pin-{esc(row["name"])}" data-pin="{esc(row["name"])}">',
            f'<circle cx="{x:g}" cy="{y:g}" r="8.4" fill="{colour}" stroke="#16201a" stroke-width="1.5"/>',
            f'<circle cx="{x:g}" cy="{y:g}" r="5.5" fill="#f5f7f4" stroke="#c8d0cb" stroke-width="1"/>',
            f'<circle cx="{x:g}" cy="{y:g}" r="2.4" fill="#3e4641"/>',
        ])
        if spec["assetId"].startswith("orange-pi"):
            tx = (offset_x + physical_width + 4 + (index % 2) * 15) * scale
            lines.append(f'<text x="{tx:g}" y="{y + 2.5:g}" fill="#29352f" font-family="ui-monospace,monospace" font-size="6.5" font-weight="700">{esc(row["number"])} {esc(label)}</text>')
        elif row["side"] == "top":
            lines.append(f'<text x="{x - 11:g}" y="{y + 3:g}" text-anchor="end" fill="{colour}" font-family="ui-monospace,monospace" font-size="6.5" font-weight="800">{esc(label)}</text>')
        elif spec.get("densePins"):
            label_y = (BOARD_Y + spec["height"] + 2.0) * scale
            lines.append(f'<text x="{x:g}" y="{label_y:g}" transform="rotate(-62 {x:g} {label_y:g})" text-anchor="start" fill="{colour}" font-family="ui-monospace,monospace" font-size="5.7" font-weight="800">{esc(label)}</text>')
        else:
            lines.append(f'<text x="{x:g}" y="{(BOARD_Y + spec["height"] + 2.2) * scale:g}" text-anchor="middle" fill="{colour}" font-family="ui-monospace,monospace" font-size="6.5" font-weight="800">{esc(label)}</text>')
        lines.append('</g>')
    lines.append('</svg>')
    return "\n".join(lines) + "\n"


def render_primitive(spec: dict[str, Any]) -> str:
    """Render deterministic orthographic primitives without copying product photos."""
    scale = 10
    canvas_width = float(spec["canvasWidth"])
    height = float(spec["height"] + BOARD_Y + FOOTER)
    offset_x = (canvas_width - float(spec["width"])) / 2
    x0 = offset_x * scale
    y0 = BOARD_Y * scale
    width = float(spec["width"]) * scale
    body_height = float(spec["height"]) * scale
    shape = spec["shape"]
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_width * scale:g} {height * scale:g}" role="img" aria-label="{esc(spec["mpn"])} interactive top view">',
        '<defs><filter id="s" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="3" stdDeviation="3" flood-opacity=".3"/></filter><linearGradient id="metal" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#f4f6f5"/><stop offset=".55" stop-color="#aab3ae"/><stop offset="1" stop-color="#707a75"/></linearGradient></defs>',
        f'<text x="{canvas_width * scale / 2:g}" y="17" text-anchor="middle" fill="#53615a" font-family="ui-monospace,monospace" font-size="8" font-weight="800" letter-spacing="1.2">↑ FRONT · TOP · CIRCUITLAB STYLE V1</text>',
    ]
    if shape == "axial-resistor":
        cy = y0 + body_height / 2
        lines += [
            f'<path d="M{x0:g} {cy:g}H{x0 + width:g}" stroke="url(#metal)" stroke-width="5"/>',
            f'<rect x="{x0 + width * .28:g}" y="{y0:g}" width="{width * .44:g}" height="{body_height:g}" rx="{body_height / 2:g}" fill="#d8b978" stroke="#846d43" stroke-width="2" filter="url(#s)"/>',
        ]
        for index, colour in enumerate(spec.get("bands", [])):
            bx = x0 + width * (.34 + index * .08)
            lines.append(f'<rect x="{bx:g}" y="{y0 + 2:g}" width="5" height="{body_height - 4:g}" fill="{esc(colour)}"/>')
    elif shape == "tactile-button":
        lines += [
            f'<rect x="{x0:g}" y="{y0:g}" width="{width:g}" height="{body_height:g}" rx="8" fill="#202723" stroke="#707b75" stroke-width="2" filter="url(#s)"/>',
            f'<circle cx="{x0 + width / 2:g}" cy="{y0 + body_height / 2:g}" r="{min(width, body_height) * .29:g}" fill="#b9c1bd" stroke="#f0f3f1" stroke-width="2"/>',
        ]
    elif shape in {"led", "rgb-led"}:
        cx = x0 + width / 2
        cy = y0 + body_height * .43
        fill = spec.get("lensColor", "#e64f4f")
        lines += [
            f'<circle cx="{cx:g}" cy="{cy:g}" r="{min(width, body_height) * .37:g}" fill="{esc(fill)}" fill-opacity=".76" stroke="#f5f7f4" stroke-width="2" filter="url(#s)"/>',
            f'<circle cx="{cx - width * .1:g}" cy="{cy - body_height * .12:g}" r="{min(width, body_height) * .08:g}" fill="#fff" opacity=".55"/>',
        ]
    for row in spec["pins"]:
        x = (offset_x + float(row["x"])) * scale
        y = (BOARD_Y + float(row["y"])) * scale
        colour = pin_colour(row)
        if row["side"] == "left":
            label_x, label_y, label_anchor = x - 12, y + 3, "end"
        elif row["side"] == "right":
            label_x, label_y, label_anchor = x + 12, y + 3, "start"
        else:
            label_x, label_y, label_anchor = x, (BOARD_Y + spec["height"] + 2.5) * scale, "middle"
        lines += [
            f'<g id="pin-{esc(row["name"])}" data-pin="{esc(row["name"])}">',
            f'<circle cx="{x:g}" cy="{y:g}" r="8.4" fill="{colour}" stroke="#16201a" stroke-width="1.5"/>',
            f'<circle cx="{x:g}" cy="{y:g}" r="4.8" fill="#f5f7f4"/>',
            f'<text x="{label_x:g}" y="{label_y:g}" text-anchor="{label_anchor}" fill="{colour}" font-family="ui-monospace,monospace" font-size="6.5" font-weight="800">{esc(row["name"])}</text>',
            '</g>',
        ]
    lines += [
        f'<text x="{canvas_width * scale / 2:g}" y="{(BOARD_Y + spec["height"] + 7) * scale:g}" text-anchor="middle" fill="#26332c" font-family="ui-monospace,monospace" font-size="11" font-weight="800">{esc(spec["mpn"])}</text>',
        f'<text x="{canvas_width * scale / 2:g}" y="{(BOARD_Y + spec["height"] + 9.1) * scale:g}" text-anchor="middle" fill="#278b50" font-family="ui-monospace,monospace" font-size="7" font-weight="700">{esc(spec["subtitle"])}</text>',
        '</svg>',
    ]
    return "\n".join(lines) + "\n"


def package_for(spec: dict[str, Any], svg: bytes) -> dict[str, Any]:
    canvas_width = float(spec["canvasWidth"]); height = float(spec["height"] + BOARD_Y + (19.0 if spec.get("densePins") else FOOTER)); offset_x = (canvas_width - float(spec["width"])) / 2
    source_urls = spec["sources"] if "sources" in spec else [spec["source"]]
    is_declarative = "sources" in spec
    physical = {"widthMm": spec["width"], "heightMm": spec["height"], "package": spec.get("package", "assembled-module")}
    if is_declarative:
        physical["dimensionStatus"] = spec.get("dimensionStatus", "OFFICIAL_PRODUCT_DIMENSIONS")
    return {
        "schema": "component-package/v1",
        "identity": {"assetId": spec["assetId"], "revision": spec["revision"], "manufacturer": spec["manufacturer"], "mpn": spec["mpn"], "level": spec["level"], "status": "DESIGN_DOC_DERIVED_UNVERIFIED", "lifecycle": "active"},
        "electrical": {"status": "OFFICIAL_PIN_TABLE_DERIVED_UNVERIFIED", "pins": [{key: row[key] for key in ("name", "number", "direction", "functions")} for row in spec["pins"]]},
        "visual": {"appearance": "top.svg", "appearanceSha256": hashlib.sha256(svg).hexdigest(), "style": STYLE["schema"], "coordinateStatus": "DOCUMENTED_PIN_TABLE_VISUAL_LAYOUT_UNVERIFIED", "anchors": [{"pin": row["name"], "x": round((offset_x + row["x"]) / canvas_width, 8), "y": round((BOARD_Y + row["y"]) / height, 8), "status": "DOCUMENTED_PIN_TABLE_VISUAL_LAYOUT_UNVERIFIED"} for row in spec["pins"]], "views": [{"name": "interactive-top", "view": "original-vector-top", "path": "top.svg"}]},
        "physical": physical,
        "evidence": {"capturedAt": "2026-09-03T00:00:00Z" if is_declarative else "2026-09-02T00:00:00Z", "sources": [{"type": "official-product-or-pinout" if is_declarative else "manufacturer-pinout-documentation", "url": url} for url in source_urls], "rendering": "ORIGINAL_CIRCUITLAB_VECTOR_FROM_OFFICIAL_PIN_TABLE_NOT_PHOTO_TRACE", "sourceSpecSha256": hashlib.sha256(json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the redistributable CircuitLab starter hardware catalog.")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "assets" / "catalog")
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--data", type=Path, default=default_data_root())
    args = parser.parse_args()
    output = args.output.expanduser().resolve(); output.mkdir(parents=True, exist_ok=True)
    (output / "style.json").write_text(json.dumps(STYLE, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    registry = ComponentRegistry(args.data.expanduser().resolve() / "registry") if args.install else None
    results = []
    for spec in CATALOG:
        directory = output / spec["assetId"] / spec["revision"]
        directory.mkdir(parents=True, exist_ok=True)
        svg = render(spec).encode("utf-8")
        package = package_for(spec, svg)
        (directory / "top.svg").write_bytes(svg)
        (directory / "source-spec.json").write_text(json.dumps({"schema": "hardware-source-spec/v1", **spec}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (directory / "component-package.json").write_text(json.dumps(package, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result = {"ref": f'{spec["assetId"]}@{spec["revision"]}', "pins": len(spec["pins"])}
        if registry is not None:
            result["install"] = registry.install(package, {"top.svg": svg})["status"]
        results.append(result)
    xiao_source = Path(__file__).resolve().parents[1] / "docs" / "generated" / "xiao-esp32s3"
    xiao_package = json.loads((xiao_source / "component-package.json").read_text(encoding="utf-8"))
    xiao_package["identity"]["revision"] = "1.3.0"
    xiao_package["evidence"]["capturedAt"] = "2026-09-02T00:00:00Z"
    xiao_package["visual"]["style"] = STYLE["schema"]
    xiao_files = {name: (xiao_source / name).read_bytes() for name in ("board.svg", "board.json")}
    xiao_directory = output / xiao_package["identity"]["assetId"] / xiao_package["identity"]["revision"]
    xiao_directory.mkdir(parents=True, exist_ok=True)
    for name, body in xiao_files.items():
        (xiao_directory / name).write_bytes(body)
    (xiao_directory / "component-package.json").write_text(json.dumps(xiao_package, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    xiao_result = {"ref": "seeed.xiao-esp32s3@1.3.0", "pins": len(xiao_package["electrical"]["pins"])}
    if registry is not None:
        xiao_result["install"] = registry.install(xiao_package, xiao_files)["status"]
    results.append(xiao_result)
    latest_rows = {}
    for package_path in output.glob("*/*/component-package.json"):
        package = json.loads(package_path.read_text(encoding="utf-8"))
        identity = package["identity"]
        ref = f'{identity["assetId"]}@{identity["revision"]}'
        current = latest_rows.get(identity["assetId"])
        if current is None or identity["revision"] > current["revision"]:
            latest_rows[identity["assetId"]] = {"ref": ref, "revision": identity["revision"], "pins": len(package.get("electrical", {}).get("pins", []))}
    catalog_rows = [{"ref": row["ref"], "pins": row["pins"]} for row in sorted(latest_rows.values(), key=lambda item: item["ref"])]
    (output / "index.json").write_text(json.dumps({"schema": "circuitlab-catalog/v1", "components": catalog_rows}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "components": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
