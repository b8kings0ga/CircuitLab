#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _platform import ComponentRegistry, default_data_root


def fetch_digikey(mpn: str) -> dict:
    client_id = os.environ.get("DIGIKEY_CLIENT_ID")
    token = os.environ.get("DIGIKEY_ACCESS_TOKEN")
    if not client_id or not token:
        raise ValueError("DigiKey requires DIGIKEY_CLIENT_ID and DIGIKEY_ACCESS_TOKEN")
    url = f"https://api.digikey.com/products/v4/search/{urllib.parse.quote(mpn)}/productdetails"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "X-DIGIKEY-Client-Id": client_id, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def fetch_mouser(mpn: str) -> dict:
    key = os.environ.get("MOUSER_API_KEY")
    if not key:
        raise ValueError("Mouser requires MOUSER_API_KEY")
    url = f"https://api.mouser.com/api/v2/search/partnumber?apiKey={urllib.parse.quote(key)}"
    body = json.dumps({"SearchByPartRequest": {"mouserPartNumber": mpn, "partSearchOptions": "Exact"}}).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser(description="Record a read-only DigiKey or Mouser procurement snapshot; never purchases.")
    parser.add_argument("provider", choices=["digikey", "mouser"])
    parser.add_argument("reference")
    parser.add_argument("mpn")
    parser.add_argument("--data", type=Path, default=default_data_root())
    args = parser.parse_args()
    registry = ComponentRegistry(args.data.expanduser().resolve() / "registry")
    payload = fetch_digikey(args.mpn) if args.provider == "digikey" else fetch_mouser(args.mpn)
    sampled = datetime.now(timezone.utc)
    result = registry.add_procurement_snapshot(args.reference, {
        "provider": args.provider,
        "sampledAt": sampled.isoformat(),
        "staleAfter": (sampled + timedelta(hours=24)).isoformat(),
        "payload": payload,
    })
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

