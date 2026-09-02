# HIL Safety And State

CircuitLab uses `fixture-driver/v1` and `hil-plan/v1`. The fixed job state machine is:

`IDLE → PREPARED → ARMED → RUNNING → PASSED | FAILED | ABORTED`

Preparation binds DUT and fixture fingerprints, wiring lock, asset lock, firmware hash, plan hash, voltage/current limits, and a maximum ten-minute nonce. Arm requires an explicit wiring and safety acknowledgement. Any mismatch or expiry requires a new preparation.

Mock and replay drivers are software-only and may run automatically after Arm. Real serial, flash, power, backup, and restore drivers remain fail-closed until exact hardware Assets, protective circuitry, emergency-stop behavior, and a real backup/restore path have been verified. Generic CircuitLab never supports mains or unknown/high-energy loads.

Reports retain every test result, waveform summary, binding hash, state transition, failure, and report SHA-256. Do not discard failed or aborted runs.

