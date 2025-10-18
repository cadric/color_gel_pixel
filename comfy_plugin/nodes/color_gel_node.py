# SPDX-License-Identifier: MIT
# Copyright (c) 2025

"""
Color Gel nodes — apply color gels from JSON palettes.

Design goals (per CODEX.md):
- No I/O in execution path (run): palettes are preloaded at import.
- Deterministic, typed, small nodes.
- Clear exceptions instead of silent fallbacks.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from typing import TYPE_CHECKING, Any

try:  # Optional at import; required at run-time
    import torch
    import torch.nn.functional as F
except Exception:  # pragma: no cover - allow import without torch for tooling
    torch = None  # type: ignore[assignment]
    F = None  # type: ignore[assignment]

if TYPE_CHECKING:  # Real types for type checkers
    import torch as _torch


# -------- Paths --------
_NODES_DIR = os.path.dirname(__file__)
_PALETTES_DIR = os.path.normpath(os.path.join(_NODES_DIR, "..", "palettes"))
_PALETTES_FIXED_DIR = os.path.normpath(os.path.join(_NODES_DIR, "..", "palettes_fixed"))


# -------- Regexes --------
_HEX_RE = re.compile(r"^#?([0-9A-Fa-f]{6})$")
_RGB_RE = re.compile(r"^\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*$")


# -------- Palette I/O (import time only) --------
def _list_palette_files(dir_path: str) -> list[str]:
    if not os.path.isdir(dir_path):
        raise ValueError(f"Palettes directory not found: {dir_path}")
    files = [f for f in os.listdir(dir_path) if f.lower().endswith(".json")]
    files.sort()
    if not files:
        raise ValueError(f"No palette JSON files found in: {dir_path}")
    return files


def _load_palette_json(path: str) -> tuple[list[str], list[str]]:
    """Load one palette JSON file -> (names, hex_colors).

    Accepts either a dict mapping name->hex/rgb or a list of {'name','hex'| 'rgb'} dicts.
    Raises ValueError on invalid content.
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:  # pragma: no cover - propagate with context
        raise ValueError(f"Failed to load palette: {path}: {e}") from e

    items: list[tuple[str, Any]]
    if isinstance(data, dict):
        items = list(data.items())
    elif isinstance(data, list):
        items = []
        for row in data:
            if not isinstance(row, dict):
                raise ValueError(f"Invalid palette list entry in {path}: {row!r}")
            n = row.get("name") or row.get("label") or row.get("title")
            v = row.get("hex") or row.get("color") or row.get("rgb")
            if not (n and v):
                raise ValueError(f"Missing name/color in palette row: {row!r} in {path}")
            items.append((str(n), v))
    else:
        raise ValueError(f"Unsupported palette format in {path}: {type(data).__name__}")

    names: list[str] = []
    colors: list[str] = []
    for k, v in items:
        if isinstance(v, str):
            colors.append(v.strip())
        elif isinstance(v, (list, tuple)) and len(v) == 3:
            try:
                r, g, b = int(v[0]), int(v[1]), int(v[2])
            except Exception as e:
                raise ValueError(f"Non-integer RGB in {path}: {v!r}") from e
            colors.append(f"#{r:02X}{g:02X}{b:02X}")
        else:
            raise ValueError(f"Unsupported color value in {path}: {v!r}")
        names.append(str(k))
    if not names:
        raise ValueError(f"Empty palette in {path}")
    return names, colors


def _build_palette_cache() -> tuple[dict[str, tuple[list[str], list[str]]], list[str]]:
    cache: dict[str, tuple[list[str], list[str]]] = {}
    order: list[str] = []
    try:
        files = _list_palette_files(_PALETTES_DIR)
    except Exception:
        # Keep node importable; fail at run if/when a palette is actually used
        return cache, order
    for fname in files:
        try:
            base = os.path.splitext(fname)[0]
            path = os.path.join(_PALETTES_DIR, fname)
            names, colors = _load_palette_json(path)
            if names:
                cache[base] = (names, colors)
                order.append(base)
        except Exception:
            # Skip bad palette files; report only when selected
            continue
    return cache, order


