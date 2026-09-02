# CircuitLab

CircuitLab is a portable, local-first circuit-development workspace for interactive wiring, immutable component assets, visual and pogo touchpoints, fixture packages, software HIL, and auditable reports.

It is both a standalone application template and a Codex Skill. The repository has no runtime dependency on Rune or Sindri. Rune can consume the shared core through its own adapter, and Sindri assets can be imported read-only.

## What is included

- Single-browser PWA: Projects, Components, Workbench, Touchpoints, Fixture, HIL, and Reports.
- `component-package/v1`, `fixture-package/v1`, `hil-plan/v1`, and `fixture-driver/v1` contracts.
- Immutable JSON component registry with rebuildable SQLite indexes.
- Exact-part discovery for pinned Wokwi data and checksum-verified step.parts models.
- Fail-closed official manufacturer image discovery, immutable capture, and human-confirmed attachment.
- DigiKey and Mouser read-only procurement snapshots.
- Fixture map, CSV, DXF, KiCad PCB, Gerber, drill, BOM, and assembly outputs.
- Mock and replay HIL with expiring, hash-bound Arm sessions.
- A generic redistributable starter board; product-specific boards remain in their project adapters.

## Quick start

```bash
python3 scripts/init_lab.py ~/CircuitLabProjects/my-lab
python3 scripts/validate_instance.py ~/CircuitLabProjects/my-lab
python3 scripts/start_lab.py ~/CircuitLabProjects/my-lab --port 8766
```

Open <http://127.0.0.1:8766>.

Run the complete software-only acceptance loop:

```bash
python3 scripts/verify_platform.py
python3 -m unittest discover -s tests -p 'test_*.py'
```

## Install as a Codex Skill

Clone or download this repository into `$CODEX_HOME/skills/circuitlab`, or install the GitHub repository with Codex's Skill installer. Invoke it as `$circuitlab`.

## Safety

CircuitLab's generic boundary is current-limited embedded work at or below 24 V. Real serial, flashing, power, restore, purchasing, and fabrication are fail-closed until separately verified and authorized. Generated manufacturing files are always marked `GENERATED_UNVERIFIED_DO_NOT_FABRICATE`; software-only evidence is marked `PHYSICAL_UNVERIFIED`.

## Licensing

CircuitLab code and original starter assets are MIT licensed. The vendored Wokwi Elements runtime retains its upstream MIT license. Product-specific Wokwi board artwork is intentionally not included because its redistribution status requires separate review. See `THIRD_PARTY_NOTICES.md`.

![CircuitLab standalone workbench](docs/circuitlab-standalone.png)
