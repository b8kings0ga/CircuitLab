# Component Assets

CircuitLab stores immutable `component-package/v1` revisions below its configured data directory. JSON packages are authoritative; SQLite is a rebuildable search, procurement, and run index.

## Default scope: packaged chips only

The primary registry and UI surface only the latest revision of packaged semiconductors: MCU/SoC, sensor IC, and supporting analog, interface, driver, logic, memory, and power-management ICs. Development boards, modules, displays, motors, switches, power supplies, PCB assemblies, and discrete passives stay outside the default scope. Historical imports remain immutable and can be audited with `component_assets.py search --all-history --all-revisions`, but ordinary acquisition rejects them.

Run `python3 scripts/component_assets.py audit-chips` to identify missing package codes, pin tables, datasheet evidence, footprints, and package appearances before scheduling more online collection.

Do not start from a board photo. For every chip, collect the exact orderable MPN, package code, official package-top or package drawing, pin table, absolute-maximum ratings, datasheet revision, and a footprint from manufacturer material or a pinned KiCad release.

## Acquisition order

1. Search the local registry by exact manufacturer and MPN.
2. Prefer manufacturer datasheets and mechanical drawings.
3. Use a fixed KiCad release for symbols, footprints, and 3D models.
4. Use pinned Wokwi or step.parts content when provenance and redistribution status are explicit.
5. Keep community or reverse-engineered material `CANDIDATE_UNVERIFIED`.

Acquisition requires an exact packaged-chip MPN. Store source URL, capture time, SHA-256, license status, and transformation details. Board, module, and assembled-product candidates are rejected by the normal acquire path.

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
