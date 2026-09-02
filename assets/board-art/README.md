# Generated Board Body Layers

The PNG files stored in each immutable catalog revision are ImageGen redraws used
only as orthographic board-body layers. They were generated from the corresponding
reviewed source image (except the two Sindri concept boards, which use project
pin-map descriptions). Prompts required:

- a true top-down, zero-perspective board-only rendering;
- preservation of the board silhouette, connectors, mounting holes, and major
  component placement;
- no labels, callouts, pin identities, watermarks, cables, or added accessories;
- the shared CircuitLab dark technical PCB treatment.

`scripts/generate_board_topviews.py` supplies all electrical pin identities,
semantic point colors, and normalized anchors from official or project-owned pin
tables. Nothing in these raster layers is trusted as electrical evidence. All
generated bodies and visual alignment remain `PHYSICAL_UNVERIFIED`.
