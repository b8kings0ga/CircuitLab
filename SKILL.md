---
name: circuitlab
description: Build, operate, and verify portable local circuit-development workspaces with component acquisition, visual and pogo touchpoints, interactive wiring, software HIL, fixture packages, and auditable reports. Use for CircuitLab projects, Rune hardware simulation, component assets, test fixtures, or low-voltage embedded HIL.
---

# CircuitLab

This repository is the canonical generic core and installable Codex Skill. Keep project behavior in `circuit-lab.json` and its adapter; never add project-specific state or pin names to the core. CircuitLab is local-first and single-user. Rune is an optional downstream adapter and Sindri may be imported read-only, but neither is a runtime dependency.

## Choose The Workflow

- New lab: run `scripts/init_lab.py TARGET`, edit the generated config/diagram/adapter, then run `scripts/validate_instance.py TARGET`.
- Existing instance: inspect live `/healthz`, `/api/lab-config`, `/api/diagram`, and `/api/state` before editing.
- Component work: read [component assets](references/component-assets.md). The default scope is packaged chips only: MCU/SoC, sensor IC, and supporting analog/interface/driver/logic/memory/power ICs. Search the latest local revision first, acquire only an exact confirmed MPN, and reject development boards, modules, PCB assemblies, displays, motors, switches, power supplies, and passives. Use the discover → capture → human-confirmed attach flow for official package images; never infer electrical identity from pixels.
- Touchpoint or fixture work is secondary while chip acquisition is the active scope. When explicitly requested, read [fixtures](references/fixtures.md); never infer electrical identity from image coordinates.
- HIL work: read [HIL safety](references/hil.md); software mock/replay is available, while real serial, flash, power, restore, purchase, and fabrication remain fail-closed until separately verified and authorized.
- Generic rendering or routing change: edit `assets/template/core`, run `scripts/update_manifest.py`, run `sync_instance.py --apply`, and test both a fresh lab and the project instance.
- Wokwi asset refresh: clone official `wokwi-elements` and `wokwi-boards`, run `scripts/import_wokwi_assets.py`, update the template manifest, then sync and verify every project.
- Project behavior change: edit only its config, diagram, adapter, or tests. The vendored core must still pass `sync_instance.py --check`.
- Rune integration is downstream-only: follow [references/rune-workflow.md](references/rune-workflow.md) without copying Rune-specific state into this repository.

## Required Validation

1. Run `scripts/validate_instance.py`.
2. Run project unit tests for adapter state transitions and layout persistence.
3. Start on a spare port and verify API compatibility.
4. Verify DPR 1 and 2 in Playwright: nonblank canvas, visible endpoints, anchor error at most 1 CSS px, dragging, rotation, routing, selection, and persistence.
5. Deploy only after local checks; then verify the installed copy, service health, logs, and checksum.
6. For platform changes, run `scripts/verify_platform.py` and complete the Components → Touchpoints → Fixture → HIL → Reports software loop.

## Core Contract

- `server.py` owns static serving, APIs, diagram overlay, version 2 layout validation, and atomic persistence.
- `circuitlab_platform.py` owns immutable component packages, the derived SQLite index, fixture output, and the HIL state machine.
- `web/` owns rendering, live pin anchors, HVH/VHV routes, module transforms, wire tracing, and config-driven controls/status.
- `circuit-lab.json` owns all board assets, dimensions, controls, keyboard bindings, expected wiring, labels, and state presentation.
- The adapter factory uses `module:factory` and returns an object with `snapshot(since)` and `apply(payload)`.
- Layout edits may change only known part `left`, `top`, 90-degree `rotate`, known wire route points/styles, and the ground bus Y position.

For repositories containing multiple hardware projects, vendor the core once at `simulation/circuit_lab` and keep each project under `simulation/projects/<project-id>`. Start the shared server with the selected project's `--config` path.

Read [references/config-reference.md](references/config-reference.md) when adding a board or control. Assets marked `local-only` must not be redistributed without a fresh license review.

## Physical Boundary

- Generic CircuitLab is limited to explicitly current-limited embedded work at or below 24 V.
- Generated fixture files stay `GENERATED_UNVERIFIED_DO_NOT_FABRICATE` until dimensions, board revision, electrical mapping, and physical contact are independently checked.
- An Arm token authorizes only its exact device fingerprints, hashes, safety limits, plan, and expiry. It never authorizes purchasing, fabrication, mains work, or a different physical run.
