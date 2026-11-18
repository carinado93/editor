"""Reel-Intro-Titel: Ortsname in GROSSBUCHSTABEN, dünne Schrift, sehr weite Laufweite, weiß, weicher Schatten.

Animation (Standard): langsam einblenden, dabei zieht sich die Laufweite langsam zusammen
(0,62 em → 0,45 em), nach ~2,8 s ausblenden. Optional eine kleinere Unterzeile.
Gerendert wird nur das Titel-Fenster als PNG-Folge (RGBA) und dann über das Video gelegt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..config import ROOT

FONTS = {
    "Montserrat ExtraLight": "Montserrat-ExtraLight.ttf",
    "Montserrat Light": "Montserrat-Light.ttf",
    "Raleway Thin": "Raleway-Thin.ttf",
    "Raleway ExtraLight": "Raleway-ExtraLight.ttf",
    "Josefin Sans Light": "JosefinSans-Light.ttf",
    "Inter Light": "Inter-Light.ttf",
}


@dataclass
class Title:
    text: str = "SRI LANKA"
    subtitle: str = ""
    font: str = "Montserrat ExtraLight"
    size: float = 0.075          # Schriftgröße als Anteil der Bildbreite
    spacing: float = 0.45        # Laufweite am Ende (em)
    spacing_start: float = 0.62  # Laufweite am Anfang (em) – zieht sich zusammen
    color: tuple = (255, 255, 255)
    y: float = 0.44              # Mitte der Zeile, Anteil der Bildhöhe (etwas über der Mitte)
    start: float = 0.2
    duration: float = 3.0
    fade_in: float = 1.0
    fade_out: float = 0.7
    animate: bool = True
    anim_in: str = "tracking"    # tracking | fade | rise | letters | blur
    anim_out: str = "fade"       # fade | sink | none
    keep_case: bool = False      # Abspann (@handle) nicht in Großbuchstaben
    shadow: float = 0.45
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict | None) -> "Title":
        d = dict(d or {})
        t = cls()
        for k, v in d.items():
            if hasattr(t, k) and v is not None:
                setattr(t, k, tuple(v) if k == "color" else v)
        return t


def font_path(name: str) -> Path:
    return ROOT / "assets" / "fonts" / FONTS.get(name, FONTS["Montserrat ExtraLight"])


def _ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def _ease_out(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


ANIMS_IN = {"tracking": "Fade in, spacing tightens", "fade": "Fade in", "rise": "Rise up",
            "letters": "Letter by letter", "blur": "Blur in"}
ANIMS_OUT = {"fade": "Fade out", "sink": "Sink and fade", "none": "Cut (no animation)"}


def state(t: Title, time: float) -> tuple[float, float]:
    """(Deckkraft 0..1, Laufweite in em) zum Zeitpunkt time (Sekunden ab Video-Anfang)."""
    u = time - t.start
    if u < 0 or u > t.duration:
        return 0.0, t.spacing
    if not t.animate:
        return 1.0, t.spacing
    a_in = 1.0 if t.anim_in == "letters" else _ease(u / max(0.01, t.fade_in))
    a_out = 1.0 if t.anim_out == "none" else 1 - _ease((u - (t.duration - t.fade_out)) / max(0.01, t.fade_out))
    sp = t.spacing
    if t.anim_in == "tracking":
        sp = t.spacing_start + (t.spacing - t.spacing_start) * _ease_out(u / max(0.1, t.duration * 0.9))
    return a_in * a_out, sp


def _motion(t: Title, time: float, H: int, size: int) -> tuple[float, float, float]:
    """(y-Versatz in px, Unschärfe-Radius, Buchstaben-Fortschritt 0..1) für die Ein-/Ausblend-Art."""
    u = time - t.start
    dy, blur, letters = 0.0, 0.0, 1.0
    if not t.animate:
        return dy, blur, letters
    p_in = _ease_out(u / max(0.01, t.fade_in * 1.2))
    if t.anim_in == "rise":
        dy += (1 - p_in) * size * 0.6
    elif t.anim_in == "blur":
        blur = (1 - p_in) * size * 0.22
    elif t.anim_in == "letters":
        letters = min(1.0, u / max(0.01, t.fade_in * 1.4))
    if t.anim_out == "sink":
        q = _ease((u - (t.duration - t.fade_out)) / max(0.01, t.fade_out))
        dy += q * size * 0.5
    return dy, blur, letters


def _draw_tracked(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, cx: float, cy: float,
                  spacing_px: float, fill, letters: float = 1.0) -> tuple[int, int, int, int]:
    """Text mit Laufweite zentriert zeichnen (Laufweite nur ZWISCHEN den Buchstaben → echt zentriert).
    letters < 1: Buchstabe für Buchstabe einblenden (jeder mit eigener weicher Blende)."""
    widths = [f.getlength(ch) for ch in text]
    total = sum(widths) + spacing_px * max(0, len(text) - 1)
    asc, desc = f.getmetrics()
    x = cx - total / 2
    y = cy - (asc + desc) / 2
    n = max(1, len(text))
    for i, (ch, w) in enumerate(zip(text, widths)):
        a = 1.0 if letters >= 1 else max(0.0, min(1.0, letters * (n + 2) - i))
        if a > 0:
            draw.text((x, y), ch, font=f, fill=fill[:3] + (int(fill[3] * a),))
        x += w + spacing_px
    return int(cx - total / 2), int(y), int(cx + total / 2), int(y + asc + desc)


def fit_size(t: Title, W: int, max_width: float = 0.86) -> int:
    """Schriftgröße so, dass der Titel auch mit der weitesten Laufweite (Anfang der Animation) ins Bild passt."""
    text = " ".join((t.text if t.keep_case else t.text.upper()).split())
    size = max(10, int(W * t.size))
    sp = max(t.spacing, t.spacing_start if t.animate and t.anim_in == "tracking" else t.spacing)
    for _ in range(30):
        f = ImageFont.truetype(str(font_path(t.font)), size)
        total = sum(f.getlength(ch) for ch in text) + sp * size * max(0, len(text) - 1)
        if total <= W * max_width or size <= 10:
            break
        size = max(10, int(size * 0.94))
    return size


def render_frame(t: Title, W: int, H: int, time: float) -> Image.Image | None:
    alpha, sp = state(t, time)
    if alpha <= 0.003:
        return None
    text = " ".join((t.text if t.keep_case else t.text.upper()).split())
    size = fit_size(t, W)
    f = ImageFont.truetype(str(font_path(t.font)), size)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    dy, blur, letters = _motion(t, time, H, size)
    cy = H * t.y + dy
    _draw_tracked(d, text, f, W / 2, cy, sp * size, tuple(t.color) + (255,), letters)
    if t.subtitle:
        fs = ImageFont.truetype(str(font_path(t.font)), max(8, int(size * 0.36)))
        _draw_tracked(d, " ".join(t.subtitle.split()), fs, W / 2, cy + size * 0.95, sp * 0.8 * fs.size,
                      tuple(t.color) + (235,), letters)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if t.shadow:
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sh.putalpha(layer.getchannel("A").point(lambda v: int(v * t.shadow)))
        sh = sh.filter(ImageFilter.GaussianBlur(max(2, size * 0.09)))
        out.alpha_composite(sh, (0, max(1, int(size * 0.03))))
    out.alpha_composite(layer)
    if blur > 0.5:
        out = out.filter(ImageFilter.GaussianBlur(blur))
    if alpha < 1:
        out.putalpha(out.getchannel("A").point(lambda v: int(v * alpha)))
    return out


def render_sequence(t: Title, W: int, H: int, fps: float, out_dir: Path) -> tuple[float, int]:
    """PNG-Folge des Titel-Fensters → (Startzeit, Anzahl Bilder). Leere Bilder werden transparent geschrieben."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("t_*.png"):
        old.unlink()
    n = int(round(t.duration * fps)) + 1
    blank = None
    for k in range(n):
        im = render_frame(t, W, H, t.start + k / fps)
        if im is None:
            blank = blank or Image.new("RGBA", (W, H), (0, 0, 0, 0))
            im = blank
        im.save(out_dir / f"t_{k:05d}.png", compress_level=1)
    return t.start, n
