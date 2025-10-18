# SPDX-License-Identifier: MIT
"""
ColorGelPreview — lightweight preview node to decouple viewing from saving.

Connect the output `image` from Color Gel Save (or any IMAGE tensor) here to
show a preview window in ComfyUI. Returns the same image for chaining.
"""

from __future__ import annotations

import os
import time
from typing import Any, cast

try:  # Optional at import; required at run
    import torch
except Exception:  # pragma: no cover
    torch = None  # type: ignore[assignment]

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None  # type: ignore[assignment]

def _get_temp_dir() -> str:
    # Prefer ComfyUI temp folder if available
    try:
        import folder_paths  # type: ignore[import-not-found]
        td = cast(str, folder_paths.get_temp_directory())
        os.makedirs(td, exist_ok=True)
        return td
    except Exception:
        pass
    td_env = os.environ.get("COMFYUI_TEMP_DIR")
    if td_env:
        os.makedirs(td_env, exist_ok=True)
        return td_env
    # fallback local temp
    td = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "temp"))
    os.makedirs(td, exist_ok=True)
    return td


def _to_pil_list(image: torch.Tensor) -> list[Image.Image]:
    if torch is None or Image is None:
        raise ImportError("torch and Pillow are required for preview")
    if image.dim() not in (3, 4):
        raise ValueError("image must be HxWxC or BxHxWxC")
    if image.dim() == 3:
        image = image.unsqueeze(0)
    if image.shape[-1] not in (3, 4):
        raise ValueError("image must have 3 or 4 channels")
    # convert each batch element to PIL
    ims: list[Image.Image] = []
    try:
        import numpy as np
    except Exception as e:
        raise ImportError("NumPy is required to preview images") from e
    arr = (
        image.clip(0.0, 1.0)
        .to(dtype=torch.float32)
        .cpu()
        .contiguous()
        .numpy()
        * 255.0
    ).astype(np.uint8)
    for i in range(arr.shape[0]):
        a = arr[i]
        mode = "RGBA" if a.shape[-1] == 4 else "RGB"
        ims.append(Image.fromarray(a, mode=mode))
    return ims


class ColorGelPreview:
    """Pass-through preview node for IMAGE tensors."""

    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "Image to preview (RGB/RGBA)."}),
            },
            "optional": {
                # Optional label for clarity in complex graphs
                "title": ("STRING", {"default": "", "multiline": False, "tooltip": "Optional label; does not affect output."}),
                "max_previews": ("INT", {"default": 32, "min": 1, "max": 256, "step": 1, "tooltip": "Limit number of images shown when input is a batch."}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "Color Gel Pixel/Core"

    def run(self, image: torch.Tensor, title: str = "", max_previews: int = 32) -> dict[str, Any]:
        if torch is None or Image is None:
            raise ImportError("torch and Pillow are required to preview images")

        pil_list = _to_pil_list(image)
        # Cap previews to avoid flooding UI/temp
        MAX_PREVIEWS = max(1, int(max_previews))
        truncated = False
        if len(pil_list) > MAX_PREVIEWS:
            pil_list = pil_list[:MAX_PREVIEWS]
            truncated = True

        td = _get_temp_dir()
        subfolder = "color_gel_preview"
        out_subdir = os.path.join(td, subfolder)
        os.makedirs(out_subdir, exist_ok=True)

        # Opportunistic cleanup of old previews (>48h)
        try:
            import time as _t
            now = _t.time()
            ttl = 48 * 3600
            for fn in os.listdir(out_subdir):
                fp = os.path.join(out_subdir, fn)
                try:
                    if os.path.isfile(fp) and (now - os.path.getmtime(fp) > ttl):
                        os.remove(fp)
                except Exception:
                    pass
        except Exception:
            pass

        ts = int(time.time() * 1000)
        ui_images = []
        for idx, im in enumerate(pil_list):
            fname = f"preview_{ts}_{idx}.png"
            outp = os.path.join(out_subdir, fname)
            try:
                im.save(outp, format="PNG", optimize=True)
            except OSError as e:
                raise OSError(f"Failed to save preview PNG to '{outp}'") from e
            ui_images.append({"filename": fname, "subfolder": subfolder, "type": "temp"})

        ui_text = title or "preview"
        if truncated:
            ui_text = f"{ui_text} (truncated)"
        return {
            "ui": {"images": ui_images, "text": ui_text},
            "result": (image,),
        }
