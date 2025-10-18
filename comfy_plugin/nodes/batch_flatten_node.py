# SPDX-License-Identifier: MIT
"""
ColorGelBatchFlatten — concatenate up to 10 IMAGE batches along the batch axis.

All inputs are optional; at least one must be connected.
Images must share width/height; channels are unified to RGBA if needed.
"""

from __future__ import annotations

from typing import Any

try:
    import torch
except Exception:  # pragma: no cover
    torch = None  # type: ignore[assignment]


def _as_4d(x: torch.Tensor) -> torch.Tensor:
    if x.dim() == 3:
        return x.unsqueeze(0)
    if x.dim() == 4:
        return x
    raise ValueError("image must be HxWxC or BxHxWxC")


def _ensure_rgba(b: torch.Tensor) -> torch.Tensor:
    c = b.shape[-1]
    if c == 4:
        return b
    if c == 3:
        a = torch.ones(b.shape[0], b.shape[1], b.shape[2], 1, dtype=b.dtype, device=b.device)
        return torch.cat([b, a], dim=-1)
    raise ValueError("channels must be 3 or 4")


class ColorGelBatchFlatten:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        req: dict[str, Any] = {}
        opt: dict[str, Any] = {}
        for i in range(1, 11):
            opt[f"images_{i}"] = ("IMAGE", {"tooltip": f"Optional batch {i} (B x H x W x C)."})
        return {"required": req, "optional": opt}

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "run"
    CATEGORY = "Color Gel Pixel/Batch"

    def run(
        self,
        images_1: torch.Tensor | None = None,
        images_2: torch.Tensor | None = None,
        images_3: torch.Tensor | None = None,
        images_4: torch.Tensor | None = None,
        images_5: torch.Tensor | None = None,
        images_6: torch.Tensor | None = None,
        images_7: torch.Tensor | None = None,
        images_8: torch.Tensor | None = None,
        images_9: torch.Tensor | None = None,
        images_10: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor]:
        if torch is None:
            raise ImportError("torch is required")
        inputs: list[torch.Tensor | None] = [
            images_1, images_2, images_3, images_4, images_5,
            images_6, images_7, images_8, images_9, images_10,
        ]
        batches: list[torch.Tensor] = []
        base_shape = None
        target_dtype = None
        target_device = None
        for t in inputs:
            if t is None:
                continue
            b = _as_4d(t)
            if torch.isnan(b).any() or torch.isinf(b).any():
                raise ValueError("Input batch contains NaN/inf values")
            if base_shape is None:
                base_shape = b.shape[1:3]
                target_dtype = b.dtype
                target_device = b.device
            if b.shape[1:3] != base_shape:
                raise ValueError("all batches must share width/height")
            if b.dtype != target_dtype or b.device != target_device:
                b = b.to(dtype=target_dtype, device=target_device)
            b = _ensure_rgba(b)
            batches.append(b)
        if not batches:
            raise ValueError("no batches provided")
        if len(batches) == 1:
            return (batches[0],)
        out = torch.cat(batches, dim=0).contiguous()
        return (out,)
