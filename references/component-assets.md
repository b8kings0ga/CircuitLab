# Component Assets

CircuitLab stores immutable `component-package/v1` revisions below its configured data directory. JSON packages are authoritative; SQLite is a rebuildable search, procurement, and run index.

## Acquisition order

1. Search the local registry by exact manufacturer and MPN.
2. Prefer manufacturer datasheets and mechanical drawings.
3. Use a fixed KiCad release for symbols, footprints, and 3D models.
4. Use pinned Wokwi or step.parts content when provenance and redistribution status are explicit.
5. Keep community or reverse-engineered material `CANDIDATE_UNVERIFIED`.

Acquisition requires the exact physical level: bare IC, radio module, development board, or assembled product. Never substitute a bare-chip asset for a board. Store source URL, capture time, SHA-256, license status, and transformation details.

Use `scripts/import_sindri_assets.py` for a read-only migration. CircuitLab copies bytes and records the Sindri directory hash; it never edits Sindri.

Use `scripts/discover_components.py wokwi-search QUERY` for the pinned offline catalog and `step-search QUERY` for online mechanical candidates. Search never installs a fuzzy result. `step-acquire PART_ID --asset-id ID --revision REV --confirm-exact-part` installs only the exact selected record after verifying its published SHA-256; the resulting geometry remains `PHYSICAL_UNVERIFIED` and redistribution licensing remains review-required.

Use `scripts/procurement_snapshot.py` only for read-only DigiKey or Mouser data. Credentials remain in the environment. A snapshot is historical after its `staleAfter` time and never authorizes a cart or purchase.
