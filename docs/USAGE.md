SPDX-License-Identifier: MIT

# Color Gel Nodes — Usage Guide

![Color Gel Pixel icon](../icon.png)

This plugin provides lightweight, deterministic ComfyUI nodes for applying color gels, previewing, and saving assets with pixel‑friendly options.

- Nodes included
  - Color Gel (select)
  - Color Gel Save
  - Color Gel Preview
  - Color Gel Batch (N)
  - Color Gel Names (N)
- Color Gel Batch Flatten
- Color Gel Palette

- Palette location: `comfy_plugin/palettes/` (JSON). Changes require a Reload Custom Nodes.

Example workflow
- See `docs/workflow_color_gel_pixel.json` in the repo for a sample graph wiring Select → Batch (N) → Save → Preview, with Names (N) for filenames.

## Color Gel (select)
- Purpose: Tint an image using a selected palette and numeric color index.
- Inputs
  - image (IMAGE): Input RGB/RGBA image.
  - strength (FLOAT 0..1): Blend amount between source and gel.
  - mode (CHOICE): Blend mode — `normal`, `overlay`, `multiply`, `screen`.
  - opacity (FLOAT 0..1): Output opacity. Adds alpha if missing; scales existing alpha.
  - palette (CHOICE): Palette base name (from `comfy_plugin/palettes/*.json`).
  - palette_from_node (STRING, optional): Overrides `palette` when connected from Color Gel Palette.
  - color_number (INT ≥1): 1‑based index of color within the palette.
  - color (STRING, optional): Direct color override `#RRGGBB` or `r,g,b`.
  - mosaic_cell (INT, optional): Pixelate by block size (0 disables).
  - quantize_fixed (BOOLEAN, optional): Map colors to a fixed palette after gel/opacity.
  - fixed_palette (CHOICE, optional): Palette from `palettes_fixed/` used when quantize_fixed is on.
  - quantize_dither (CHOICE, optional): `fs` or `none` for fixed‑palette quantization.
  - posterize_bits (INT 0..8, optional): Posterize RGB before any quantization (0 disables).
- Outputs
  - image (IMAGE): Tinted image (RGBA if opacity < 1 or input had alpha).
  - selected_name (STRING): Chosen color name.
  - selected_hex (STRING): Normalized `#RRGGBB`.
  - filename_stub (STRING): Portable, lowercase slug from `selected_name`.
  - selected_palette (STRING): Palette id (base filename of the palette JSON).
  - selected_index (INT): 1-based index within the palette.
- Tips
  - To switch palettes across many nodes at once, keep them on the same dropdown selection and duplicate the node.

## Removed nodes
- Color Gel (any) — replaced by the flexible options in “select”.
- Color Gel (<palette>) — noisy in menus; select covers all palettes.

## Color Gel Save
- Purpose: Save images to PNG/WebP with pixel‑friendly downscale and finishing options.
- Inputs (required)
  - image (IMAGE): RGB/RGBA. Batch > 1 is not supported.
  - filename (STRING): Base name; extension is chosen by `save_as`. Unsafe characters are sanitized.
  - save_as (CHOICE): `webp` or `png`.
  - lossless (BOOLEAN): WebP only; PNG is always lossless.
  - compression (INT 1–100):
    - WebP lossy: quality. Higher → better quality/larger file.
    - WebP lossless: effort/size tradeoff.
    - PNG: mapped to compress_level 0–9 (0 fastest, 9 smallest).
  - reduce_palette (BOOLEAN): Quantize colors to a limited set (lossy).
  - reduce_palette_max_colors (INT 1–256): Max colors after quantization.
  - save_opacity (BOOLEAN): Keep alpha if present. If False, flatten onto a background color.
  - flatten_bg_color (STRING): Background when `save_opacity` is False. Hex `#RRGGBB` or `r,g,b`.
  - resize_w (INT ≥0): Target width; 0 keeps original. If only one dimension is set, the other keeps aspect.
  - resize_h (INT ≥0): Target height; 0 keeps original.
- Inputs (optional)
  - resample (CHOICE): `nearest`, `box`, `bilinear`, `bicubic`, `lanczos`, `pixel`.
    - `pixel`: block‑averaging when downscaling by exact divisors (e.g., 1024→64), else area (BOX); NEAREST when upscaling.
    - `nearest`: crisp but can alias for non‑integer ratios.
    - `box`: area average; softer than nearest, good general downscale.
    - `bilinear`/`bicubic`: smooth; can blur fine pixel edges.
    - `lanczos`: sharp with slight ringing; good general purpose.
  - sharpen (BOOLEAN): Apply Unsharp Mask after resize.
  - sharpen_amount (FLOAT 0..5): Strength (mapped to 0–500%).
  - sharpen_radius (FLOAT 0..10): Edge width in pixels; 0.5–1.0 keeps pixels tight.
  - sharpen_threshold (INT 0..255): Edge sensitivity; higher avoids sharpening flat areas.
  - overwrite (BOOLEAN): If true, overwrite existing files instead of auto-suffixing.
  - optimize_png (BOOLEAN): If true, run PNG optimizer (slower but smaller files).
  - drop_metadata (BOOLEAN): Attempt to strip metadata (EXIF/ICC) where possible.
  - reduce_palette_dither (CHOICE): `none` or `fs` (Floyd–Steinberg) for palette reduction.
  - reduce_palette_method (CHOICE): `mediancut` (default), `fastoctree`, or `maxcoverage`.
  - posterize_bits (INT 0..8): Posterize RGB before palette reduction.
  - palette_lock_across_batch (BOOLEAN): Derive a palette from the first image and reuse for the entire batch for consistent tiles.