_PALETTE_CACHE, _PALETTE_ORDER = _build_palette_cache()


# -------- Fixed palettes (for quantization) --------
def _list_fixed_palette_files(dir_path: str) -> list[str]:
    """List JSON files in the fixed palettes directory.

    Returns an empty list when the directory is missing, not a directory,
    or cannot be read. Only OS-related errors are suppressed to avoid
    hiding unrelated bugs.
    """
    if not os.path.isdir(dir_path):
        return []
    try:
        files = [f for f in os.listdir(dir_path) if f.lower().endswith(".json")]
    except OSError:
        return []
    files.sort()
    return files


def _load_fixed_palette_colors(path: str) -> list[str]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        items: list[str] = []
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, str):
                    items.append(v)
                elif isinstance(v, (list, tuple)) and len(v) == 3:
                    items.append(f"#{int(v[0]):02X}{int(v[1]):02X}{int(v[2]):02X}")
        elif isinstance(data, list):
            for row in data:
                if isinstance(row, dict):
                    v = row.get("hex") or row.get("color") or row.get("rgb")
                    if isinstance(v, str):
                        items.append(v)
                    elif isinstance(v, (list, tuple)) and len(v) == 3:
                        items.append(f"#{int(v[0]):02X}{int(v[1]):02X}{int(v[2]):02X}")
        return [s.strip() for s in items if isinstance(s, str) and s.strip()]
    except Exception:
        return []


def _build_fixed_palette_cache() -> tuple[dict[str, list[str]], list[str]]:
    cache: dict[str, list[str]] = {}
    order: list[str] = []
    files = _list_fixed_palette_files(_PALETTES_FIXED_DIR)
    for fname in files:
        base = os.path.splitext(fname)[0]
        path = os.path.join(_PALETTES_FIXED_DIR, fname)
        cols = _load_fixed_palette_colors(path)
        if cols:
            cache[base] = cols
            order.append(base)
    return cache, order


_FIXED_PALETTE_CACHE, _FIXED_PALETTE_ORDER = _build_fixed_palette_cache()


# -------- Color parsing & blending (pure) --------
def _parse_color(s: str) -> tuple[tuple[float, float, float], str]:
    """Parse hex '#RRGGBB' or 'r,g,b' -> ((r,g,b) in 0..1, '#RRGGBB')."""
    if not isinstance(s, str) or not s.strip():
        raise ValueError("color string is empty")
    s = s.strip()
    m = _HEX_RE.match(s)
    if m:
        h = m.group(1)
        r = int(h[0:2], 16) / 255.0
        g = int(h[2:4], 16) / 255.0
        b = int(h[4:6], 16) / 255.0
        return (r, g, b), f"#{h.upper()}"
    m = _RGB_RE.match(s)
    if m:
        r = max(0, min(255, int(m.group(1))))
        g = max(0, min(255, int(m.group(2))))
        b = max(0, min(255, int(m.group(3))))
        return (r / 255.0, g / 255.0, b / 255.0), f"#{r:02X}{g:02X}{b:02X}"
    raise ValueError(f"Unrecognized color format: {s!r}")


def _ensure_batched(img: _torch.Tensor) -> tuple[_torch.Tensor, bool]:
    if img.dim() == 3:
        return img.unsqueeze(0), True
    return img, False


def _overlay_blend(base: _torch.Tensor, gel: _torch.Tensor) -> _torch.Tensor:
    return torch.where(
        base <= 0.5,
        2.0 * base * gel,
        1.0 - 2.0 * (1.0 - base) * (1.0 - gel),
    )


