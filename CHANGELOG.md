# Changelog

## 0.8.2 — 2026-09-03

- Remove the unsubstantiated Sindri Custom standing-desk controller, driver, and handset entries from the distributable catalog and live local registry.
- Stop generating concept artwork for assets without a real product identity or authoritative design source.
- Keep the generic read-only Sindri importer available for future evidence-backed imports.

## 0.8.1 — 2026-09-03

- Correct the Pico W board body so its twenty main pads per side run from the first top pad to the final bottom pad without AI-invented extra corner contacts.
- Realign all 40 main Pico W anchors to the complete edge-pad span.
- Add the three documented SWD points: SWCLK, debug GND, and SWDIO, bringing the Pico W interactive total to 43.

## 0.8.0 — 2026-09-03

- Replace photo galleries in the latest Board revisions with one generated true-top board view.
- Add deterministic interactive overlays for every documented usable point: 28 Feather, 30 Nano 33 IoT, 44 on each ESP32-S3 DevKitC, 40 on Pi Zero 2 WH, and 40 on Pico W.
- Add generated concept top views for the two Sindri custom boards while keeping them explicitly physical-unverified.
- Show semantic colored point rings directly over Board artwork with hover labels and the complete pin table below.
- Keep ImageGen responsible only for the board-body illustration; electrical identity and coordinates remain sourced from official or project pin maps.

## 0.7.0 — 2026-09-02

- Add a repeatable official-evidence → normalized specification → original top-view → touchpoint validation → immutable install workflow.
- Retain fetched official source bytes and SHA-256 metadata in a local-only evidence cache, with offline reuse and fail-closed domain checks.
- Introduce `circuitlab-top-style/v1` with common technical-board styling and semantic power, ground, clock, data, and signal touchpoint colors.
- Add original top views and explicit pins for VEML7700 light, APDS9960 proximity/color/gesture, SHT45 temperature/humidity, and SCD-40 CO2 sensor modules.
- Surface pipeline status, evidence capture totals, validation totals, and drawing style in the Hardware Library.

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
