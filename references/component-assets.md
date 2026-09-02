# Component Assets

CircuitLab stores immutable `component-package/v1` revisions below its configured data directory. JSON packages are authoritative; SQLite is a rebuildable search, procurement, and run index.

## Primary scope: chips and directly usable hardware

The primary registry and UI surface the latest exact revision of packaged semiconductors, development boards, single-board computers, sensor modules, and displays. Keep unrelated motors, switches, power supplies, fixtures, raw PCB assemblies, and discrete passives outside the default catalog. Historical imports remain immutable and can be audited with `component_assets.py search --all-history --all-revisions`.

For boards and modules, record the exact board revision or product ID, an official top view when permitted, the official pin table, and explicit visual anchors. If official imagery is local-only or unsuitable for redistribution, create an original CircuitLab SVG from published dimensions and pin tables. Mark it `OFFICIAL_DESIGN_DERIVED_UNVERIFIED`; never trace a photograph or infer pin identity from pixels.

Run `python3 scripts/component_assets.py audit-chips` to identify missing package codes, pin tables, datasheet evidence, footprints, and package appearances before scheduling more online collection.

Do not start from a board photo. For every chip, collect the exact orderable MPN, package code, official package-top or package drawing, pin table, absolute-maximum ratings, datasheet revision, and a footprint from manufacturer material or a pinned KiCad release.

## Repeatable board and sensor workflow

Use `python3 scripts/hardware_pipeline.py run --online` to execute the complete
pipeline. Network access is never implicit: omit `--online` to inspect only the
local evidence cache.

1. Capture bytes only from the official-domain allowlist. Retain the response
   body locally with its final URL, timestamp, content type, HTTP validators,
   byte count, and SHA-256. Captured bytes are local evidence and are not added
   to the redistributable Skill.
2. Normalize exact manufacturer, product ID or revision, dimensions, functions,
   and the official pin table into `hardware-source-spec/v1`.
3. Render an original vector top view with `circuitlab-top-style/v1`. Use common
   board, silkscreen, trace, and touchpoint geometry. Pin colors are semantic:
   power, ground, clock, data, and general signal.
4. Validate that every electrical pin has exactly one named visual anchor, that
   the SVG hash matches the package, and that every evidence URL remains on an
   approved official domain.
5. Install a new immutable component revision and publish the pipeline report to
   the PWA. A capture warning remains visible; it is never silently converted to
   fresh evidence.

The product photo is composition evidence only. Never derive a pin name or
electrical identity from pixel position, and never trace the photograph into a
redistributable asset. Each original view must disclose that it was generated
from the documented pin table and remains physically unverified.

## Acquisition order

1. Search the local registry by exact manufacturer and MPN.
2. Prefer manufacturer datasheets and mechanical drawings.
3. Use a fixed KiCad release for symbols, footprints, and 3D models.
4. Use pinned Wokwi or step.parts content when provenance and redistribution status are explicit.
5. Keep community or reverse-engineered material `CANDIDATE_UNVERIFIED`.

Acquisition requires an exact packaged-chip MPN or exact board/module product and revision. Store source URL, capture time, SHA-256, license status, and transformation details. Chip acquisition remains fail-closed through `install_chip`; board/module imports use the general immutable registry after explicit type validation.

Use `scripts/import_sindri_assets.py` for a read-only migration. CircuitLab copies bytes and records the Sindri directory hash; it never edits Sindri.

Use `scripts/discover_components.py wokwi-search QUERY` for the pinned offline catalog and `step-search QUERY` for online mechanical candidates. Search never installs a fuzzy result. `step-acquire PART_ID --asset-id ID --revision REV --confirm-exact-part` installs only the exact selected record after verifying its published SHA-256; the resulting geometry remains `PHYSICAL_UNVERIFIED` and redistribution licensing remains review-required.

## Official chip-package images

Use `scripts/official_media.py` for manufacturer-hosted MCU, SoC, sensor, and support-IC package images. The pipeline is deliberately three-stage:

1. `discover PAGE_URL --mpn EXACT_MPN` extracts JSON-LD, Open Graph, responsive image sources, and ordinary images only from registered official domains. It ranks top/front product-photo candidates but never selects one automatically.
2. `capture PAGE_URL --mpn EXACT_MPN --candidate ID --confirm-exact-mpn` downloads the original raster bytes, records the final URL, page and image SHA-256, ETag, Last-Modified, dimensions, capture time, and a local-only license-review status in an immutable snapshot.
3. `attach SNAPSHOT --ref ASSET@REV --revision NEW_REV --view package-top --primary --confirm-view` creates a new immutable chip revision. Changing the primary appearance clears all old visual anchors and requires touchpoint recalibration. Attach rejects non-chip assets.

The official-domain registry lives in `references/official-media-providers.json`. Redirects and image URLs outside the selected manufacturer's domains fail closed. Network failure may use an explicitly marked cached page for discovery, but capture always requires a live image response. Official images remain `LOCAL_ONLY_LICENSE_REVIEW_REQUIRED` unless their reuse terms are separately established.

Some official sites intentionally block non-browser HTTP clients. Save the fully rendered official page and image in an ordinary browser, then pass `--html PAGE.html --image-file IMAGE` to the same discovery/capture flow. CircuitLab still verifies the official page/resource domains, exact identity confirmation, file signature, dimensions, and hash, and records `USER_BROWSER_DOWNLOAD` rather than pretending the fetch was automated. If an ordering MPN such as `SC0918` is absent from a page that uses the official product name, pass `--page-identity 'Raspberry Pi Pico W'`; the component MPN remains unchanged and both identities are recorded.

Run `scripts/official_media.py audit` to classify every local component revision as official-image, non-official-image, generated/unattributed, or missing.

Use `scripts/procurement_snapshot.py` only for read-only DigiKey or Mouser data. Credentials remain in the environment. A snapshot is historical after its `staleAfter` time and never authorizes a cart or purchase.
