# CircuitLab optimization rounds 01–10

These rounds harden the software-only CircuitLab core without changing its
physical safety boundary. A passing mock or replay run remains
`PHYSICAL_UNVERIFIED`, and generated fixture output remains
`GENERATED_UNVERIFIED_DO_NOT_FABRICATE`.

| Round | Reproduced problem | Implemented change | Targeted evidence |
|---|---|---|---|
| 1 | HIL wiring, asset, and firmware locks accepted empty or arbitrary text. | Require and normalize three 64-character SHA-256 digests during prepare. | Invalid digest rejection and uppercase normalization test. |
| 2 | Duplicate test IDs, unknown failure policies, and inverted thresholds made reports ambiguous. | Validate unique IDs, `stop`/`continue`, finite bounds, and minimum ≤ maximum. | Three malformed-plan rejection cases. |
| 3 | Arm TTL values were truncated or silently capped. | Require an integer TTL from 1 through 600 seconds. | Boundary/type rejection plus exact expiry test. |
| 4 | An Abort racing a running mock test could be overwritten by PASSED. | Re-read state before finalization and preserve ABORTED as terminal with partial evidence. | Deterministic threaded Abort-during-run test. |
| 5 | Invalid fixture revision/current values and unsafe net text could reach manufacturing exports. | Validate positive revision/current, finite numbers, array fields, and export-safe strings. | Numeric and KiCad-text injection rejection tests. |
| 6 | Multiple probes on one logical net received different KiCad net IDs. | Build one stable net table and reuse each logical net ID across pads. | Shared-GND two-probe board assertion. |
| 7 | A failed fixture write left a partial immutable revision directory. | Generate in a sibling staging directory and atomically publish only after completion. | Injected write failure leaves no revision or staging residue. |
| 8 | Lexical ordering selected `1.9.0` over `1.10.0`. | Use numeric-aware revision tokens while retaining suffix support. | Out-of-order installation selects `1.10.0`. |
| 9 | A component media failure could leave a partial package revision. | Prevalidate files, stage the whole package, atomically publish, and roll back on index failure. | Invalid and reserved-file cases leave no revision directory. |
| 10 | Local JSON POST bodies had no size boundary. | Reject bodies above 1 MiB with HTTP 413 before reading the payload. | Raw HTTP oversized-header E2E check. |

## Full acceptance commands

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/verify_e2e_scenarios.py
python3 scripts/verify_api_e2e.py
python3 scripts/verify_platform.py
python3 scripts/hardware_pipeline.py validate
python3 scripts/catalog_coverage.py --require-target
```
