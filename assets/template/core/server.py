from __future__ import annotations

import argparse
import importlib
import json
import math
import mimetypes
import os
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from circuitlab_platform import CircuitLabPlatform, generate_fixture


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
CONFIG_PATH = ROOT / "circuit-lab.json"
DIAGRAM_PATH: Path | None = None
PROJECT_ASSET_ROOT: Path | None = None
LAYOUT_PATH: Path | None = None
LAYOUT_LOCK = threading.Lock()
CONFIG: dict[str, Any] = {}
ADAPTER: Any = None
PLATFORM: CircuitLabPlatform | None = None
PLATFORM_ROOT: Path | None = None


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def validate_config(config: object, base: Path) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise ValueError("circuit lab config must be an object")
    if config.get("schemaVersion") not in {1, 2}:
        raise ValueError("CircuitLab config schemaVersion must be 1 or 2")
    for key in ("id", "diagram", "adapter", "frontend"):
        if key not in config:
            raise ValueError(f"circuit lab config is missing {key}")
    diagram = (base / str(config["diagram"])).resolve()
    if not diagram.is_file():
        raise ValueError(f"diagram does not exist: {diagram}")
    adapter = config["adapter"]
    if not isinstance(adapter, str) or ":" not in adapter:
        raise ValueError("adapter must use module:factory syntax")
    if not isinstance(config["frontend"], dict):
        raise ValueError("frontend must be an object")
    return config


def _default_layout_path(config: dict[str, Any]) -> Path:
    data = config.get("data", {})
    env_name = str(data.get("env", "CIRCUIT_LAB_DATA_DIR"))
    configured = os.environ.get(env_name)
    if configured:
        directory = Path(configured).expanduser()
    else:
        directory = Path(str(data.get("default", "~/.local/share/circuit-lab"))).expanduser()
    return directory / str(data.get("layout", "circuit-layout.json"))


def _default_platform_root(config: dict[str, Any]) -> Path:
    platform = config.get("platform", {})
    configured = os.environ.get(str(platform.get("env", "CIRCUITLAB_DATA_DIR")))
    if configured:
        return Path(configured).expanduser()
    explicit = platform.get("default")
    if explicit:
        return Path(str(explicit)).expanduser()
    return _default_layout_path(config).parent / "circuitlab"


def configure(path: Path | str = CONFIG_PATH, *, create_adapter: bool = True) -> dict[str, Any]:
    global ADAPTER, CONFIG, CONFIG_PATH, DIAGRAM_PATH, PLATFORM, PLATFORM_ROOT, PROJECT_ASSET_ROOT
    resolved = Path(path).expanduser().resolve()
    config = validate_config(_load_json(resolved), resolved.parent)
    CONFIG_PATH = resolved
    CONFIG = config
    DIAGRAM_PATH = (resolved.parent / str(config["diagram"])).resolve()
    asset_path = config.get("assets")
    PROJECT_ASSET_ROOT = (resolved.parent / str(asset_path)).resolve() if asset_path else None
    PLATFORM = None
    PLATFORM_ROOT = _default_platform_root(config)
    if PROJECT_ASSET_ROOT is not None and not PROJECT_ASSET_ROOT.is_dir():
        raise ValueError(f"project assets do not exist: {PROJECT_ASSET_ROOT}")
    if create_adapter:
        if str(resolved.parent) not in sys.path:
            sys.path.insert(0, str(resolved.parent))
        module_name, factory_name = str(config["adapter"]).split(":", 1)
        module = importlib.import_module(module_name)
        factory = getattr(module, factory_name, None)
        if not callable(factory):
            raise ValueError(f"adapter factory is not callable: {config['adapter']}")
        ADAPTER = factory(config)
        for method in ("snapshot", "apply"):
            if not callable(getattr(ADAPTER, method, None)):
                raise ValueError(f"adapter is missing {method}()")
    return config


def circuit_platform() -> CircuitLabPlatform:
    global PLATFORM
    if PLATFORM is None:
        if PLATFORM_ROOT is None:
            raise ValueError("CircuitLab platform storage is not configured")
        PLATFORM = CircuitLabPlatform(PLATFORM_ROOT, CONFIG, CONFIG_PATH)
    return PLATFORM


def _base_diagram() -> dict[str, Any]:
    if DIAGRAM_PATH is None:
        raise ValueError("circuit lab is not configured")
    return _load_json(DIAGRAM_PATH)


def _movable_part_ids(diagram: dict[str, Any]) -> set[str]:
    return {
        str(part["id"])
        for part in diagram.get("parts", [])
        if part.get("type") != "wokwi-text"
    }


