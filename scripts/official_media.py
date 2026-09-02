#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from _platform import ComponentRegistry, default_data_root, require_chip_package


ROOT = Path(__file__).resolve().parents[1]
PROVIDERS_PATH = ROOT / "references" / "official-media-providers.json"
USER_AGENT = "CircuitLab-Official-Media/0.1 (+https://github.com/b8kings0ga/CircuitLab)"
PAGE_LIMIT = 6 * 1024 * 1024
IMAGE_LIMIT = 24 * 1024 * 1024
RASTER_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


def stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def atomic_bytes(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(body)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path: Path, value: object) -> None:
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


def normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def host_allowed(host: str, domains: list[str]) -> bool:
    host = host.casefold().rstrip(".")
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


def load_providers() -> list[dict[str, Any]]:
    value = json.loads(PROVIDERS_PATH.read_text(encoding="utf-8"))
    return value["providers"]


def provider_for(url: str, manufacturer: str | None = None) -> dict[str, Any]:
    host = urllib.parse.urlparse(url).hostname or ""
    profiles = load_providers()
    if manufacturer:
        exact = [row for row in profiles if row["manufacturer"].casefold() == manufacturer.casefold()]
        if not exact:
            raise ValueError(f"manufacturer is not in the official-domain registry: {manufacturer}")
        profile = exact[0]
        if not host_allowed(host, profile["domains"]):
            raise ValueError(f"page host {host!r} is not official for {profile['manufacturer']}")
        return profile
    for profile in profiles:
        if host_allowed(host, profile["domains"]):
            return profile
    raise ValueError(f"page host is not in the official-domain registry: {host}")


def read_limited(response: Any, limit: int) -> bytes:
    body = response.read(limit + 1)
    if len(body) > limit:
        raise ValueError(f"response exceeds {limit} bytes")
    return body


def fetch_cached(url: str, cache_root: Path, domains: list[str]) -> dict[str, Any]:
    key = hashlib.sha256(url.encode()).hexdigest()
    body_path = cache_root / f"{key}.body"
    meta_path = cache_root / f"{key}.json"
    previous = json.loads(meta_path.read_text()) if meta_path.is_file() and body_path.is_file() else None
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    if previous and previous.get("etag"):
        headers["If-None-Match"] = previous["etag"]
    if previous and previous.get("lastModified"):
        headers["If-Modified-Since"] = previous["lastModified"]
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
            final_url = response.url
            final_host = urllib.parse.urlparse(final_url).hostname or ""
            if not host_allowed(final_host, domains):
                raise ValueError(f"official page redirected outside its provider domains: {final_host}")
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                raise ValueError(f"official page is not HTML: {content_type}")
            body = read_limited(response, PAGE_LIMIT)
            metadata = {
                "url": url,
                "finalUrl": final_url,
                "contentType": content_type,
                "etag": response.headers.get("ETag"),
                "lastModified": response.headers.get("Last-Modified"),
                "fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "cacheStatus": "FRESH",
                "sha256": hashlib.sha256(body).hexdigest(),
            }
            atomic_bytes(body_path, body)
            atomic_json(meta_path, metadata)
            return {**metadata, "body": body}
    except urllib.error.HTTPError as error:
        if error.code == 304 and previous:
            return {**previous, "cacheStatus": "REVALIDATED", "body": body_path.read_bytes()}
        if previous:
            return {**previous, "cacheStatus": "STALE_NETWORK_FALLBACK", "networkError": str(error), "body": body_path.read_bytes()}
        raise ValueError(f"official page returned HTTP {error.code}; save it in a browser and retry with --html") from error
    except (OSError, urllib.error.URLError) as error:
        if previous:
            return {**previous, "cacheStatus": "STALE_NETWORK_FALLBACK", "body": body_path.read_bytes()}
        raise ValueError(f"official page fetch failed; save it in a browser and retry with --html: {error}") from error


class MediaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self._jsonld = False
        self._script: list[str] = []
        self.records: list[dict[str, str]] = []
        self.jsonld: list[str] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.casefold(): value or "" for key, value in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "script" and values.get("type", "").casefold() == "application/ld+json":
            self._jsonld = True
            self._script = []
        elif tag == "meta":
            name = (values.get("property") or values.get("name") or "").casefold()
            if "image" in name and values.get("content"):
                self.records.append({"url": values["content"], "origin": name, "label": values.get("content", "")})
        elif tag == "link":
            rel = values.get("rel", "").casefold()
            if ("image_src" in rel or ("preload" in rel and values.get("as") == "image")) and values.get("href"):
                self.records.append({"url": values["href"], "origin": f"link:{rel}", "label": values.get("title", "")})
        elif tag in {"img", "source"}:
            label = " ".join(filter(None, (values.get("alt"), values.get("title"), values.get("aria-label"))))
            for key in ("src", "data-src", "data-original"):
                if values.get(key):
                    self.records.append({"url": values[key], "origin": f"{tag}:{key}", "label": label})
            for key in ("srcset", "data-srcset"):
                for item in values.get(key, "").split(","):
                    candidate = item.strip().split(" ", 1)[0]
                    if candidate:
                        self.records.append({"url": candidate, "origin": f"{tag}:{key}", "label": label})

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._jsonld:
            self.jsonld.append("".join(self._script))
            self._jsonld = False
            self._script = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._jsonld:
            self._script.append(data)
        elif data.strip():
            self.text.append(data.strip())


def jsonld_images(value: Any, label: str = "") -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    if isinstance(value, dict):
        next_label = str(value.get("name") or value.get("caption") or label)
        for key, item in value.items():
            if key in {"image", "contentUrl", "thumbnailUrl"}:
                if isinstance(item, str):
                    found.append({"url": item, "origin": f"jsonld:{key}", "label": next_label})
                elif isinstance(item, list):
                    for child in item:
                        if isinstance(child, str):
                            found.append({"url": child, "origin": f"jsonld:{key}", "label": next_label})
                        else:
                            found.extend(jsonld_images(child, next_label))
                elif isinstance(item, dict) and isinstance(item.get("url"), str):
                    found.append({"url": item["url"], "origin": f"jsonld:{key}", "label": next_label})
                    found.extend(jsonld_images(item, next_label))
                else:
                    found.extend(jsonld_images(item, next_label))
            elif isinstance(item, (dict, list)):
                found.extend(jsonld_images(item, next_label))
    elif isinstance(value, list):
        for item in value:
            found.extend(jsonld_images(item, label))
    return found


def classify(label: str, url: str) -> tuple[str, str]:
    text = f"{label} {urllib.parse.unquote(url)}".casefold()
    if any(word in text for word in ("pinout", "pin-layout", "pinlayout", "block-diagram", "schematic")):
        return "diagram", "diagram"
    if any(word in text for word in ("bottom", "back", "rear")):
        return "product", "orthographic-bottom"
    if any(word in text for word in ("isometric", "iso.", "angle", "perspective")):
        return "product", "isometric-front"
    if any(word in text for word in ("front", "top", "annotated", "board", "product")):
        return "product", "orthographic-top-candidate"
    return "unknown", "unknown"


def candidate_score(record: dict[str, str], mpn: str) -> tuple[int, list[str]]:
    label_url = f"{record.get('label', '')} {urllib.parse.unquote(record['url'])}"
    normalized = normalize_token(label_url)
    score = 0
    reasons: list[str] = []
    if normalize_token(mpn) in normalized:
        score += 80; reasons.append("exact-mpn-in-image-metadata")
    origin = record.get("origin", "")
    if origin.startswith("jsonld"):
        score += 35; reasons.append("structured-product-data")
    elif "og:image" in origin:
        score += 30; reasons.append("open-graph-primary")
    elif origin.startswith("img"):
        score += 15; reasons.append("page-image")
    role, view = classify(record.get("label", ""), record["url"])
    if role == "product":
        score += 35; reasons.append(view)
    elif role == "diagram":
        score -= 25; reasons.append("diagram-not-photo")
    lowered = label_url.casefold()
    if any(word in lowered for word in ("logo", "icon", "avatar", "flag", "spinner", "loading")):
        score -= 100; reasons.append("decorative-image")
    if any(word in lowered for word in ("annotated", "callout")):
        score -= 15; reasons.append("annotation-overlay")
    if any(part in urllib.parse.urlparse(record["url"]).path.casefold() for part in (".png", ".jpg", ".jpeg", ".webp")):
        score += 10; reasons.append("raster-url")
    return score, reasons


