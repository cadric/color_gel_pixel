# SPDX-License-Identifier: MIT
# Copyright (c) 2025

"""
comfy_plugin — ComfyUI nodes package (strict layout)

Exports top-level NODE_CLASS_MAPPINGS and NODE_DISPLAY_NAME_MAPPINGS.
"""

from .nodes.batch_flatten_node import ColorGelBatchFlatten  # noqa: F401
from .nodes.batch_node import ColorGelBatchN  # noqa: F401
from .nodes.color_gel_node import (  # noqa: F401
    NODE_CLASS_MAPPINGS as _GEL_MAP,
)
from .nodes.color_gel_node import (
    NODE_DISPLAY_NAME_MAPPINGS as _GEL_DISP,
)
from .nodes.names_node import ColorGelNamesN  # noqa: F401
from .nodes.palette_node import ColorGelPalette  # noqa: F401
from .nodes.preview_node import ColorGelPreview  # noqa: F401
from .nodes.save_node import ColorGelSave  # noqa: F401

# Merge mappings
NODE_CLASS_MAPPINGS = dict(_GEL_MAP)
NODE_DISPLAY_NAME_MAPPINGS = dict(_GEL_DISP)

NODE_CLASS_MAPPINGS["Color Gel Save"] = ColorGelSave
NODE_DISPLAY_NAME_MAPPINGS["Color Gel Save"] = "Color Gel Save"
NODE_CLASS_MAPPINGS["Color Gel Preview"] = ColorGelPreview
NODE_DISPLAY_NAME_MAPPINGS["Color Gel Preview"] = "Color Gel Preview"
NODE_CLASS_MAPPINGS["Color Gel Batch (N)"] = ColorGelBatchN
NODE_DISPLAY_NAME_MAPPINGS["Color Gel Batch (N)"] = "Color Gel Batch (N)"
NODE_CLASS_MAPPINGS["Color Gel Names (N)"] = ColorGelNamesN
NODE_DISPLAY_NAME_MAPPINGS["Color Gel Names (N)"] = "Color Gel Names (N)"
NODE_CLASS_MAPPINGS["Color Gel Batch Flatten"] = ColorGelBatchFlatten
NODE_DISPLAY_NAME_MAPPINGS["Color Gel Batch Flatten"] = "Color Gel Batch Flatten"
NODE_CLASS_MAPPINGS["Color Gel Palette"] = ColorGelPalette
NODE_DISPLAY_NAME_MAPPINGS["Color Gel Palette"] = "Color Gel Palette"
# No registration for additional palette-specific or fixed-quantize nodes

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    # Export classes for typing/tools per AGENTS.md
    "ColorGelSave",
    "ColorGelPreview",
    "ColorGelBatchN",
    "ColorGelNamesN",
    "ColorGelBatchFlatten",
    "ColorGelPalette",
]
