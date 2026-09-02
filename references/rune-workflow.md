# Rune Instance Workflow

Repository: the downstream Rune checkout selected by the user. In the commands below, set `RUNE_REPO` to that absolute checkout path.

1. Inspect `http://127.0.0.1:8766/healthz`, `/api/lab-config`, `/api/diagram`, `/api/state`, and `~/Library/Logs/Rune/circuit-lab.*.log`.
2. Put reusable changes in this skill's `assets/template/core`. The vendored copy lives at `simulation/circuit_lab`. Put Rune behavior only in `simulation/projects/rune/circuit-lab.json`, `diagram.json`, `rune_adapter.py`, or `rune_sim.py`.
3. Run `python scripts/sync_instance.py --target "$RUNE_REPO" --apply`.
4. Run `python scripts/validate_instance.py "$RUNE_REPO/simulation/projects/rune"`, discover unit tests from `simulation/projects/rune`, and run its Playwright verifier at DPR 1 and 2.
5. Run `deploy/user/install.sh`.
6. Confirm `8766/healthz`, `launchctl print gui/$(id -u)/com.rune.user.circuit-lab`, installed core checksums, and the saved version 2 layout.

The installer preserves `~/Library/Application Support/Rune/circuit-layout.json`. Resetting layout deletes only that file; it must not reset Rune simulator or BLE data.
