# Fixed Palettes for Quantization

Drop JSON files here to use with "Color Gel (select)" when `quantize_fixed` is enabled and a `fixed_palette` is chosen.

Accepted JSON formats:
- Dict of name → hex/rgb:
  {
    "Color 1": "#AABBCC",
    "Color 2": [170, 187, 204]
  }
- List of rows with hex/rgb:
  [
    {"name": "C1", "hex": "#AABBCC"},
    {"hex": "#112233"}
  ]

Max 256 colors. After adding files, use "Reload Custom Nodes" to refresh dropdowns/caches.

Included sets (curated):
- dawnbringer_db16.json — DawnBringer 16 (public domain/CC0)
- dawnbringer_db32.json — DawnBringer 32 (public domain/CC0)
- aap_64.json — AAP‑64 by Adigun A. Polack (see author’s license/attribution)
- pico8_16.json — PICO‑8 palette (see Lexaloffle usage notes)
- c64_vic2_16.json — Commodore 64 (VIC‑II, “Pepto” style calibration)
- websafe_216.json — 6×6×6 web‑safe color cube
