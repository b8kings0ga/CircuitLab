# Managed Wokwi assets

- `elements/` contains the MIT-licensed `@wokwi/elements` browser bundle and a runtime-generated component/pin catalog.
- Public CircuitLab distributions do not contain Wokwi board artwork. Locally imported `boards/` content requires a separate license review.
- `sources.json` pins both upstream Git revisions.
- `manifest.json` contains SHA-256 checksums for every imported file.

The upstream `wokwi-boards` repository has no root license file. Treat all board assets as local-only and review licensing before redistribution.
