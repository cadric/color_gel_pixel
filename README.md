SPDX-License-Identifier: MIT

# Color Gel Pixel

Minimal, typed ComfyUI nodes to apply color gels from JSON palettes.
Package (registry/manager) name: `Color_Gel_Pixel`

Highlights:
- Preloaded palettes (no I/O during node execution)
- Streamlined nodes: "Color Gel (select)", "Color Gel Save", "Color Gel Preview"
- Batch support: combine up to 10 images via "Color Gel Batch (N)" and name files with "Color Gel Names (N)"
- Utilities: central palette switch via "Color Gel Palette"; batch concat via "Color Gel Batch Flatten".

Usage:
- Place this folder under `ComfyUI/custom_nodes/`.
- In your graph, use:
  - `Color Gel (select)`: choose `palette` and `color_number` (1-based). Optional `opacity` [0..1] to add/scale alpha for transparency.
  - `Color Gel Palette`: pick a palette once and wire its `palette` → `Color Gel (select).palette_from_node` for global switching.
  - `Color Gel Save`: save to PNG/WebP with options: resize, opacity flatten, background color, palette reduction, quality/compression.
  - `Color Gel Preview`: connect any IMAGE to show a dedicated preview window (OUTPUT node).

Menu categories:
- Nodes appear under `Color Gel Pixel/Core`, `Color Gel Pixel/Batch`, and `Color Gel Pixel/Utils`.

Detailed docs for every node and option: see docs/USAGE.md

Palettes:
- JSON files under `comfy_plugin/palettes/` (name becomes palette id)
- Supports `{ "Name": "#RRGGBB", ... }` or list of objects with `name` + `hex`/`rgb`.

License: MIT

## Changelog

- 0.2.0 (BREAKING)
  - Removed deprecated `dither` boolean from Color Gel (select). Use `quantize_dither` (`fs`/`none`).
  - Updated sample workflows to match new Select inputs.
- 0.1.5
  - Phase 3: Added utility node — Batch Flatten.
- 0.1.4
  - Phase 2: Save — palette lock across batch, palette method (`mediancut`/`fastoctree`/`maxcoverage`), dither (`none`/`fs`), posterize pre‑quantization.
  - Phase 2: Select — posterize and dither choice for fixed‑palette quantization.
- 0.1.3
  - Phase 1: added `filename_stub`, `selected_palette`, `selected_index` outputs to Color Gel (select).
  - Names (N): new `prefix`/`suffix` inputs; improved packing.
  - Save: new `overwrite`, `optimize_png`, `drop_metadata` toggles; extra `files_json` output.
  - Preview: input `max_previews` to cap UI load.
- 0.1.2
  - Housekeeping: remove palette-specific nodes, "Color Gel (any)", Batch (2), Batch Slice, standalone fixed-quantize node.
  - Keep features inside "Color Gel (select)": mosaic and optional fixed-palette quantization.
  - Save now supports batches and per-image names via "Color Gel Names (N)".
- 0.1.1
  - Add `opacity` to all nodes (any/select/palette-specific)
  - Add tooltips for all inputs
  - Preload palettes at import (no I/O during run)
  - Reduce GPU memory by avoiding clones and using inference_mode
  - Remove unused `palette_str` from select node
