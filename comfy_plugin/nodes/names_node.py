# SPDX-License-Identifier: MIT
"""
ColorGelNamesN — pack up to 10 STRING inputs into a newline-separated list
for use with Color Gel Save (use_names_for_filenames + names_packed).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def _sanitize_name(s: str) -> str:
    # Normalize to ASCII for portability; drop accents/marks
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    s = s.strip()
    # Replace separators; collapse whitespace to underscores
    s = s.replace("/", "_").replace("\\", "_")
    s = re.sub(r"\s+", "_", s)
    # Keep a portable subset
    s = re.sub(r"[^0-9A-Za-z._-]", "", s)
    # Avoid leading dots (hidden files) and repetitive separators
    s = s.lstrip(".")
    s = re.sub(r"_+", "_", s)
    s = re.sub(r"\.+", ".", s)
    # Windows reserved basenames
    reserved = {"CON","PRN","AUX","NUL","COM1","COM2","COM3","COM4","COM5","COM6","COM7","COM8","COM9",
                "LPT1","LPT2","LPT3","LPT4","LPT5","LPT6","LPT7","LPT8","LPT9"}
    if s.upper() in reserved:
        s = f"{s}_file"
    # Cap length conservatively
    if len(s) > 120:
        s = s[:120]
    return s or "image"


class ColorGelNamesN:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        req = {"name_1": ("STRING", {"default": "", "multiline": False, "tooltip": "First name or title."})}
        opt: dict[str, Any] = {
            "prefix": ("STRING", {"default": "", "multiline": False, "tooltip": "Optional prefix added to each name."}),
            "suffix": ("STRING", {"default": "", "multiline": False, "tooltip": "Optional suffix added to each name."}),
        }
        for i in range(2, 11):
            opt[f"name_{i}"] = ("STRING", {"default": "", "multiline": False, "tooltip": f"Optional name {i}."})
        return {"required": req, "optional": opt}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("names_packed",)
    FUNCTION = "run"
    CATEGORY = "Color Gel Pixel/Utils"

    def run(
        self,
        name_1: str,
        prefix: str = "",
        suffix: str = "",
        name_2: str | None = "",
        name_3: str | None = "",
        name_4: str | None = "",
        name_5: str | None = "",
        name_6: str | None = "",
        name_7: str | None = "",
        name_8: str | None = "",
        name_9: str | None = "",
        name_10: str | None = "",
    ) -> tuple[str]:
        names: list[str | None] = [name_1, name_2, name_3, name_4, name_5, name_6, name_7, name_8, name_9, name_10]
        pre = str(prefix or "")
        suf = str(suffix or "")
        cleaned = [_sanitize_name(f"{pre}{n}{suf}") for n in names if isinstance(n, str) and n.strip()]
        if not cleaned:
            return ("image",)
        # Enforce uniqueness to avoid overwrites downstream
        seen: dict[str, int] = {}
        unique: list[str] = []
        for nm in cleaned:
            count = seen.get(nm, 0) + 1
            seen[nm] = count
            unique.append(nm if count == 1 else f"{nm}({count})")
        packed = "\n".join(unique)
        return (packed,)