def discover(page_url: str, mpn: str, data_root: Path, manufacturer: str | None = None, page_identity: str | None = None, html_path: Path | None = None) -> dict[str, Any]:
    profile = provider_for(page_url, manufacturer)
    if html_path:
        body = html_path.read_bytes()
        if len(body) > PAGE_LIMIT:
            raise ValueError(f"browser HTML snapshot exceeds {PAGE_LIMIT} bytes")
        fetched = {
            "finalUrl": page_url,
            "body": body,
            "sha256": hashlib.sha256(body).hexdigest(),
            "cacheStatus": "USER_BROWSER_HTML_SNAPSHOT",
        }
    else:
        fetched = fetch_cached(page_url, data_root / "official-media" / "http-cache", profile["domains"])
    charset = "utf-8"
    html = fetched["body"].decode(charset, "replace")
    parser = MediaParser(); parser.feed(html)
    records = list(parser.records)
    for raw in parser.jsonld:
        try:
            records.extend(jsonld_images(json.loads(raw)))
        except json.JSONDecodeError:
            continue
    page_text = " ".join([parser.title, *parser.text])
    identity_on_page = page_identity or mpn
    exact_on_page = normalize_token(identity_on_page) in normalize_token(page_text)
    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []
    for record in records:
        absolute = urllib.parse.urljoin(fetched["finalUrl"], record["url"])
        parsed = urllib.parse.urlparse(absolute)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or not host_allowed(parsed.hostname, profile["domains"]):
            continue
        absolute = urllib.parse.urlunparse(parsed._replace(fragment=""))
        if absolute in seen:
            continue
        seen.add(absolute)
        record = {**record, "url": absolute}
        score, reasons = candidate_score(record, mpn)
        role, view = classify(record.get("label", ""), absolute)
        candidates.append({
            "id": hashlib.sha256(absolute.encode()).hexdigest()[:16],
            "url": absolute,
            "label": record.get("label", ""),
            "origin": record.get("origin", ""),
            "role": role,
            "view": view,
            "score": score,
            "reasons": reasons,
        })
    candidates.sort(key=lambda row: (-row["score"], row["url"]))
    return {
        "schema": "official-media-discovery/v1",
        "status": "CANDIDATES_SELECTION_REQUIRED" if exact_on_page else "MPN_NOT_CONFIRMED_ON_PAGE",
        "manufacturer": profile["manufacturer"],
        "mpn": mpn,
        "pageIdentity": identity_on_page,
        "pageUrl": page_url,
        "finalPageUrl": fetched["finalUrl"],
        "pageSha256": fetched["sha256"],
        "pageCacheStatus": fetched["cacheStatus"],
        "exactMpnOnPage": exact_on_page,
        "candidates": candidates,
    }


def image_dimensions(body: bytes, content_type: str) -> tuple[int | None, int | None]:
    if content_type == "image/png" and body[:8] == b"\x89PNG\r\n\x1a\n" and len(body) >= 24:
        return struct.unpack(">II", body[16:24])
    if content_type == "image/jpeg" and body[:2] == b"\xff\xd8":
        offset = 2
        while offset + 9 < len(body):
            if body[offset] != 0xFF:
                offset += 1; continue
            marker = body[offset + 1]
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                height, width = struct.unpack(">HH", body[offset + 5:offset + 9])
                return width, height
            if offset + 4 > len(body): break
            length = struct.unpack(">H", body[offset + 2:offset + 4])[0]
            offset += 2 + max(length, 2)
    if content_type == "image/webp" and body[:4] == b"RIFF" and body[8:12] == b"WEBP" and body[12:16] == b"VP8X" and len(body) >= 30:
        width = 1 + int.from_bytes(body[24:27], "little")
        height = 1 + int.from_bytes(body[27:30], "little")
        return width, height
    return None, None


