SPDX-License-Identifier: MIT

# Changelog

All notable changes to Color Gel Pixel will be documented in this file.

## 0.3.2 — Release candidate for registry

* Rename package for registry: `Color_Gel_Pixel` (spec‑compliant; no "ComfyUI" in name).
* Add registry metadata: `[project.urls]`, `[tool.comfy]` (PublisherId/Icon/Banner/requires‑comfyui).
* Replace palette set with 10 generic JSON palettes (neutral/blue/sky/red/green/amber/purple/orange/teal/indigo).
* Add curated fixed palettes: DawnBringer DB16/DB32, AAP‑64, PICO‑8, C64 VIC‑II (Pepto), Web‑safe 216.
* Remove experimental nodes from this release: Reload Palettes, Preset: Pixel 64 (kept on a separate branch).
* Update docs: README (icon/screenshot, example workflow), USAGE (icon, example workflow), sample workflow `docs/workflow_color_gel_pixel.json`.

## 0.3.1 — Sanitized bundle

* Strict layout with `comfy_plugin` package; import side‑effects only for node registration.
* Nodes kept: Color Gel (select), Save, Preview, Batch (N), Batch Flatten, Names (N), Palette.
* Prune legacy nodes and helpers from menus.

## 0.3.0 — Initial refactor

* Deterministic, typed nodes; blend math fixes; safer I/O and filenames; basic docs.

## 0.2.5 — Transitional development snapshot

* Internal rename of repository and prep for refactor branch (`dev/refactor‑typed‑nodes`).
* Introduced modular folder layout (`nodes/`, `palettes/`, `utils/`, `tests/`).
* Started migration from procedural node definitions to class‑based nodes with type hints.
* Added experimental `Reload Palettes` node (later removed).
* Introduced JSON palette import/export helpers.
* Began cleaning up image quantization logic (split palette lookup and dither passes).
* Updated `Color Gel (select)` node to support optional external palette source.
* Added internal palette cache to avoid repeated disk I/O.
* Refactored batch handling — unified naming for batch and single image processing.
* Added test scaffolding and mock palette data for CI.
* Early documentation drafts and project metadata added (`pyproject.toml`, `README_stub.md`).

## 0.2.4

* Added preliminary support for custom JSON palette import/export.
* Improved error handling when saving batches with missing names.
* Palette caching optimization: load once per session.

## 0.2.3

* Introduced internal helpers for color math (gamma correction, clipping, alpha blending).
* Adjusted Save node to preserve metadata options.
* Experimental: introduced hidden debug flag for profiling quantization.

## 0.2.2

* Batch (N): stabilized multi‑image output and unified filename handling.
* Color Gel (select): fixed inconsistent posterize results when dither disabled.
* Save: better PNG optimization and overwrite logic.

## 0.2.1

* Palette node cleanup and preparation for modular refactor.
* Removed unused attributes and legacy palette data.
* Updated example workflows.

## 0.2.0 (BREAKING)

* Removed deprecated `dither` boolean from Color Gel (select). Use `quantize_dither` (`fs`/`none`).
* Updated sample workflows to match new Select inputs.

## 0.1.5

* Phase 3: Added utility node — Batch Flatten.

## 0.1.4

* Phase 2: Save — palette lock across batch, palette method (`mediancut`/`fastoctree`/`maxcoverage`), dither (`none`/`fs`), posterize pre‑quantization.
* Phase 2: Select — posterize and dither choice for fixed‑palette quantization.

## 0.1.3

* Phase 1: added `filename_stub`, `selected_palette`, `selected_index` outputs to Color Gel (select).
* Names (N): new `prefix`/`suffix` inputs; improved packing.
* Save: new `overwrite`, `optimize_png`, `drop_metadata` toggles; extra `files_json` output.
* Preview: input `max_previews` to cap UI load.

## 0.1.2

* Housekeeping: remove palette‑specific nodes, "Color Gel (any)", Batch (2), Batch Slice, standalone fixed‑quantize node.
* Keep features inside "Color Gel (select)": mosaic and optional fixed‑palette quantization.
* Save now supports batches and per‑image names via "Color Gel Names (N)".

## 0.1.1

* Add `opacity` to all nodes (any/select/palette‑specific)
* Add tooltips for all inputs
* Preload palettes at import (no I/O during run)
* Reduce GPU memory by avoiding clones and using inference_mode
* Remove unused `palette_str` from select node
