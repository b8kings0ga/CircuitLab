from __future__ import annotations

import importlib.util
import sys
import json
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("official_media", SCRIPTS / "official_media.py")
official_media = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(official_media)


class OfficialMediaTests(unittest.TestCase):
    def test_parser_extracts_structured_and_responsive_images(self) -> None:
        parser = official_media.MediaParser()
        parser.feed('''<html><head><title>ESP32-S3-DevKitC-1</title>
          <meta property="og:image" content="/media/hero.png">
          <script type="application/ld+json">{"@type":"Product","name":"ESP32-S3-DevKitC-1","image":["/media/top.jpg"]}</script>
          </head><body><img alt="ESP32-S3-DevKitC-1 front board" src="/media/front.webp" srcset="/media/front-2x.webp 2x"></body></html>''')
        records = list(parser.records)
        for value in parser.jsonld:
            records.extend(official_media.jsonld_images(__import__("json").loads(value)))
        self.assertEqual({row["url"] for row in records}, {"/media/hero.png", "/media/top.jpg", "/media/front.webp", "/media/front-2x.webp"})

    def test_scoring_prefers_exact_top_product_over_logo(self) -> None:
        product = {"url": "https://docs.espressif.com/media/ESP32-S3-DevKitC-1-front.png", "origin": "img:src", "label": "ESP32-S3-DevKitC-1 front board"}
        logo = {"url": "https://docs.espressif.com/logo.png", "origin": "img:src", "label": "logo"}
        self.assertGreater(official_media.candidate_score(product, "ESP32-S3-DevKitC-1")[0], official_media.candidate_score(logo, "ESP32-S3-DevKitC-1")[0])

    def test_provider_domains_are_fail_closed(self) -> None:
        profile = official_media.provider_for("https://docs.espressif.com/example", "Espressif Systems")
        self.assertEqual(profile["manufacturer"], "Espressif Systems")
        with self.assertRaisesRegex(ValueError, "not official"):
            official_media.provider_for("https://example.com/product", "Espressif Systems")

    def test_png_dimensions(self) -> None:
        body = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + (640).to_bytes(4, "big") + (480).to_bytes(4, "big")
        self.assertEqual(official_media.image_dimensions(body, "image/png"), (640, 480))

    def test_attach_new_primary_clears_old_touchpoints(self) -> None:
        with tempfile.TemporaryDirectory(prefix="official-media-attach-") as temporary:
            root = Path(temporary)
            registry = official_media.ComponentRegistry(root / "registry")
            registry.install({
                "schema": "component-package/v1",
                "identity": {"assetId": "test.chip", "revision": "1.0.0", "manufacturer": "Espressif Systems", "mpn": "ESP32-S3", "level": "wireless-microcontroller", "status": "HUMAN_CALIBRATED"},
                "electrical": {"pins": [{"name": "GND", "number": "1", "direction": "power"}]},
                "visual": {"appearance": "old.png", "appearanceSha256": "a" * 64, "anchors": [{"pin": "GND", "x": 0.5, "y": 0.5}], "coordinateStatus": "HUMAN_CALIBRATED"},
                "physical": {}, "evidence": {"capturedAt": "2026-09-02T00:00:00Z", "sources": []},
            }, {"old.png": b"old"})
            snapshot = root / "snapshot"; snapshot.mkdir()
            image = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + (640).to_bytes(4, "big") + (480).to_bytes(4, "big")
            (snapshot / "original.png").write_bytes(image)
            (snapshot / "official-media.json").write_text(json.dumps({
                "schema": "official-media-snapshot/v1", "image": "original.png", "imageSha256": __import__("hashlib").sha256(image).hexdigest(),
                "mpn": "ESP32-S3", "pageUrl": "https://docs.espressif.com/product", "resourceUrl": "https://docs.espressif.com/top.png",
                "mediaType": "image/png", "capturedAt": "2026-09-02T00:00:00Z", "redistribution": "LOCAL_ONLY_LICENSE_REVIEW_REQUIRED",
            }))
            official_media.attach(snapshot, "test.chip@1.0.0", "1.0.1", "package-top", True, True, root)
            installed = registry.get("test.chip@1.0.1")
            self.assertEqual(installed["visual"]["anchors"], [])
            self.assertEqual(installed["visual"]["coordinateStatus"], "UNCALIBRATED_NEW_APPEARANCE")

    def test_attach_rejects_development_board(self) -> None:
        with tempfile.TemporaryDirectory(prefix="official-media-board-reject-") as temporary:
            root = Path(temporary)
            registry = official_media.ComponentRegistry(root / "registry")
            registry.install({
                "schema": "component-package/v1",
                "identity": {"assetId": "test.board", "revision": "1.0.0", "manufacturer": "Espressif Systems", "mpn": "ESP32-S3-DevKitC-1", "level": "development-board", "status": "UNVERIFIED"},
                "electrical": {"pins": []}, "visual": {"anchors": []}, "physical": {"package": "assembled-board"},
                "evidence": {"sources": []},
            })
            snapshot = root / "snapshot"; snapshot.mkdir()
            image = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + (640).to_bytes(4, "big") + (480).to_bytes(4, "big")
            (snapshot / "original.png").write_bytes(image)
            (snapshot / "official-media.json").write_text(json.dumps({
                "schema": "official-media-snapshot/v1", "image": "original.png", "imageSha256": __import__("hashlib").sha256(image).hexdigest(),
                "mpn": "ESP32-S3-DevKitC-1", "pageUrl": "https://docs.espressif.com/product", "resourceUrl": "https://docs.espressif.com/top.png",
                "mediaType": "image/png", "capturedAt": "2026-09-02T00:00:00Z", "redistribution": "LOCAL_ONLY_LICENSE_REVIEW_REQUIRED",
            }))
            with self.assertRaisesRegex(ValueError, "chip-only acquisition rejected"):
                official_media.attach(snapshot, "test.board@1.0.0", "1.0.1", "package-top", True, True, root)


if __name__ == "__main__":
    unittest.main()
