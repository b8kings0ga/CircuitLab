# Interactive board views

CircuitLab separates appearance evidence from electrical geometry:

- Official product photos show what a board revision looks like.
- Manufacturer KiCad, DXF, footprint, and pinout files provide explicit geometry.
- `board-view-spec/v1` records only reviewed dimensions and pin coordinates.
- `generate_board_view.py` deterministically creates an original SVG, `interactive-board/v1` geometry, and an immutable `component-package/v1` revision.

Never infer an electrical pin identity from image pixels. A photo-only acquisition remains `VISUAL_SUGGESTION`; a design-document-derived board remains `OFFICIAL_DESIGN_DERIVED_UNVERIFIED` until the exact physical revision and pin mapping are checked.

Generate and preview the included XIAO ESP32S3 view:

```bash
python3 scripts/generate_board_view.py \
  assets/board-specs/seeed-xiao-esp32s3.json \
  --output /tmp/circuitlab-xiao
```

Install it into the local immutable registry only after reviewing the exact board revision:

```bash
python3 scripts/generate_board_view.py \
  assets/board-specs/seeed-xiao-esp32s3.json \
  --output /tmp/circuitlab-xiao \
  --install
```

The generated artwork is a CircuitLab-authored technical rendering. Manufacturer photos and design downloads are retained as evidence subject to their own licenses; they are not embedded into the generated SVG.
