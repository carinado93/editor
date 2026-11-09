"""Thumbnails (YouTube 1280×720) und Reel-Cover (1080×1920) im Stil von Carinas bisherigen Designs.

Grundlage: docs/THUMBNAIL_STIL.md. Bilder sind immer echte Standbilder aus ihrem Video, nie KI-generiert.
Text-Hervorhebung: Wörter in *Sternchen* werden zum farbigen Schlüsselwort.
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from .config import ROOT

FONTS = ROOT / "assets" / "fonts"

BRAUN_DUNKEL = (59, 36, 32)
ROSA = (201, 80, 106)
WEINROT = (122, 46, 51)
CREME_ROSA = (248, 238, 232)
CREME = (244, 238, 228)
LILA = (106, 76, 156)
OLIV = (107, 111, 58)

# Reel-Cover: Farbschleier + Textfarbe (Rotation lila → hell → oliv)
COVER_SCHEMES = {
    "lila": {"veil": (106, 76, 156), "alpha": 0.55, "text": (250, 246, 240)},
    "hell": {"veil": (246, 241, 233), "alpha": 0.62, "text": (106, 76, 156)},
    "oliv": {"veil": (107, 111, 58), "alpha": 0.50, "text": (250, 246, 240)},
}
ROTATION = ["lila", "hell", "oliv"]


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


# ---------- Cover-Rotation (gespeichert auf Carinas PC) ----------

def _state_file() -> Path:
    return ROOT / "daten" / "einstellungen.json"


def _state() -> dict:
    try:
        return json.loads(_state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def next_cover_color() -> str:
    return _state().get("cover_next", "hell")  # zuletzt war lila (Stand 8.11.)


def advance_cover_color(used: str) -> str:
    nxt = ROTATION[(ROTATION.index(used) + 1) % len(ROTATION)] if used in ROTATION else next_cover_color()
    st = _state()
    st["cover_next"] = nxt
    _state_file().parent.mkdir(parents=True, exist_ok=True)
    _state_file().write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    return nxt


# ---------- Hilfen ----------

def cover_fit(img: Image.Image, w: int, h: int, focus: tuple[float, float] = (0.5, 0.4)) -> Image.Image:
    """Bild so zuschneiden, dass es w×h füllt, mit `focus` (0..1) möglichst mittig."""
    scale = max(w / img.width, h / img.height)
    im = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    x = min(max(0, round(focus[0] * im.width - w / 2)), im.width - w)
    y = min(max(0, round(focus[1] * im.height - h / 2)), im.height - h)
    return im.crop((x, y, x + w, y + h))


def parse_marked(text: str) -> list[tuple[str, bool]]:
    """"REST DIDN'T FIX MY *BURNOUT*" → [("REST DIDN'T FIX MY ", False), ("BURNOUT", True)]."""
    parts = re.split(r"(\*[^*]+\*)", text)
    out: list[tuple[str, bool]] = []
    for p in parts:
        if not p:
            continue
        key = p.startswith("*")
        seg = p.strip("*")
        # Satzzeichen direkt nach dem Schlüsselwort ("*ANXIETY*?") gehören zu ihm, nicht in eine neue Zeile
        m = re.match(r"^([?!.,:;…]+)(.*)$", seg)
        if not key and m and out and out[-1][1]:
            out[-1] = (out[-1][0] + m.group(1), True)
            seg = m.group(2)
        if seg.strip():
            out.append((seg, key))
    return out


def wrap(words: list[str], fnt: ImageFont.FreeTypeFont, max_w: int, draw: ImageDraw.ImageDraw) -> list[str]:
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=fnt) <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def watercolor(size: tuple[int, int], blobs: list[tuple[float, float, float, tuple[int, int, int], int]], blur: int = 40,
               seed: int = 7) -> Image.Image:
    """Weiche Aquarell-Flecken (RGBA): (x, y, Radius relativ, Farbe, Deckkraft 0..255)."""
    rnd = random.Random(seed)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    W, H = size
    for cx, cy, r, col, a in blobs:
        for _ in range(6):
            rr = r * W * rnd.uniform(0.55, 1.0)
            ox, oy = rnd.uniform(-0.4, 0.4) * rr, rnd.uniform(-0.25, 0.25) * rr
            d.ellipse((cx * W + ox - rr, cy * H + oy - rr * 0.6, cx * W + ox + rr, cy * H + oy + rr * 0.6),
                      fill=(*col, int(a * rnd.uniform(0.35, 0.7))))
    return layer.filter(ImageFilter.GaussianBlur(blur))


def soft_background(size: tuple[int, int], top=(249, 241, 236), bottom=(246, 231, 228)) -> Image.Image:
    """Saubere helle Fläche mit leichtem Verlauf (kein Fleck hinter dem Text)."""
    W, H = size
    grad = Image.linear_gradient("L").resize((W, H))
    a, b = Image.new("RGB", size, top), Image.new("RGB", size, bottom)
    return Image.composite(b, a, grad)


def brush_band(size: tuple[int, int], y: float, height: float, color=(233, 160, 175), x0: float = -0.05,
               x1: float = 0.62, seed: int = 3) -> Image.Image:
    """Aquarell-Pinselstrich (waagrecht) mit unruhigem Rand, wie in Carinas Thumbnails."""
    rnd = random.Random(seed)
    W, H = size
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    for pass_, alpha in enumerate((70, 55, 45)):
        d = ImageDraw.Draw(layer)
        pts_top, pts_bot = [], []
        steps = 40
        for i in range(steps + 1):
            x = (x0 + (x1 - x0) * i / steps) * W
            taper = min(1.0, i / 6, (steps - i) / 6)  # Enden laufen dünn aus
            h = height * H * (0.55 + 0.45 * taper) * rnd.uniform(0.85, 1.1)
            yc = y * H + rnd.uniform(-0.04, 0.04) * height * H + pass_ * 3
            pts_top.append((x, yc - h / 2))
            pts_bot.append((x, yc + h / 2))
        d.polygon(pts_top + pts_bot[::-1], fill=(*color, alpha))
    return layer.filter(ImageFilter.GaussianBlur(5))


def corner_wash(size: tuple[int, int], color=(236, 178, 188)) -> Image.Image:
    W, H = size
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse((-0.10 * W, -0.22 * H, 0.10 * W, 0.16 * H), fill=(*color, 120))
    d.ellipse((-0.06 * W, -0.10 * H, 0.16 * W, 0.08 * H), fill=(*color, 70))
    return layer.filter(ImageFilter.GaussianBlur(14))


def fit_text(d: ImageDraw.ImageDraw, segs: list[tuple[str, bool]], max_w: int, max_h: int,
             font_name: str = "Poppins-ExtraBold.ttf", start: int = 124, key_scale: float = 1.15):
    """Größte Schrift finden, bei der alle Zeilen in max_w × max_h passen (nie abgeschnitten)."""
    for size in range(start, 30, -4):
        nf, kf = font(font_name, size), font(font_name, round(size * key_scale))
        lines: list[tuple[str, bool]] = []
        for seg, key in segs:
            for ln in wrap(seg.split(), kf if key else nf, max_w, d):
                lines.append((ln, key))
        widths_ok = all(d.textlength(ln, font=kf if k else nf) <= max_w for ln, k in lines)
        heights = [round((kf if k else nf).size * 1.02) for _, k in lines]
        if widths_ok and sum(heights) <= max_h and len(lines) <= 5:
            return lines, heights, nf, kf
    return lines, heights, nf, kf


def youtube_talking(photo: Image.Image, face: tuple[float, float, float, float] | None, text: str,
                    pill: str = "") -> Image.Image:
    W, H = 1280, 720
    canvas = soft_background((W, H))
    # Aquarell nur am Rand: Ecke oben links + Pinselstrich ganz unten (nie hinter dem Text)
    for layer in (corner_wash((W, H)), brush_band((W, H), 0.985, 0.07)):
        canvas.paste(layer, (0, 0), layer)
    fx = ((face[0] + face[2]) / 2) if face else 0.5
    fy = ((face[1] + face[3]) / 2) if face else 0.35
    # Foto rechts in der rechten Hälfte, Gesicht im oberen Drittel, scharf
    region_w = round(W * 0.50)
    ph = cover_fit(photo, region_w, H, (fx, max(0.3, fy - 0.02)))
    fade = 90
    mask = Image.new("L", ph.size, 255)
    md = ImageDraw.Draw(mask)
    for i in range(fade):
        md.line((i, 0, i, H), fill=int(255 * (i / fade) ** 1.6))
    canvas.paste(ph, (W - region_w, 0), mask)
    d = ImageDraw.Draw(canvas)
    # Text: nur in der linken Hälfte, nie im Foto, nie abgeschnitten
    left, max_w = 60, round(W * 0.50) - 60 - 30
    top, bottom = 60, H - (150 if pill else 70)
    lines, heights, nf, kf = fit_text(d, parse_marked(text.upper()), max_w, bottom - top)
    y = top + max(0, (bottom - top - sum(heights)) / 2)
    for (ln, key), h in zip(lines, heights):
        d.text((left, y), ln, font=kf if key else nf, fill=ROSA if key else BRAUN_DUNKEL)
        y += h
    if pill:
        pf = font("Poppins-Bold.ttf", 32)
        label = pill.upper()
        while d.textlength(label, font=pf) > max_w - 48 and pf.size > 18:
            pf = font("Poppins-Bold.ttf", pf.size - 2)
        tw = d.textlength(label, font=pf)
        py = min(H - 100, y + 18)
        d.rounded_rectangle((left - 4, py, left - 4 + tw + 48, py + pf.size + 30), radius=14, fill=WEINROT)
        d.text((left + 20, py + 13), label, font=pf, fill=(255, 255, 255))
    return canvas


# ---------- YouTube B: "Meditation / Entspannung" ----------

def youtube_meditation(photo: Image.Image, face, title: str, subtitle: str = "", top_pill: str = "",
                       top_label: str = "") -> Image.Image:
    W, H = 1280, 720
    fx = ((face[0] + face[2]) / 2) if face else 0.6
    canvas = cover_fit(photo, W, H, (min(0.85, fx + 0.1), 0.45)).convert("RGB")
    veil = Image.new("RGB", (W, H), CREME_ROSA)
    grad = Image.linear_gradient("L").rotate(90, expand=True).resize((W, H))
    grad = ImageOps.invert(grad).point(lambda v: min(245, int(v * 1.35)))
    canvas.paste(veil, (0, 0), grad)
    wc = corner_wash((W, H))
    canvas.paste(wc, (0, 0), wc)
    d = ImageDraw.Draw(canvas)
    x, y = 64, 70
    if top_pill:
        pf = font("Poppins-SemiBold.ttf", 22)
        tw = d.textlength(top_pill.upper(), font=pf)
        d.rounded_rectangle((x, y, x + tw + 36, y + 40), radius=20, fill=(232, 160, 170))
        d.text((x + 18, y + 7), top_pill.upper(), font=pf, fill=(255, 255, 255))
        if top_label:
            d.text((x + tw + 56, y + 9), "  ".join(top_label.upper()), font=font("Jost.ttf", 18), fill=BRAUN_DUNKEL)
        y += 80
    tf = font("CormorantGaramond-SemiBold.ttf", 96)
    for ln in wrap(title.split(), tf, 620, d)[:3]:
        d.text((x, y), ln, font=tf, fill=BRAUN_DUNKEL)
        y += 92
    if subtitle:
        d.text((x + 6, y + 14), subtitle, font=font("CormorantGaramond-SemiBoldItalic.ttf", 44), fill=(120, 90, 80))
        y += 70
    fy = H - 120
    d.line((x, fy, x + 330, fy), fill=(150, 110, 100), width=2)
    d.text((x, fy + 16), "C A R I N A   D O R C A", font=font("CormorantGaramond-SemiBold.ttf", 30), fill=BRAUN_DUNKEL)
    d.text((x, fy + 58), "Relaxation, Stress & Burnout Coach", font=font("Jost.ttf", 20), fill=(110, 90, 80))
    return canvas


# ---------- Reel-Cover ----------

def reel_cover(photo: Image.Image, face, text: str, color: str) -> Image.Image:
    W, H = 1080, 1920
    sch = COVER_SCHEMES.get(color, COVER_SCHEMES["hell"])
    fx = ((face[0] + face[2]) / 2) if face else 0.5
    fy = ((face[1] + face[3]) / 2) if face else 0.4
    canvas = cover_fit(photo, W, H, (fx, fy)).convert("RGB")
    veil = Image.new("RGB", (W, H), sch["veil"])
    canvas = Image.blend(canvas, veil, sch["alpha"])
    d = ImageDraw.Draw(canvas)
    # Im Profil-Raster zeigt Instagram nur die Mitte (3:4) → Text zwischen y≈300 und y≈1250 halten
    tf = font("CormorantGaramond-SemiBold.ttf", 150)
    lines = wrap(text.split(), tf, 860, d)
    while (len(lines) > 4 or any(d.textlength(ln, font=tf) > 900 for ln in lines)) and tf.size > 70:
        tf = font("CormorantGaramond-SemiBold.ttf", tf.size - 8)
        lines = wrap(text.split(), tf, 860, d)
    lh = tf.size * 1.12
    block = lh * len(lines)
    face_top = (face[1] if face else 0.3)
    # Text über dem Gesicht, wenn Platz ist; sonst unter dem Kinn – aber noch im sichtbaren Profil-Raster (bis y≈1650)
    if not face or face_top * H > 300 + block + 40:
        y = 300
    else:
        chin = face[3] * H + 0.07 * H
        y = min(1650 - block, chin)
    for ln in lines:
        w = d.textlength(ln, font=tf)
        d.text(((W - w) / 2, y), ln, font=tf, fill=sch["text"])
        y += lh
    return canvas


def default_thumb_text(title: str, key_words: set[str]) -> str:
    """Aus einem YouTube-Titel einen kurzen Thumbnail-Text machen (max. 5 Wörter, ein Schlüsselwort markiert)."""
    words = re.sub(r"[|–—:]+.*$", "", title).split()[:5] or title.split()[:5]
    if not words:
        return ""
    idx = next((i for i, w in enumerate(words) if re.sub(r"\W", "", w).lower() in key_words), None)
    if idx is None:
        idx = max(range(len(words)), key=lambda i: len(re.sub(r"\W", "", words[i])))
    words[idx] = f"*{words[idx]}*"
    return " ".join(words)
