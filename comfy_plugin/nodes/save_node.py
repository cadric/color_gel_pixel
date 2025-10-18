# SPDX-License-Identifier: MIT
"""
ColorGelSave — compact image saver for Color Gel workflows.

Features:
- Optional resize (width/height; keep aspect if one is zero).
- Optional opacity handling (flatten alpha or keep alpha).
- Optional palette reduction (Pillow quantize) with max colors.
- Formats: PNG and WebP (WebP supports lossy/lossless + quality).

Notes:
- This node performs filesystem I/O by design (saves an image). That is the
  one intentional exception to the "no I/O in run" rule for this plugin.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, cast

try:  # Optional at import; required at run
    import torch
except Exception:  # pragma: no cover
    torch = None  # type: ignore[assignment]

try:  # Optional at import; required at run
    from PIL import Image, ImageFilter, ImageOps
except Exception:  # pragma: no cover
    Image = None  # type: ignore[assignment]
    ImageFilter = None  # type: ignore[assignment]
    ImageOps = None  # type: ignore[assignment]

# Reuse color parser from color_gel_node (hex or r,g,b)
try:
    from .color_gel_node import _parse_color as _parse_hex_or_rgb
except Exception:  # pragma: no cover
    _parse_hex_or_rgb = None  # type: ignore

_SAFE_BASENAME_RE = re.compile(r"[^0-9A-Za-z._-]+")


def _sanitize_basename(name: str) -> str:
    name = name.strip()
    if not name:
        return "image"
    # remove path separators
    name = name.replace("\\", "_").replace("/", "_")
    name = _SAFE_BASENAME_RE.sub("_", name)
    return name or "image"


def _find_output_dir() -> str:
    # 1) Environment override for tests or custom setups
    env = os.environ.get("COMFYUI_OUTPUT_DIR")
    if env:
        os.makedirs(env, exist_ok=True)
        return env

    # 2) Try to locate ComfyUI/output by walking up
    here = os.path.abspath(os.path.dirname(__file__))
    cur = here
    for _ in range(8):
        parent = os.path.dirname(cur)
        output_path = os.path.join(cur, "output")
        if os.path.isdir(output_path):
            return output_path
        # if folder itself is ComfyUI
        if os.path.basename(cur).lower() == "comfyui" and os.path.isdir(os.path.join(cur, "output")):
            return os.path.join(cur, "output")
        if parent == cur:
            break
        cur = parent

    # 3) Fallback local output next to this plugin
    fallback = os.path.abspath(os.path.join(here, "..", "..", "..", "output"))
    os.makedirs(fallback, exist_ok=True)
    return fallback


def _to_pil(image: torch.Tensor) -> Image.Image:
    if torch is None or Image is None:
        raise ImportError("torch and Pillow are required to run ColorGelSave")
    if image.dim() not in (3, 4):
        raise ValueError("image must be HxWxC or BxHxWxC")
    if image.dim() == 4:
        if image.shape[0] != 1:
            raise ValueError("_to_pil expects a single image; got a batch")
        image = image.squeeze(0)
    if image.shape[-1] not in (3, 4):
        raise ValueError("image must have 3 or 4 channels")
    img = (image.clip(0.0, 1.0) * 255.0).to(dtype=torch.uint8).cpu().contiguous()
    mode = "RGBA" if image.shape[-1] == 4 else "RGB"
    return Image.fromarray(img.numpy(), mode=mode)


def _to_pil_list(image: torch.Tensor) -> list[Image.Image]:
    """Split IMAGE tensor into a list of PIL images (handles batch or single)."""
    if image.dim() == 3:
        return [_to_pil(image)]
    if image.dim() == 4:
        return [_to_pil(image[i:i+1]) for i in range(image.shape[0])]
    raise ValueError("image must be HxWxC or BxHxWxC")


_RESAMPLE_MAP = {
    "nearest": getattr(Image, "NEAREST", 0),
    "box": getattr(Image, "BOX", 4),
    "bilinear": getattr(Image, "BILINEAR", 2),
    "bicubic": getattr(Image, "BICUBIC", 3),
    "lanczos": getattr(Image, "LANCZOS", 1),
    # Special mode handled separately for pixel-art downscaling
    "pixel": None,
}

_METHOD_MAP = {
    "mediancut": getattr(Image, "MEDIANCUT", 0) if Image else 0,
    "fastoctree": getattr(Image, "FASTOCTREE", 2) if Image else 2,
    "maxcoverage": getattr(Image, "MAXCOVERAGE", 3) if Image else 3,
}

_DITHER_MAP = {
    "none": getattr(Image, "NONE", 0) if Image else 0,
    "fs": getattr(Image, "FLOYDSTEINBERG", 1) if Image else 1,
}


def _maybe_resize(im: Image.Image, w: int, h: int, mode: str) -> Image.Image:
    if (w is None or w <= 0) and (h is None or h <= 0):
        return im
    mode = str(mode).lower()
    resample = _RESAMPLE_MAP.get(mode, _RESAMPLE_MAP["lanczos"])  # fallback to lanczos
    ow, oh = im.size
    # Determine target size
    if w and w > 0 and h and h > 0:
        tw, th = int(w), int(h)
    elif w and w > 0:
        tw = int(w)
        th = max(1, int(round(oh * (w / ow))))
    elif h and h > 0:
        th = int(h)
        tw = max(1, int(round(ow * (h / oh))))
    else:
        return im

    # Pixel-art downscaling: block-averaging to exact grid when possible
    if mode == "pixel":
        return _pixel_downscale(im, tw, th)

    # Fallback to standard resampling
    return im.resize((tw, th), resample)


def _pixel_downscale(im: Image.Image, tw: int, th: int) -> Image.Image:
    """Downscale to (tw,th) by averaging exact blocks when divisible, else BOX.

    - If original size is an exact multiple of target, averages each block
      (area resample) which preserves edges without blur between cells.
    - Otherwise, falls back to BOX resampling which is still area-based.
    - If upscaling, uses NEAREST to retain pixel edges.
    """
    ow, oh = im.size
    if tw >= ow or th >= oh:
        return im.resize((tw, th), cast(int, _RESAMPLE_MAP["nearest"]))

    try:
        import numpy as np
    except Exception as e:
        raise ImportError("NumPy is required for 'pixel' resample mode") from e

    mode = im.mode
    arr = np.array(im, dtype=np.float32)
    if oh % th == 0 and ow % tw == 0:
        fy = oh // th
        fx = ow // tw
        # Ensure array is HxWxC
        if arr.ndim == 2:
            arr = arr[..., None]
        h, w, c = arr.shape
        arr = arr.reshape(th, fy, tw, fx, c).mean(axis=(1, 3))
        arr = np.clip(arr, 0, 255).astype("uint8")
        if mode == "RGBA" and arr.shape[-1] == 3:
            mode = "RGB"
        return Image.fromarray(arr, mode=mode if mode in ("RGB", "RGBA") else "RGB")
    else:
        # Non-integer scale: area resample
        return im.resize((tw, th), _RESAMPLE_MAP["box"])        


def _flatten_alpha_on_color(im: Image.Image, rgb: tuple[int, int, int]) -> Image.Image:
    if im.mode != "RGBA":
        return im.convert("RGB")
    bg = Image.new("RGB", im.size, rgb)
    bg.paste(im, mask=im.split()[3])
    return bg


def _reduce_palette(im: Image.Image, max_colors: int, keep_alpha: bool) -> Image.Image:
    # Pillow quantize max 256 colors
    n = max(1, min(int(max_colors), 256))
    method_val: Any = _METHOD_MAP.get("mediancut", 0)
    if keep_alpha and im.mode == "RGBA":
        # Quantize RGB only; reattach alpha
        rgb = im.convert("RGB").quantize(colors=n, method=cast(Any, method_val)).convert("RGB")
        a = im.split()[3]
        out = Image.merge("RGBA", (*rgb.split(), a))
        return out
    else:
        return im.convert("RGB").quantize(colors=n, method=cast(Any, method_val)).convert("RGB")


class ColorGelSave:
    """Save image with compact controls (PNG/WebP, resize, opacity, palette)."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "Input image (RGB/RGBA)."}),
                "filename": ("STRING", {"default": "image", "multiline": False, "tooltip": "Base filename without extension."}),
                "save_as": (["webp", "png"], {"default": "webp", "tooltip": "Output format."}),
                "lossless": ("BOOLEAN", {"default": False, "tooltip": "Lossless WebP (ignored for PNG)."}),
                "compression": ("INT", {"default": 90, "min": 1, "max": 100, "step": 1, "tooltip": "WebP quality 1-100; PNG compression mapped 0-9."}),
                "reduce_palette": ("BOOLEAN", {"default": False, "tooltip": "Reduce colors via quantization."}),
                "reduce_palette_max_colors": ("INT", {"default": 32, "min": 1, "max": 256, "step": 1, "tooltip": "Max colors after palette reduction."}),
                "save_opacity": ("BOOLEAN", {"default": True, "tooltip": "Keep alpha channel; if False flattens on background color."}),
                "flatten_bg_color": ("STRING", {"default": "#FFFFFF", "multiline": False, "tooltip": "Background color when save_opacity is False (hex or r,g,b)."}),
                "resize_w": ("INT", {"default": 0, "min": 0, "max": 16384, "step": 1, "tooltip": "Resize width; 0 keeps original."}),
                "resize_h": ("INT", {"default": 0, "min": 0, "max": 16384, "step": 1, "tooltip": "Resize height; 0 keeps original."}),
            },
            "optional": {
                "resample": (["nearest", "box", "bilinear", "bicubic", "lanczos", "pixel"], {"default": "lanczos", "tooltip": "Resize filter; 'pixel' does block-averaging to a fixed grid."}),
                "sharpen": ("BOOLEAN", {"default": False, "tooltip": "Apply unsharp mask after resize."}),
                "sharpen_amount": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 5.0, "step": 0.05, "tooltip": "Sharpen strength (mapped to 0-500%)."}),
                "sharpen_radius": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.25, "tooltip": "Unsharp mask radius (pixels)."}),
                "sharpen_threshold": ("INT", {"default": 0, "min": 0, "max": 255, "step": 1, "tooltip": "Unsharp threshold (edge sensitivity)."}),
                "use_names_for_filenames": ("BOOLEAN", {"default": False, "tooltip": "Use provided names as filenames for batches."}),
                "names_packed": ("STRING", {"default": "", "multiline": True, "tooltip": "Optional newline-separated names (one per image) used when saving a batch."}),
                "overwrite": ("BOOLEAN", {"default": False, "tooltip": "Overwrite existing files instead of suffixing (name(2), …)."}),
                "optimize_png": ("BOOLEAN", {"default": True, "tooltip": "Use PNG optimizer (may be slower)."}),
                "drop_metadata": ("BOOLEAN", {"default": True, "tooltip": "Strip embedded metadata (EXIF/ICC) when possible."}),
                "reduce_palette_dither": (["none", "fs"], {"default": "none", "tooltip": "Dither for palette reduction (fs/none)."}),
                "reduce_palette_method": (["mediancut", "fastoctree", "maxcoverage"], {"default": "mediancut", "tooltip": "Palette selection algorithm."}),
                "posterize_bits": ("INT", {"default": 0, "min": 0, "max": 8, "step": 1, "tooltip": "Posterize RGB to N bits before palette reduction (0 disables)."}),
                "palette_lock_across_batch": ("BOOLEAN", {"default": False, "tooltip": "Derive palette from first image and reuse for all in the batch."}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("image", "file", "files_json")
    FUNCTION = "run"
    CATEGORY = "Color Gel Pixel/Core"

    def run(
        self,
        image: torch.Tensor,
        filename: str,
        save_as: str,
        lossless: bool,
        compression: int,
        reduce_palette: bool,
        reduce_palette_max_colors: int,
        save_opacity: bool,
        flatten_bg_color: str,
        resize_w: int,
        resize_h: int,
        resample: str = "lanczos",
        sharpen: bool = False,
        sharpen_amount: float = 1.0,
        sharpen_radius: float = 1.0,
        sharpen_threshold: int = 0,
        use_names_for_filenames: bool = False,
        names_packed: str = "",
        overwrite: bool = False,
        optimize_png: bool = True,
        drop_metadata: bool = True,
        reduce_palette_dither: str = "none",
        reduce_palette_method: str = "mediancut",
        posterize_bits: int = 0,
        palette_lock_across_batch: bool = False,
    ) -> tuple[torch.Tensor, str, str]:
        if torch is None or Image is None:
            raise ImportError("torch and Pillow are required to run ColorGelSave")

        imgs = _to_pil_list(image)
        base = _sanitize_basename(filename)
        ext = save_as.lower()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        outdir = _find_output_dir()
        # Sanity: ensure output dir is writable
        try:
            testfile = os.path.join(outdir, ".cg_save_test")
            with open(testfile, "wb") as _f:
                _f.write(b"ok")
            os.remove(testfile)
        except Exception as e:
            raise PermissionError(f"Output directory '{outdir}' not writable") from e
        paths: list[str] = []
        previews: list[torch.Tensor] = []
        has_alpha_input = (image.shape[-1] == 4)

        # Parse packed names (newline-separated)
        names: list[str] = []
        if isinstance(names_packed, str) and names_packed.strip():
            names = [s.strip() for s in names_packed.splitlines() if s.strip()]

        locked_pal_img: Image.Image | None = None
        for i, im0 in enumerate(imgs, start=1):
            im = _maybe_resize(im0, resize_w, resize_h, resample)

            if sharpen:
                percent = int(max(0, min(sharpen_amount, 5.0)) * 100)
                radius = max(0.0, float(sharpen_radius))
                threshold = max(0, min(int(sharpen_threshold), 255))
                im = im.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold))

            if not save_opacity:
                if _parse_hex_or_rgb is None:
                    raise ImportError("color parser not available")
                (r, g, b), _ = _parse_hex_or_rgb(flatten_bg_color)
                im = _flatten_alpha_on_color(im, (int(round(r * 255)), int(round(g * 255)), int(round(b * 255))))

            # Optional posterize prior to palette reduction
            if int(posterize_bits) > 0 and ImageOps is not None:
                if im.mode == "RGBA":
                    rgb = im.convert("RGB")
                    rgbp = ImageOps.posterize(rgb, int(posterize_bits))
                    a = im.split()[3]
                    im = Image.merge("RGBA", (*rgbp.split(), a))
                else:
                    im = ImageOps.posterize(im.convert("RGB"), int(posterize_bits))

            if reduce_palette:
                keep_alpha = (save_opacity and im.mode == "RGBA")
                if palette_lock_across_batch and len(imgs) > 1:
                    # Build locked palette from first image after preprocessing
                    if locked_pal_img is None:
                        rgb0 = im.convert("RGB")
                        q0 = rgb0.quantize(
                            colors=max(1, min(int(reduce_palette_max_colors), 256)),
                            method=cast(Any, _METHOD_MAP.get(reduce_palette_method, _METHOD_MAP["mediancut"])),
                            dither=cast(Any, _DITHER_MAP["none"]),
                        ).convert("P")
                        pal = q0.getpalette()
                        if pal is None:
                            pal = [0] * (256 * 3)
                        locked_pal_img = Image.new("P", (1, 1))
                        locked_pal_img.putpalette(pal)
                    # Apply locked palette with requested dither
                    dval_locked: Any = _DITHER_MAP.get(reduce_palette_dither, _DITHER_MAP["none"])  # mypy: Dither enum
                    q = im.convert("RGB").quantize(palette=locked_pal_img, dither=cast(Any, dval_locked))
                    if keep_alpha:
                        alpha_layer = im.split()[3] if im.mode == "RGBA" else None
                        q = q.convert("RGB")
                        if alpha_layer is not None:
                            im = Image.merge("RGBA", (*q.split(), alpha_layer))
                        else:
                            im = q
                    else:
                        im = q.convert("RGB")
                else:
                    # Per-image reduction
                    method_val: Any = _METHOD_MAP.get(reduce_palette_method, _METHOD_MAP["mediancut"])  # mypy: Quantize enum
                    dval: Any = _DITHER_MAP.get(reduce_palette_dither, _DITHER_MAP["none"]) if hasattr(Image, "FLOYDSTEINBERG") else 0
                    n = max(1, min(int(reduce_palette_max_colors), 256))
                    if keep_alpha and im.mode == "RGBA":
                        rgb = im.convert("RGB").quantize(colors=n, method=cast(Any, method_val), dither=cast(Any, dval)).convert("RGB")
                        alpha_layer = im.split()[3]
                        im = Image.merge("RGBA", (*rgb.split(), alpha_layer))
                    else:
                        im = im.convert("RGB").quantize(colors=n, method=cast(Any, method_val), dither=cast(Any, dval)).convert("RGB")

            # Optionally strip metadata (best-effort)
            if drop_metadata:
                try:
                    # Remove common keys; saving without pnginfo/exif keeps it minimal
                    for k in ("icc_profile", "exif"):
                        if hasattr(im, "info") and isinstance(im.info, dict):
                            im.info.pop(k, None)
                except Exception:
                    pass

            # Path: if batch and names provided+enabled, use them; else timestamp index
            if len(imgs) == 1:
                outname = f"{base}_{stamp}.{ext}"
            elif use_names_for_filenames and i-1 < len(names):
                nm = _sanitize_basename(names[i-1])
                outname = f"{nm}.{ext}"
            else:
                outname = f"{base}_{stamp}_{i:04d}.{ext}"
            outpath = os.path.join(outdir, outname)
            # Collision-safe suffix if file already exists (unless overwrite)
            if not overwrite and os.path.exists(outpath):
                root, dot, extension = outpath.rpartition(".")
                suffix_idx = 2
                while os.path.exists(f"{root}({suffix_idx}).{extension}"):
                    suffix_idx += 1
                outpath = f"{root}({suffix_idx}).{extension}"

            if ext == "webp":
                params = {
                    "lossless": bool(lossless),
                    "quality": int(max(1, min(compression, 100))),
                    "method": 6,
                }
                # For transparency ensure RGBA when saving with alpha
                if save_opacity and has_alpha_input and im.mode != "RGBA":
                    im = im.convert("RGBA")
                try:
                    im.save(outpath, format="WEBP", **params)
                except OSError as e:
                    raise OSError(f"Failed to save WEBP to '{outpath}'") from e
            elif ext == "png":
                # Map 1..100 to 0..9
                level = int(round((compression / 100.0) * 9))
                params = {
                    "optimize": bool(optimize_png),
                    "compress_level": max(0, min(level, 9)),
                }
                try:
                    im.save(outpath, format="PNG", **params)
                except OSError as e:
                    raise OSError(f"Failed to save PNG to '{outpath}'") from e
            else:
                raise ValueError(f"Unsupported save_as: {save_as!r}")

            previews.append(_pil_to_torch(im))
            paths.append(outpath)

        # Return stacked preview when batch; else single
        if len(previews) == 1:
            return previews[0], paths[0], json.dumps(paths)
        else:
            # Stack to BxHxWxC and return all paths in one STRING (newline-separated)
            import torch as _t
            return _t.stack(previews, dim=0), "\n".join(paths), json.dumps(paths)


def _pil_to_torch(im: Image.Image) -> torch.Tensor:
    # Convert PIL (RGB/RGBA) to torch float tensor HxWxC in 0..1
    try:
        import numpy as np
    except Exception as e:
        raise ImportError("NumPy is required to convert PIL→Torch preview") from e
    np_arr = np.array(im, copy=True)
    t = torch.from_numpy(np_arr).contiguous().to(dtype=torch.float32) / 255.0
    return t