def _apply_gel(
    image: _torch.Tensor,
    strength: float,
    mode: str,
    r: float,
    g: float,
    b: float,
) -> _torch.Tensor:
    if torch is None:
        raise ImportError("torch is required to run Color Gel nodes")
    if not (0.0 <= float(strength) <= 1.0):
        raise ValueError("strength must be within [0, 1]")
    if image.dim() not in (3, 4):
        raise ValueError("image must be HxWxC (3) or BxHxWxC (4)")

    with torch.inference_mode():
        img, added_batch = _ensure_batched(image)
        _, _, _, C = img.shape
        if C < 3:
            raise ValueError("image must have at least 3 channels (RGB)")

        if C != 3:
            rgb = img[..., :3]
            alpha = img[..., 3:]  # view only; avoid clone to save memory
        else:
            rgb = img
            alpha = None

        gel = torch.tensor([r, g, b], dtype=rgb.dtype, device=rgb.device).view(1, 1, 1, 3)
        s = torch.as_tensor(float(strength), dtype=rgb.dtype, device=rgb.device)

        if mode == "normal":
            tinted = rgb * (1.0 - s) + gel * s
        elif mode == "overlay":
            ov = _overlay_blend(rgb, gel.expand_as(rgb))
            tinted = rgb * (1.0 - s) + ov * s
        elif mode == "multiply":
            tinted = rgb * (gel * s + (1.0 - s))
        elif mode == "screen":
            # Fix: compute screen(rgb, gel) then lerp with strength
            screen = 1.0 - (1.0 - rgb) * (1.0 - gel)
            tinted = rgb * (1.0 - s) + screen * s
        else:
            raise ValueError(f"Unsupported mode: {mode!r}")

        tinted = torch.clamp(tinted, 0.0, 1.0)
        out = torch.cat([tinted, alpha], dim=-1) if alpha is not None else tinted
        if added_batch:
            out = out.squeeze(0)
        return out