def _connection_keys(diagram: dict[str, Any]) -> set[str]:
    return {f"{connection[0]}>{connection[1]}" for connection in diagram.get("connections", [])}


def _finite_coordinate(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and abs(value) <= 10_000
    )


def validate_layout(payload: object, diagram: dict[str, Any] | None = None) -> dict[str, Any]:
    diagram = diagram or _base_diagram()
    if not isinstance(payload, dict) or not isinstance(payload.get("parts"), dict):
        raise ValueError("layout must contain a parts object")
    allowed = _movable_part_ids(diagram)
    parts: dict[str, dict[str, float]] = {}
    for part_id, position in payload["parts"].items():
        if part_id not in allowed:
            raise ValueError(f"unknown movable part: {part_id}")
        if not isinstance(position, dict):
            raise ValueError(f"invalid position for {part_id}")
        left = position.get("left")
        top = position.get("top")
        if not _finite_coordinate(left) or not _finite_coordinate(top):
            raise ValueError(f"invalid coordinates for {part_id}")
        parts[part_id] = {"left": round(float(left), 3), "top": round(float(top), 3)}
        if "rotate" in position:
            rotate = position["rotate"]
            if (
                not isinstance(rotate, (int, float))
                or isinstance(rotate, bool)
                or not math.isfinite(rotate)
                or rotate % 90 != 0
            ):
                raise ValueError(f"invalid rotation for {part_id}")
            parts[part_id]["rotate"] = float(rotate) % 360
    wires_payload = payload.get("wires", {})
    if not isinstance(wires_payload, dict):
        raise ValueError("layout wires must be an object")
    allowed_wires = _connection_keys(diagram)
    wires: dict[str, dict[str, Any]] = {}
    for wire_id, route in wires_payload.items():
        if wire_id not in allowed_wires:
            raise ValueError(f"unknown wire: {wire_id}")
        if (
            not isinstance(route, dict)
            or not _finite_coordinate(route.get("x"))
            or not _finite_coordinate(route.get("y"))
        ):
            raise ValueError(f"invalid route for {wire_id}")
        wires[wire_id] = {
            "x": round(float(route["x"]), 3),
            "y": round(float(route["y"]), 3),
        }
        if "style" in route:
            if route["style"] not in {"hv", "vh"}:
                raise ValueError(f"invalid route style for {wire_id}")
            wires[wire_id]["style"] = route["style"]
    ground_bus_y = payload.get("groundBusY")
    if ground_bus_y is not None and not _finite_coordinate(ground_bus_y):
        raise ValueError("invalid ground bus position")
    return {
        "parts": parts,
        "wires": wires,
        "groundBusY": None if ground_bus_y is None else round(float(ground_bus_y), 3),
    }


def load_diagram() -> dict[str, Any]:
    diagram = _base_diagram()
    if LAYOUT_PATH is None or not LAYOUT_PATH.is_file():
        return diagram
    try:
        layout = validate_layout(_load_json(LAYOUT_PATH), diagram)
    except (OSError, ValueError, json.JSONDecodeError):
        return diagram
    for part in diagram["parts"]:
        if part["id"] in layout["parts"]:
            part.update(layout["parts"][part["id"]])
    diagram["layout"] = {
        "wires": layout["wires"],
        "groundBusY": layout["groundBusY"],
    }
    return diagram


def save_layout(payload: object) -> dict[str, Any]:
    if LAYOUT_PATH is None:
        raise ValueError("layout persistence is not configured")
    layout = validate_layout(payload)
    body = json.dumps({"version": 2, **layout}, ensure_ascii=False, indent=2) + "\n"
    with LAYOUT_LOCK:
        LAYOUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = LAYOUT_PATH.with_name(f".{LAYOUT_PATH.name}.tmp")
        try:
            temporary.write_text(body, encoding="utf-8")
            os.replace(temporary, LAYOUT_PATH)
        finally:
            temporary.unlink(missing_ok=True)
    return layout


def clear_layout() -> None:
    if LAYOUT_PATH is None:
        return
    with LAYOUT_LOCK:
        LAYOUT_PATH.unlink(missing_ok=True)


