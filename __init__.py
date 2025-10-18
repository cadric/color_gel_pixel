# re-eksportér node mappings til ComfyUI
# SPDX-License-Identifier: MIT
# Copyright (c) 2025

"""
Entry point for ComfyUI plugin discovery.

Exports NODE_CLASS_MAPPINGS and NODE_DISPLAY_NAME_MAPPINGS from the strict
layout package under `comfy_plugin`.
"""

from .comfy_plugin import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
]