def _apply_mosaic(image: _torch.Tensor, cell: int) -> _torch.Tensor:
    """Pixelate image using average blocks of roughly `cell` size.

    Works with HxWxC or BxHxWxC; keeps channels. If cell <= 1, returns input.
    """
    if torch is None:
        raise ImportError("torch is required to run mosaic")
    if F is None:
        raise ImportError("torch.nn.functional is required for mosaic")
    if cell is None or int(cell) <= 1:
        return image
    img, added_batch = _ensure_batched(image)
    b, h, w, c = img.shape
    # Clamp cell to image dimensions to avoid degenerate huge values
    cell = int(cell)
    cell = max(2, min(cell, int(min(h, w))))
    # Convert to NCHW for pooling
    x = img.permute(0, 3, 1, 2)
    # Target grid size
    gh = max(1, (h + cell - 1) // cell)
    gw = max(1, (w + cell - 1) // cell)
    # Average down to grid, then upsample back with nearest
    x_small = F.adaptive_avg_pool2d(x, (gh, gw))
    x_big = F.interpolate(x_small, size=(h, w), mode="nearest")
    out = x_big.permute(0, 2, 3, 1)
    if added_batch:
        out = out.squeeze(0)
    return out


def _slugify_basename(s: str) -> str:
    """Portable, lowercase filename stub from a display name.

    - ASCII normalize (NFKD) and drop accents
    - Replace whitespace with underscores; remove unsafe chars
    - Collapse repeats; strip leading dots; lowercase
    """
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    s = s.strip()
    s = s.replace("/", "_").replace("\\", "_")
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^0-9A-Za-z._-]", "", s)
    s = s.lstrip(".")
    s = re.sub(r"_+", "_", s)
    s = re.sub(r"\.+", ".", s)
    return (s or "image").lower()


def _apply_opacity(image: _torch.Tensor, opacity: float) -> _torch.Tensor:
    """Apply output opacity 0..1.

    If image has no alpha and opacity < 1, attach an alpha channel with that value.
    If image has alpha, multiply by opacity.
    If opacity >= 1, return image unchanged.
    """
    if torch is None:
        raise ImportError("torch is required to run Color Gel nodes")
    if not (0.0 <= float(opacity) <= 1.0):
        raise ValueError("opacity must be within [0, 1]")
    if float(opacity) >= 1.0:
        return image

    with torch.inference_mode():
        img, added_batch = _ensure_batched(image)
        _, _, _, C = img.shape
        if C == 3:
            a = torch.full((img.shape[0], img.shape[1], img.shape[2], 1), float(opacity), dtype=img.dtype, device=img.device)
            out = torch.cat([img, a], dim=-1)
        else:
            # Avoid mutating upstream inputs by cloning before scaling alpha
            out = img.clone()
            out[..., 3:].mul_(float(opacity))
        if added_batch:
            out = out.squeeze(0)
        return out


def _posterize_tensor(image: _torch.Tensor, bits: int) -> _torch.Tensor:
    """Posterize RGB channels to `bits` (1..8) akin to PIL ImageOps.posterize.

    Keeps alpha unchanged. A value of 0 disables posterize. Values outside
    1..8 are invalid and raise ValueError to surface misuse clearly.
    """
    if torch is None:
        raise ImportError("torch is required")
    b = int(bits)
    if b == 0:
        return image
    if b < 1 or b > 8:
        raise ValueError(f"posterize_bits must be in [1, 8], got {bits}")
    with torch.inference_mode():
        img, added_batch = _ensure_batched(image)
        if img.shape[-1] < 3:
            return image
        rgb = img[..., :3]
        alpha = img[..., 3:] if img.shape[-1] > 3 else None
        # Convert to 8-bit, apply bitmask by shifting
        vals = torch.clamp((rgb * 255.0).floor(), 0, 255).to(torch.int32)
        shift = 8 - b
        vals = (vals >> shift) << shift
        rgbp = (vals.to(torch.float32) / 255.0).to(dtype=img.dtype)
        out = torch.cat([rgbp, alpha], dim=-1) if alpha is not None else rgbp
        if added_batch:
            out = out.squeeze(0)
        return out


# -------- Node helpers --------
def _resolve_by_name(palette: str, color_name: str) -> tuple[str, str]:
    """Return (selected_name, selected_hex) for given palette and color name.

    Case-insensitive match on color name; raises ValueError if not found.
    """
    if palette not in _PALETTE_CACHE:
        raise ValueError(f"Unknown palette: {palette!r}")
    names, colors = _PALETTE_CACHE[palette]
    try:
        idx = names.index(color_name)
    except ValueError:
        lowered = [n.lower() for n in names]
        try:
            idx = lowered.index(color_name.lower())
        except ValueError as e:
            raise ValueError(f"Color '{color_name}' not found in palette '{palette}'") from e
    return names[idx], colors[idx]


def _resolve_by_index(palette: str, color_index_1based: int) -> tuple[str, str]:
    """Return (selected_name, selected_hex) for 1-based color index.

    Raises ValueError if index is out of range.
    """
    if palette not in _PALETTE_CACHE:
        raise ValueError(f"Unknown palette: {palette!r}")
    names, colors = _PALETTE_CACHE[palette]
    if not isinstance(color_index_1based, int):
        raise TypeError("color_number must be an integer")
    if color_index_1based < 1 or color_index_1based > len(names):
        raise ValueError(
            f"color_number must be in [1, {len(names)}] for palette '{palette}'"
        )
    idx = color_index_1based - 1
    return names[idx], colors[idx]


# -------- Nodes --------


class ColorGelSelect:
    """Dropdown for palette + numeric index (no long color lists)."""

    _palette_options = list(_PALETTE_ORDER)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "Input image (RGB/RGBA)."}),
                "strength": ("FLOAT", {"default": 0.35, "min": 0.0, "max": 1.0, "step": 0.01, "tooltip": "Blend strength 0..1 between source and gel."}),
                "mode": (["normal", "overlay", "multiply", "screen"], {"default": "overlay", "tooltip": "Blend mode for the gel tint."}),
                "opacity": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01, "tooltip": "Final output opacity 0..1 (adds/scales alpha)."}),
                "palette": (list(cls._palette_options), {"default": cls._palette_options[0], "tooltip": "Palette name from installed palettes."}),
                "color_number": ("INT", {"default": 1, "min": 1, "max": 100, "step": 1, "tooltip": "1-based index in the selected palette (effective range 1..N)."}),
            },
            "optional": {
                # Direct color override (#RRGGBB or r,g,b). If provided, palette/index are ignored.
                "color": ("STRING", {"default": "", "multiline": False, "tooltip": "Direct color override (#RRGGBB or r,g,b)."}),
                # Optional: override palette via link from Color Gel Palette node
                "palette_from_node": ("STRING", {"default": "", "multiline": False, "tooltip": "Override 'palette' when connected (from Color Gel Palette)."}),
                "mosaic_cell": ("INT", {"default": 0, "min": 0, "max": 4096, "step": 1, "tooltip": "Mosaic cell size in pixels (0 disables)."}),
                "quantize_fixed": ("BOOLEAN", {"default": False, "tooltip": "Map colors to a fixed palette (nearest)."}),
                "fixed_palette": (list(_FIXED_PALETTE_ORDER) if _FIXED_PALETTE_ORDER else [""], {"default": (_FIXED_PALETTE_ORDER[0] if _FIXED_PALETTE_ORDER else ""), "tooltip": "Fixed palette from palettes_fixed."}),
                "quantize_dither": (["fs", "none"], {"default": "fs", "tooltip": "Dither type for fixed-quantize (fs/none)."}),
                "posterize_bits": ("INT", {"default": 0, "min": 0, "max": 8, "step": 1, "tooltip": "Posterize RGB to N bits before quantization (0 disables)."}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING", "STRING", "INT")
    RETURN_NAMES = ("image", "selected_name", "selected_hex", "filename_stub", "selected_palette", "selected_index")
    FUNCTION = "run"
    CATEGORY = "Color Gel Pixel/Core"

    def run(
        self,
        image: _torch.Tensor,
        strength: float,
        mode: str,
        palette: str,
        color_number: int,
        color: str = "",
        palette_from_node: str = "",
        opacity: float = 1.0,
        mosaic_cell: int = 0,
        quantize_fixed: bool = False,
        fixed_palette: str = "",
        quantize_dither: str = "fs",
        posterize_bits: int = 0,
    ) -> tuple[_torch.Tensor, str, str, str, str, int]:
        # Validate posterize range: 0 disables; 1..8 valid; otherwise error
        pb = int(posterize_bits)
        if pb < 0 or pb > 8:
            raise ValueError(f"posterize_bits must be in [0, 8], got {posterize_bits}")
        # Direct color override
        if isinstance(color, str) and color.strip():
            (r, g, b), hex_norm = _parse_color(color)
            out = _apply_gel(image, strength, mode, r, g, b)
            if int(mosaic_cell) > 1:
                out = _apply_mosaic(out, int(mosaic_cell))
            out = _apply_opacity(out, opacity)
            if pb > 0:
                out = _posterize_tensor(out, pb)
            if quantize_fixed and fixed_palette and fixed_palette in _FIXED_PALETTE_CACHE:
                use_dither = (str(quantize_dither).lower() != "none")
                out = _quantize_to_fixed_tensor(out, fixed_palette, dither=use_dither, keep_alpha=(out.shape[-1] == 4))
            stub = _slugify_basename(hex_norm)
            return out, "(custom)", hex_norm, stub, "", 0

        chosen_palette = palette_from_node.strip() or palette
        # Helpful error when no palettes are available at all
        if not _PALETTE_CACHE:
            raise ValueError(
                "No palettes installed; either add JSON files under 'comfy_plugin/palettes' or use the 'color' override input."
            )
        sel_name, sel_hex = _resolve_by_index(chosen_palette, int(color_number))
        (r, g, b), hex_norm = _parse_color(sel_hex)
        out = _apply_gel(image, strength, mode, r, g, b)
        if int(mosaic_cell) > 1:
            out = _apply_mosaic(out, int(mosaic_cell))
        out = _apply_opacity(out, opacity)
        if pb > 0:
            out = _posterize_tensor(out, pb)
        if quantize_fixed and fixed_palette and fixed_palette in _FIXED_PALETTE_CACHE:
            use_dither = (str(quantize_dither).lower() != "none")
            out = _quantize_to_fixed_tensor(out, fixed_palette, dither=use_dither, keep_alpha=(out.shape[-1] == 4))
        stub = _slugify_basename(sel_name)
        return out, f"{chosen_palette}/{sel_name}", hex_norm, stub, chosen_palette, int(color_number)



def _register_palette_specific_nodes() -> tuple[dict[str, Any], dict[str, str]]:
    """Create one node per palette file with a small color-name dropdown."""
    # Pruned: return empty mapping to avoid registering per-palette nodes
    return {}, {}


def _register_all_nodes() -> tuple[dict[str, Any], dict[str, str]]:
    mappings: dict[str, Any] = {}
    displays: dict[str, str] = {}

    # Keep only the streamlined select node
    mappings["Color Gel (select)"] = ColorGelSelect
    displays["Color Gel (select)"] = "Color Gel (select)"
    return mappings, displays


NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS = _register_all_nodes()


# -------- Fixed Palette Quantization Node --------
try:
    from PIL import Image
except Exception:
    Image = None  # type: ignore[assignment]


def _tensor_to_pil(img: _torch.Tensor) -> Image.Image:
    if torch is None or Image is None:
        raise ImportError("torch/Pillow required")
    if img.dim() not in (3, 4):
        raise ValueError("image must be HxWxC or BxHxWxC")
    if img.dim() == 4:
        if img.shape[0] != 1:
            raise ValueError("batch > 1 not supported")
        img = img.squeeze(0)
    if img.shape[-1] not in (3, 4):
        raise ValueError("image must have 3 or 4 channels")
    arr = (
        img.clip(0.0, 1.0)
        * 255.0
    ).to(dtype=torch.uint8).cpu().contiguous().numpy()
    mode = "RGBA" if arr.shape[-1] == 4 else "RGB"
    return Image.fromarray(arr, mode=mode)


def _pil_to_tensor(im: Image.Image) -> _torch.Tensor:
    try:
        import numpy as _np
    except Exception as e:
        raise ImportError("NumPy is required for quantization path (_pil_to_tensor)") from e
    arr = _np.array(im, copy=False)
    t = torch.from_numpy(arr).to(dtype=torch.float32) / 255.0
    return t


def _make_pil_palette(colors_hex: list[str]) -> Image.Image:
    # Build a 'P' image with provided palette (max 256 colors)
    pal_img = Image.new("P", (1, 1))
    table: list[int] = []
    for hx in colors_hex[:256]:
        (r, g, b), _ = _parse_color(hx)
        table.extend([int(round(r * 255)), int(round(g * 255)), int(round(b * 255))])
    # pad to 256*3
    while len(table) < 256 * 3:
        table.extend([0, 0, 0])
    pal_img.putpalette(table)
    return pal_img



def _quantize_to_fixed_tensor(image: _torch.Tensor, palette: str, dither: bool, keep_alpha: bool) -> _torch.Tensor:
    """Shared helper: quantize a tensor to a named fixed palette from cache.

    Supports single image or batches (BxHxWxC). Batches are processed per-frame.
    """
    if Image is None:
        raise ImportError("Pillow is required for fixed-palette quantization")
    if palette not in _FIXED_PALETTE_CACHE:
        raise ValueError(f"Unknown fixed palette: {palette}")
    # Preserve original device/dtype
    orig_device = image.device
    orig_dtype = image.dtype
    # Batched case
    if image.dim() == 4 and image.shape[0] > 1:
        frames = []
        for i in range(image.shape[0]):
            frames.append(_quantize_to_fixed_tensor(image[i:i+1], palette, dither, keep_alpha))
        return torch.cat(frames, dim=0).to(device=orig_device, dtype=orig_dtype).contiguous()

    colors = _FIXED_PALETTE_CACHE[palette]
    pal_img = _make_pil_palette(colors)
    pil = _tensor_to_pil(image)
    has_alpha = (pil.mode == "RGBA") and keep_alpha
    base = pil.convert("RGB")
    dither_val: Any = getattr(Image, "FLOYDSTEINBERG", 1) if dither else getattr(Image, "NONE", 0)
    q = base.quantize(palette=pal_img, dither=dither_val)
    q_rgb = q.convert("RGB")
    if has_alpha:
        a = pil.split()[3]
        out = Image.merge("RGBA", (*q_rgb.split(), a))
    else:
        out = q_rgb
    t = _pil_to_tensor(out).to(device=orig_device, dtype=orig_dtype).contiguous()
    return t