def capture(discovery: dict[str, Any], candidate_id: str, data_root: Path, confirmed: bool, image_path: Path | None = None) -> dict[str, Any]:
    if not confirmed:
        raise ValueError("capture requires explicit exact-MPN confirmation")
    if not discovery.get("exactMpnOnPage"):
        raise ValueError("exact MPN was not found on the official page")
    candidate = next((row for row in discovery["candidates"] if row["id"] == candidate_id), None)
    if not candidate:
        raise ValueError(f"candidate does not exist: {candidate_id}")
    profile = provider_for(discovery["finalPageUrl"], discovery["manufacturer"])
    if image_path:
        body = image_path.read_bytes()
        if len(body) > IMAGE_LIMIT:
            raise ValueError(f"browser-downloaded image exceeds {IMAGE_LIMIT} bytes")
        signatures = {
            b"\x89PNG\r\n\x1a\n": "image/png",
            b"\xff\xd8": "image/jpeg",
            b"RIFF": "image/webp",
        }
        content_type = next((kind for signature, kind in signatures.items() if body.startswith(signature)), "")
        if content_type == "image/webp" and body[8:12] != b"WEBP":
            content_type = ""
        if content_type not in RASTER_TYPES:
            raise ValueError("browser-downloaded file is not PNG, JPEG, or WebP")
        final_url = candidate["url"]
        etag = None; last_modified = None
        transport = "USER_BROWSER_DOWNLOAD"
    else:
        request = urllib.request.Request(candidate["url"], headers={"User-Agent": USER_AGENT, "Accept": "image/png,image/jpeg,image/webp"})
        with urllib.request.urlopen(request, timeout=30) as response:
            final_url = response.url
            host = urllib.parse.urlparse(final_url).hostname or ""
            if not host_allowed(host, profile["domains"]):
                raise ValueError(f"image redirected outside official domains: {host}")
            content_type = response.headers.get_content_type()
            if content_type not in RASTER_TYPES:
                raise ValueError(f"candidate is not a supported raster image: {content_type}")
            body = read_limited(response, IMAGE_LIMIT)
            etag = response.headers.get("ETag")
            last_modified = response.headers.get("Last-Modified")
        transport = "DIRECT_OFFICIAL_HTTP"
    digest = hashlib.sha256(body).hexdigest()
    width, height = image_dimensions(body, content_type)
    snapshot_id = hashlib.sha256(f"{discovery['pageSha256']}\n{final_url}\n{digest}".encode()).hexdigest()[:24]
    directory = data_root / "official-media" / "snapshots" / snapshot_id
    image_name = f"original{RASTER_TYPES[content_type]}"
    if directory.exists():
        current = json.loads((directory / "official-media.json").read_text())
        if current["imageSha256"] != digest:
            raise ValueError(f"immutable official-media snapshot conflict: {snapshot_id}")
        return current
    metadata = {
        "schema": "official-media-snapshot/v1",
        "snapshotId": snapshot_id,
        "manufacturer": discovery["manufacturer"],
        "mpn": discovery["mpn"],
        "pageUrl": discovery["finalPageUrl"],
        "pageSha256": discovery["pageSha256"],
        "resourceUrl": final_url,
        "candidate": candidate,
        "image": image_name,
        "imageSha256": digest,
        "mediaType": content_type,
        "fetchTransport": transport,
        "width": width,
        "height": height,
        "etag": etag,
        "lastModified": last_modified,
        "capturedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "redistribution": "LOCAL_ONLY_LICENSE_REVIEW_REQUIRED",
        "status": "EXACT_MPN_CONFIRMED_MEDIA_UNREVIEWED",
    }
    atomic_bytes(directory / image_name, body)
    atomic_json(directory / "official-media.json", metadata)
    return metadata


def audit(data_root: Path) -> dict[str, Any]:
    registry = ComponentRegistry(data_root / "registry")
    profiles = load_providers()
    items: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for row in registry.list():
        package = registry.get(row["ref"])
        identity = package["identity"]
        matching = [profile for profile in profiles if profile["manufacturer"].casefold() == identity["manufacturer"].casefold()]
        sources = package.get("evidence", {}).get("sources", [])
        official_images = []
        nonofficial_images = []
        for source in sources:
            resource = source.get("resource_url") or source.get("resourceUrl")
            if not resource or not str(source.get("media_type") or source.get("mediaType") or "").startswith("image/"):
                continue
            host = urllib.parse.urlparse(resource).hostname or ""
            if matching and host_allowed(host, matching[0]["domains"]):
                official_images.append(resource)
            else:
                nonofficial_images.append(resource)
        if official_images:
            status = "OFFICIAL_IMAGE"
        elif nonofficial_images:
            status = "NON_OFFICIAL_IMAGE"
        elif package.get("visual", {}).get("appearance"):
            status = "GENERATED_OR_UNATTRIBUTED_APPEARANCE"
        else:
            status = "NO_APPEARANCE"
        counts[status] = counts.get(status, 0) + 1
        items.append({"ref": row["ref"], "manufacturer": identity["manufacturer"], "mpn": identity["mpn"], "level": identity["level"], "status": status, "officialImages": official_images, "otherImages": nonofficial_images})
    return {"schema": "official-media-audit/v1", "counts": counts, "items": items}