- Outputs
  - image (IMAGE): Preview of the exact image saved (RGB/RGBA).
  - file (STRING): Absolute path to the last (or only) saved file.
  - files_json (STRING): JSON array of all written paths (batch or single).
- Environment
  - COMFYUI_OUTPUT_DIR: override save location (default: ComfyUI/output).
- Recommended presets
  - Modern pixel look for 1024→64:
    - resample: `pixel`
    - sharpen: on, amount ≈1.5, radius 0.5–1.0, threshold 0–4
    - reduce_palette: on, max_colors: 32; method: `mediancut`; dither: `none` or `fs` per taste
    - posterize_bits: 5–6 for subtle banding control
    - palette_lock_across_batch: on for tilesets/animations
    - save_as: png (or webp with lossless)

## Color Gel Preview
- Purpose: Dedicated preview node that shows the image and passes it through.
- Inputs
  - image (IMAGE): Any RGB/RGBA tensor.
  - title (STRING, optional): Label shown with the preview.
  - max_previews (INT, optional): Limit number of shown previews when input is a batch.
- Outputs
  - image (IMAGE): Pass‑through output.
- Implementation details
  - Writes PNGs to ComfyUI’s temp folder, then returns UI metadata so the preview appears.
  - COMFYUI_TEMP_DIR can override the temp location.

## Color Gel Batch (N)
- Purpose: Combine multiple images into a batch so you can save them with identical settings using a single Color Gel Save.
- Inputs
  - Batch (2): image_a, image_b
  - Batch (N): image_1 (required), image_2..image_10 (optional)
- Rules
  - All images must have the same width/height.
  - RGB/RGBA are auto‑matched (RGB gets alpha=1 if any input has alpha).
  - Dtype/device are unified to the first image.
- Output
  - images (IMAGE): a batch tensor BxHxWxC
- Saving
  - Color Gel Save detects a batch and writes multiple files: base_timestamp_0001.ext, base_timestamp_0002.ext, ...

## Removed utility
- Color Gel Batch Slice — normal Preview or “select”‑stage previews are sufficient for most workflows.

## Color Gel Names (N)
- Purpose: Pack up to 10 names (strings) into a newline‑separated list for Color Gel Save.
- Workflow for named files:
  - Connect each `selected_name` (or your own string) to `Color Gel Names (N)`.
  - Connect its `names_packed` → `Color Gel Save.names_packed` and set `use_names_for_filenames=True`.
  - When saving a batch, files will be named directly from those names (after sanitization): `<name>.png`/`.webp`.

## Fixed palettes
- For fixed‑palette quantization, use the options inside Color Gel (select): `quantize_fixed`, `fixed_palette`, `dither`.

## Palettes (JSON)
- Location: `comfy_plugin/palettes/`
- Formats supported
  - Dict of name → hex/rgb: `{ "Color 1": "#AABBCC", ... }`
  - List of objects: `[{"name":"Color 1","hex":"#AABBCC"}, ...]`
  - Optional `rgb`: `[r,g,b]` allowed and normalized to hex.
- Loading: Palettes are preloaded at import (Reload Custom Nodes to pick up changes).

## Notes & Limitations
- Opacity < 1 adds or scales alpha and may increase memory usage (RGB→RGBA).
- Save node: supports batches; filenames indexed or taken from `names_packed` when enabled.
- Quantization is lossy; “lossless” only refers to the file format.
- Preview requires Pillow.
## Color Gel Batch Flatten
- Purpose: Concatenate up to 10 IMAGE batches along the batch dimension.
- Inputs: images_1..images_10 (IMAGE) — any BxHxWxC; unify to RGBA; H and W must match.
- Output: images (IMAGE): concatenated batch (B_total x H x W x 4).

## Color Gel Palette
- Purpose: Centralize palette choice across many selects.
- Inputs
  - palette (CHOICE): Palette id from `comfy_plugin/palettes/` (dropdown).
- Outputs
  - palette (STRING): Selected palette id; connect to `Color Gel (select).palette_from_node`.
- Notes
  - If you add/remove palettes, use “Reload Custom Nodes” to update dropdowns.
