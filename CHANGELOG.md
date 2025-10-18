SPDX-License-Identifier: MIT

# Changelog

All notable changes to Color Gel Pixel will be documented in this file.

## 0.3.2 — Release candidate for registry
- Rename package for registry: `Color_Gel_Pixel` (spec‑compliant; no "ComfyUI" in name).
- Add registry metadata: `[project.urls]`, `[tool.comfy]` (PublisherId/Icon/Banner/requires‑comfyui).
- Replace palette set with 10 generic JSON palettes (neutral/blue/sky/red/green/amber/purple/orange/teal/indigo).
- Add curated fixed palettes: DawnBringer DB16/DB32, AAP‑64, PICO‑8, C64 VIC‑II (Pepto), Web‑safe 216.
- Remove experimental nodes from this release: Reload Palettes, Preset: Pixel 64 (kept on a separate branch).
- Update docs: README (icon/screenshot, example workflow), USAGE (icon, example workflow), sample workflow `docs/workflow_color_gel_pixel.json`.

## 0.3.1 — Sanitized bundle
- Strict layout with `comfy_plugin` package; import side‑effects only for node registration.
- Nodes kept: Color Gel (select), Save, Preview, Batch (N), Batch Flatten, Names (N), Palette.
- Prune legacy nodes and helpers from menus.

## 0.3.0 — Initial refactor
- Deterministic, typed nodes; blend math fixes; safer I/O and filenames; basic docs.

