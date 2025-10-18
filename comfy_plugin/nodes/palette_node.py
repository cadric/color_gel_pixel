# SPDX-License-Identifier: MIT
"""
ColorGelPalette — central palette selector that outputs a palette id.

Connect this node's `palette` output to Color Gel (select) `palette_from_node`
to switch palettes across many branches from one place.
"""

from __future__ import annotations

from typing import Any

from . import color_gel_node as _gel


class ColorGelPalette:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        opts = list(_gel._PALETTE_ORDER) or [""]
        default = opts[0] if opts else ""
        return {
            "required": {
                "palette": (opts, {"default": default, "tooltip": "Palette from comfy_plugin/palettes."}),
            },
            "optional": {},
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("palette",)
    FUNCTION = "run"
    CATEGORY = "Color Gel Pixel/Utils"

    def run(self, palette: str) -> tuple[str]:
        p = str(palette or "").strip()
        if p and p not in _gel._PALETTE_CACHE:
            raise ValueError(f"Unknown palette: {p}")
        return (p,)