def public_config() -> dict[str, Any]:
    return {
        "schemaVersion": CONFIG["schemaVersion"],
        "templateVersion": CONFIG.get("templateVersion", 1),
        "id": CONFIG["id"],
        **CONFIG["frontend"],
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "CircuitLab/2.0"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/diagram":
            self._json(load_diagram())
            return
        if parsed.path == "/api/lab-config":
            self._json(public_config())
            return
        if parsed.path == "/api/state":
            params = parse_qs(parsed.query)
            since = int(params.get("since", ["0"])[0])
            self._json(ADAPTER.snapshot(since))
            return
        if parsed.path == "/api/platform":
            self._json(circuit_platform().info())
            return
        if parsed.path == "/api/projects":
            self._json({"projects": circuit_platform().projects()})
            return
        if parsed.path == "/api/components":
            query = parse_qs(parsed.query).get("q", [""])[0]
            self._json({"components": circuit_platform().registry.list(query)})
            return
        if parsed.path.startswith("/api/components/"):
            reference = unquote(parsed.path.removeprefix("/api/components/"))
            self._json(circuit_platform().registry.get(reference))
            return
        if parsed.path == "/api/hil/status":
            job_id = parse_qs(parsed.query).get("job", [None])[0]
            self._json(circuit_platform().hil.status(job_id))
            return
        if parsed.path == "/api/reports":
            self._json({"reports": circuit_platform().hil.reports_list()})
            return
        if parsed.path == "/healthz":
            self._json({"ok": True, "lab": CONFIG["id"], "templateVersion": CONFIG.get("templateVersion", 1)})
            return
        self._static(parsed.path)

    def do_HEAD(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self._json({"ok": True}, send_body=False)
            return
        self._static(parsed.path, send_body=False)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        routes = {
            "/api/input", "/api/layout", "/api/components/acquire",
            "/api/components/procurement", "/api/touchpoints/calibrate",
            "/api/fixture/generate", "/api/hil/prepare", "/api/hil/arm",
            "/api/hil/run", "/api/hil/abort", "/api/hil/restore",
        }
        if parsed.path not in routes:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            if parsed.path == "/api/layout":
                self._json({"ok": True, "layout": save_layout(payload)})
            elif parsed.path == "/api/input":
                self._json(ADAPTER.apply(payload))
            elif parsed.path == "/api/components/acquire":
                if payload.get("confirmed") is not True:
                    raise ValueError("component acquisition requires confirmed=true for the exact MPN")
                self._json(circuit_platform().registry.install(payload.get("package")))
            elif parsed.path == "/api/components/procurement":
                self._json(circuit_platform().registry.add_procurement_snapshot(payload.get("ref", ""), payload.get("snapshot", {})))
            elif parsed.path == "/api/touchpoints/calibrate":
                self._json(circuit_platform().registry.calibrate(payload.get("ref", ""), payload.get("appearanceSha256", ""), payload.get("points", {})))
            elif parsed.path == "/api/fixture/generate":
                self._json(generate_fixture(payload, circuit_platform().fixtures))
            elif parsed.path == "/api/hil/prepare":
                self._json(circuit_platform().hil.prepare(payload))
            elif parsed.path == "/api/hil/arm":
                self._json(circuit_platform().hil.arm(payload.get("jobId", ""), payload.get("nonce", ""), payload.get("acknowledged") is True))
            elif parsed.path == "/api/hil/run":
                self._json(circuit_platform().hil.run(payload.get("jobId", ""), payload.get("options", {})))
            elif parsed.path == "/api/hil/abort":
                self._json(circuit_platform().hil.abort(payload.get("jobId", "")))
            elif parsed.path == "/api/hil/restore":
                raise ValueError("restore remains fail-closed until a hash-verified physical backup exists")
        except (ValueError, json.JSONDecodeError) as error:
            self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except KeyError as error:
            self._json({"error": f"not found: {error.args[0]}"}, HTTPStatus.NOT_FOUND)
        except OSError as error:
            self._json({"error": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_DELETE(self) -> None:  # noqa: N802
        if self.path != "/api/layout":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        clear_layout()
        self._json({"ok": True})

    def log_message(self, format: str, *args: object) -> None:
        return

    def _static(self, request_path: str, send_body: bool = True) -> None:
        if request_path.startswith("/project-assets/") and PROJECT_ASSET_ROOT is not None:
            root = PROJECT_ASSET_ROOT.resolve()
            relative = request_path.removeprefix("/project-assets/")
        else:
            root = WEB_ROOT.resolve()
            relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        candidate = (root / relative).resolve()
        if root not in candidate.parents and candidate != root:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        body = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if send_body:
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _json(
        self,
        payload: object,
        status: HTTPStatus = HTTPStatus.OK,
        send_body: bool = True,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if send_body:
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass


def main() -> None:
    global LAYOUT_PATH
    parser = argparse.ArgumentParser(description="Run an offline CircuitLab instance.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--layout", type=Path)
    args = parser.parse_args()
    configure(args.config)
    LAYOUT_PATH = args.layout.expanduser() if args.layout else _default_layout_path(CONFIG)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"CircuitLab: http://{args.host}:{args.port} ({CONFIG['id']})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if CONFIG_PATH.is_file():
    configure(CONFIG_PATH)


if __name__ == "__main__":
    main()
