"""Masken: eine Farbkorrektur nur in einem Bereich (z. B. Himmel dunkler/blauer, Mitte heller).

Formen: linear (Verlauf, z. B. Himmel), mirror (Streifen), circle, rectangle, heart, star, sky (Verlauf von oben bis
zum Horizont). Weiche Kante (feather), umkehren (invert), Lage x/y, Größe, Drehung.
Im Export: Aufnahme zweimal (normal + mit Masken-Farbe), per ffmpeg maskedmerge mit dem Maskenbild gemischt.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

SHAPES = {"linear": "Linear (gradient)", "mirror": "Mirror (band)", "circle": "Circle", "rectangle": "Rectangle",
          "heart": "Heart", "star": "Star", "sky": "Sky (top down to horizon)"}


def make(mask: dict, W: int, H: int) -> Image.Image:
    """Graues Maskenbild W×H (255 = Korrektur voll, 0 = keine)."""
    shape = mask.get("shape", "circle")
    x, y = float(mask.get("x", 0.5)) * W, float(mask.get("y", 0.5)) * H
    size = float(mask.get("size", 0.5))
    rot = float(mask.get("rot", 0.0))
    feather = float(mask.get("feather", 0.3))
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    short = min(W, H)
    if shape in ("linear", "sky", "mirror"):
        # Verlauf senkrecht zur Linie durch (x, y), Linie um rot gedreht
        big = int(math.hypot(W, H)) * 2
        g = Image.new("L", (big, big), 0)
        gd = ImageDraw.Draw(g)
        band = max(2, int(short * (0.05 + feather * 0.6)))
        if shape == "mirror":
            half = max(2, int(short * size * 0.25))
            gd.rectangle((0, big // 2 - half, big, big // 2 + half), fill=255)
        else:
            gd.rectangle((0, 0, big, big // 2), fill=255)   # obere Hälfte = Korrektur (Himmel)
        g = g.filter(ImageFilter.GaussianBlur(band / 2))
        g = g.rotate(rot, resample=Image.BICUBIC)
        cy = y if shape != "sky" else float(mask.get("y", 0.42)) * H
        m = g.crop((int(big / 2 - x), int(big / 2 - cy), int(big / 2 - x) + W, int(big / 2 - cy) + H))
    else:
        r = size * short * 0.5
        if shape == "circle":
            d.ellipse((x - r, y - r, x + r, y + r), fill=255)
        elif shape == "rectangle":
            d.rectangle((x - r * 1.3, y - r * 0.8, x + r * 1.3, y + r * 0.8), fill=255)
        elif shape == "heart":
            pts = []
            for k in range(120):
                t = k / 120 * 2 * math.pi
                hx = 16 * math.sin(t) ** 3
                hy = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
                pts.append((x + hx / 17 * r, y - hy / 17 * r))
            d.polygon(pts, fill=255)
        elif shape == "star":
            pts = []
            for k in range(10):
                a = -math.pi / 2 + k * math.pi / 5
                rr = r if k % 2 == 0 else r * 0.45
                pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
            d.polygon(pts, fill=255)
        if rot:
            m = m.rotate(-rot, center=(x, y), resample=Image.BICUBIC)
        if feather > 0:
            m = m.filter(ImageFilter.GaussianBlur(max(1, short * feather * 0.08)))
    if mask.get("invert"):
        m = ImageChops.invert(m)
    return m


def mask_file(mask: dict, W: int, H: int, cache: Path) -> Path:
    key = hashlib.sha1(json.dumps([mask.get(k) for k in ("shape", "x", "y", "size", "rot", "feather", "invert")] + [W, H],
                                  sort_keys=True).encode()).hexdigest()[:12]
    cache.mkdir(parents=True, exist_ok=True)
    f = cache / f"mask_{key}.png"
    if not f.exists():
        make(mask, W, H).convert("RGB").save(f)
    return f