def attach(snapshot_path: Path, reference: str, revision: str, view: str, primary: bool, confirmed_view: bool, data_root: Path) -> dict[str, Any]:
    if not confirmed_view:
        raise ValueError("attach requires explicit view confirmation")
    metadata_path = snapshot_path / "official-media.json" if snapshot_path.is_dir() else snapshot_path
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("schema") != "official-media-snapshot/v1":
        raise ValueError("snapshot schema must be official-media-snapshot/v1")
    registry = ComponentRegistry(data_root / "registry")
    current = registry.get(reference)
    current.pop("procurement", None); current.pop("packageSha256", None)
    require_chip_package(current)
    if normalize_token(metadata["mpn"]) not in normalize_token(current["identity"]["mpn"]) and normalize_token(current["identity"]["mpn"]) not in normalize_token(metadata["mpn"]):
        raise ValueError("snapshot MPN does not match the component identity")
    current["identity"]["revision"] = revision
    current["identity"]["status"] = "PHYSICAL_UNVERIFIED"
    extension = Path(metadata["image"]).suffix
    name = f"official-{view}{extension}"
    visual = current.setdefault("visual", {})
    views = [row for row in visual.get("views", []) if row.get("name") != view]
    views.append({"name": view, "path": name, "view": view, "image_role": "product", "source": "official-media-snapshot"})
    visual["views"] = views
    if primary:
        visual["appearance"] = name
        visual["appearanceSha256"] = metadata["imageSha256"]
        visual["anchors"] = []
        visual["coordinateStatus"] = "UNCALIBRATED_NEW_APPEARANCE"
    current.setdefault("evidence", {}).setdefault("sources", []).append({
        "type": "manufacturer-product-image",
        "page_url": metadata["pageUrl"],
        "resource_url": metadata["resourceUrl"],
        "original_sha256": metadata["imageSha256"],
        "media_type": metadata["mediaType"],
        "retrieved_at": metadata["capturedAt"],
        "redistribution": metadata["redistribution"],
        "selection": {"subject_match": "exact", "view": view, "review": "human-confirmed"},
    })
    body = (metadata_path.parent / metadata["image"]).read_bytes()
    return registry.install(current, {name: body})


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover and freeze official chip-package images for MCU, SoC, sensor, and support IC assets.")
    parser.add_argument("--data", type=Path, default=default_data_root())
    sub = parser.add_subparsers(dest="command", required=True)
    find = sub.add_parser("discover")
    find.add_argument("page_url"); find.add_argument("--mpn", required=True); find.add_argument("--manufacturer")
    find.add_argument("--page-identity"); find.add_argument("--html", type=Path)
    freeze = sub.add_parser("capture")
    freeze.add_argument("page_url"); freeze.add_argument("--mpn", required=True); freeze.add_argument("--manufacturer")
    freeze.add_argument("--page-identity"); freeze.add_argument("--html", type=Path); freeze.add_argument("--image-file", type=Path)
    freeze.add_argument("--candidate", required=True); freeze.add_argument("--confirm-exact-mpn", action="store_true")
    add = sub.add_parser("attach")
    add.add_argument("snapshot", type=Path); add.add_argument("--ref", required=True); add.add_argument("--revision", required=True)
    add.add_argument("--view", required=True, choices=("package-top", "package-bottom", "package-drawing", "pinout"))
    add.add_argument("--primary", action="store_true"); add.add_argument("--confirm-view", action="store_true")
    sub.add_parser("audit")
    args = parser.parse_args()
    data_root = args.data.expanduser().resolve()
    if args.command == "discover":
        result = discover(args.page_url, args.mpn, data_root, args.manufacturer, args.page_identity, args.html.expanduser().resolve() if args.html else None)
    elif args.command == "capture":
        discovery = discover(args.page_url, args.mpn, data_root, args.manufacturer, args.page_identity, args.html.expanduser().resolve() if args.html else None)
        result = capture(discovery, args.candidate, data_root, args.confirm_exact_mpn, args.image_file.expanduser().resolve() if args.image_file else None)
    elif args.command == "attach":
        result = attach(args.snapshot.expanduser().resolve(), args.ref, args.revision, args.view, args.primary, args.confirm_view, data_root)
    else:
        result = audit(data_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, urllib.error.URLError) as error:
        raise SystemExit(str(error)) from error
