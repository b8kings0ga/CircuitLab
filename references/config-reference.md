# Configuration Reference

`circuit-lab.json` uses `schemaVersion: 1` and records the vendored core with `templateVersion`.

Top-level fields:

- `id`: stable lab identifier.
- `diagram`: JSON path relative to the config.
- `adapter`: Python `module:factory` relative to the instance root.
- `data`: environment variable, default data directory, and layout filename.
- `frontend`: browser-safe declarative settings returned by `/api/lab-config`.

Frontend groups:

- `partSizes`: unrotated CSS-pixel dimensions keyed by diagram part type.
- `boards`: board type to local SVG and board geometry JSON URLs.
- `orientations`: optional front-face label keyed by part ID.
- `keyboard`: `KeyboardEvent.code` to part ID.
- `controls`: `momentary`, `toggle`, or `indicator` definitions with state paths and adapter payloads.
- `displays`: state-driven SSD1306 pixel displays keyed by part ID. Items support text, lines, and progress bars using the same dot paths and templates as the status UI.
- `ui`: status strip and state panel fields. Dot paths support array indexes such as `fingers.0`.
- `wiring`: expected pairs, ground network IDs, shared/power/ground pins, trace labels, and Wiring rows.

Board geometry JSON requires numeric `width`, `height`, and either an object of named `{x,y}` pins or an array of `{name,x,y}` pins. Coordinates use the same coordinate system as the board SVG.

The managed Wokwi Elements runtime is under `assets/template/core/web/vendor/wokwi/elements`; its catalog records default runtime `pinInfo`. Public CircuitLab distributions intentionally exclude Wokwi board artwork. A local `boards/catalog.json` may be generated from a pinned checkout only after the relevant board licenses are reviewed.

The diagram uses Wokwi-style `parts` and `connections`. Each connection starts with two references in `part-id:pin-name` form. The first two entries and their order must match `expectedConnections` exactly.
