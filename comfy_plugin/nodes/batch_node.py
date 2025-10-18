# SPDX-License-Identifier: MIT
"""
Batch helpers for Color Gel workflows.

ColorGelBatch2 — combine two IMAGE tensors into a batch (B=2) so they can be
saved with identical settings through a single save node.
"""

from __future__ import annotations

from typing import Any

try:
    import torch
except Exception:  # pragma: no cover
    torch = None  # type: ignore[assignment]


def _as_3d(img: torch.Tensor) -> torch.Tensor:
    if img.dim() == 3:
        return img
    if img.dim() == 4:
        if img.shape[0] != 1:
            raise ValueError("Input already a batch; expected single image")
        return img.squeeze(0)
    raise ValueError("image must be HxWxC or BxHxWxC")


def _match_channels(a: torch.Tensor, b: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    ca = a.shape[-1]
    cb = b.shape[-1]
    if ca not in (3, 4) or cb not in (3, 4):
        raise ValueError("images must have 3 or 4 channels")
    target = 4 if (ca == 4 or cb == 4) else 3
    if ca == target and cb == target:
        return a, b
    if ca == 3 and target == 4:
        alpha = torch.ones(a.shape[0], a.shape[1], 1, dtype=a.dtype, device=a.device)
        a = torch.cat([a, alpha], dim=-1)
    if cb == 3 and target == 4:
        alpha = torch.ones(b.shape[0], b.shape[1], 1, dtype=b.dtype, device=b.device)
        b = torch.cat([b, alpha], dim=-1)
    return a, b



class ColorGelBatchN:
    """Combine up to 10 images into a batch (B=N).

    - Requires at least `image_1`.
    - `image_2` .. `image_10` are optional; only connected inputs are used.
    - All images must have the same width/height. Channels can be RGB/RGBA
      and will be matched automatically (RGB gets alpha=1 if needed).
    - Outputs a single `IMAGE` tensor with shape BxHxWxC.
    """

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        opts: dict[str, dict[str, Any]] = {
            "required": {
                "image_1": ("IMAGE", {"tooltip": "First image (RGB/RGBA)."}),
            },
            "optional": {},
        }
        # Add optional image_2..image_10
        for i in range(2, 11):
            opts["optional"][f"image_{i}"] = ("IMAGE", {"tooltip": f"Optional image {i} (RGB/RGBA)."})
        return opts

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "run"
    CATEGORY = "Color Gel Pixel/Batch"

    def run(
        self,
        image_1: torch.Tensor,
        image_2: torch.Tensor | None = None,
        image_3: torch.Tensor | None = None,
        image_4: torch.Tensor | None = None,
        image_5: torch.Tensor | None = None,
        image_6: torch.Tensor | None = None,
        image_7: torch.Tensor | None = None,
        image_8: torch.Tensor | None = None,
        image_9: torch.Tensor | None = None,
        image_10: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor]:
        if torch is None:
            raise ImportError("torch is required")
        imgs_in: list[torch.Tensor | None] = [
            image_1,
            image_2,
            image_3,
            image_4,
            image_5,
            image_6,
            image_7,
            image_8,
            image_9,
            image_10,
        ]
        imgs: list[torch.Tensor] = []
        base: torch.Tensor | None = None
        for t in imgs_in:
            if t is None:
                continue
            x = _as_3d(t)
            if torch.isnan(x).any() or torch.isinf(x).any():
                raise ValueError("Input image contains NaN/inf values")
            if base is None:
                base = x
            else:
                if x.shape[:2] != base.shape[:2]:
                    raise ValueError("all images must have same width/height to batch")
                # match channels vs the current base target (based on existence of alpha)
                base, x = _match_channels(base, x)
                # ensure dtype/device match base
                if x.dtype != base.dtype or x.device != base.device:
                    x = x.to(dtype=base.dtype, device=base.device)
            imgs.append(x)

        if not imgs:
            raise ValueError("no images provided to batch")
        if len(imgs) == 1:
            return (imgs[0].unsqueeze(0),)

        # Now ensure all match the final target (in case base changed during match)
        target = imgs[0]
        fixed: list[torch.Tensor] = [target]
        for x in imgs[1:]:
            t0, t1 = _match_channels(target, x)
            # _match_channels may have converted target; keep the result as new target
            target = t0
            if t1.dtype != target.dtype or t1.device != target.device:
                t1 = t1.to(dtype=target.dtype, device=target.device)
            fixed[0] = target
            fixed.append(t1)

        batched = torch.stack(fixed, dim=0).contiguous()
        return (batched,)
