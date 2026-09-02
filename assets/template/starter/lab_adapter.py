from __future__ import annotations

import threading
import time
from typing import Any


class StarterAdapter:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.button = False
        self.cursor = 0
        self.events: list[dict[str, Any]] = []

    def snapshot(self, since: int = 0) -> dict[str, Any]:
        with self.lock:
            return {
                "button": self.button,
                "led": self.button,
                "connected": True,
                "event_cursor": self.cursor,
                "events": [event for event in self.events if event["id"] > since],
            }

    def apply(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            event_type = payload.get("type")
            if event_type == "reset":
                self.button = False
            elif event_type == "button" and isinstance(payload.get("down"), bool):
                self.button = payload["down"]
            else:
                raise ValueError(f"unsupported input: {event_type}")
            self.cursor += 1
            self.events.append({
                "id": self.cursor,
                "time_ms": int(time.monotonic() * 1000),
                "name": event_type.upper(),
                "down": self.button,
            })
            return self.snapshot()


def create_adapter(_config: dict[str, Any]) -> StarterAdapter:
    return StarterAdapter()
