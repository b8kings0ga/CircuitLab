# Changelog

## 0.6.0 — 2026-09-02

- Expand the primary Hardware Library to boards, single-board computers, sensor modules, displays, and packaged chips.
- Show official/local component imagery as thumbnails and prioritize pinout diagrams in component details.
- Add deterministic original top-view SVG assets for XIAO ESP32S3, Orange Pi Zero 3, Waveshare OLED, VL53L1X distance, LIS3MDL magnetic, BME688 gas/VOC, and SPH0645LM4H sound modules.
- Install the seven offline starter assets automatically for every fresh CircuitLab project.
- Preserve Espressif's imported product media while adding the official 44-pin J1/J3 table as a new immutable ESP32-S3-DevKitC-1 revision.

## 0.5.0 — 2026-09-02

- Open CircuitLab directly on a dedicated Sensors & MCUs catalog.
- Separate sensors, MCU/SoC parts, support ICs, and the complete chip list.
- Classify sensor chips into environment, motion/IMU, current, and general sensor groups.
- Keep filters grounded in immutable component metadata instead of adding placeholder devices.

## 0.4.0 — 2026-09-02

- Make packaged chips the default and enforced acquisition scope.
- Show only the latest revision of MCU/SoC, sensor IC, and support-IC assets in the PWA.
- Keep board, module, assembly, display, motor, switch, supply, passive, and other historical imports out of the default catalog.
- Reject non-chip assets from normal API/CLI acquisition and official-media attachment.
- Retain an explicit all-history audit path without deleting immutable evidence.

## 0.3.0 — 2026-09-02

- Add deterministic `board-view-spec/v1` to original interactive SVG generation.
- Add a XIAO ESP32S3 reference view with 14 explicit wireable touchpoints.
- Lock the official Seeed Studio DXF and pinout evidence by SHA-256.
- Expose component geometry files through the local media API for Workbench consumers.
- Keep design-derived boards fail-closed as `OFFICIAL_DESIGN_DERIVED_UNVERIFIED`.

## 0.2.0 — 2026-09-02

- Add fail-closed official manufacturer media discovery for MCU, module, and development-board pages.
- Add immutable image snapshots with URL, page/image hashes, HTTP validators, dimensions, and licensing status.
- Add human-confirmed attachment that creates a new component revision and invalidates stale touchpoints.
- Add browser-snapshot fallback for official sites that block automated HTTP access.
- Add registry-wide official-media provenance audit.
- Display component product photos and diagrams directly in the Components interface.

## 0.1.0 — 2026-09-02

- Initial standalone CircuitLab release.
