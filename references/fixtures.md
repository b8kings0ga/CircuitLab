# Touchpoints And Fixtures

Keep four identities explicit for every test point: electrical pin, visual anchor, PCB pad, and logical HIL net. A fixture package is rejected when any identity is missing.

- Derive visual anchors from verified footprint pads or board geometry when possible.
- Image-only coordinates require human calibration against the locked appearance SHA-256.
- Visual calibration never upgrades electrical confidence.
- Validate unique point IDs, finite coordinates, minimum pogo spacing, keepouts, locating holes, net continuity, and the 24 V maximum.
- Generated DXF, KiCad PCB, Gerber, drill, BOM, CSV, and assembly files remain `GENERATED_UNVERIFIED_DO_NOT_FABRICATE` until independent physical review.

