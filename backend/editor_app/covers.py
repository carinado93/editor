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

# Thumbnail-Farbwelten: Carina wählt Rosa (wie bisher), Lila oder ihr Salbei-Grün
THUMB_THEMES = {
    "rosa": {"key": (201, 80, 106), "wash": (236, 178, 188), "band": (233, 160, 175), "pill": (122, 46, 51),
             "bg": ((249, 241, 236), (246, 231, 228)), "line": (205, 130, 145), "label": "Pink"},
    "lila": {"key": (100, 68, 165), "wash": (200, 184, 226), "band": (188, 168, 222), "pill": (72, 48, 120),
             "bg": ((248, 245, 251), (237, 231, 245)), "line": (150, 125, 195), "label": "Lilac"},
    "gruen": {"key": (109, 125, 81), "wash": (196, 207, 170), "band": (172, 188, 140), "pill": (84, 97, 60),
              "bg": ((248, 247, 240), (237, 240, 227)), "line": (139, 154, 107), "label": "Green"},
}


def _bezier(p0, p1, p2, n=40):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in (i / n for i in range(n + 1))]


def _leaf(d, cx, cy, length, angle, color, width):
    """Blatt als Umriss (Mandelform) mit Mittelrippe."""
    import math
    ca, sa = math.cos(angle), math.sin(angle)
    pts_a, pts_b = [], []
    for i in range(21):
        t = i / 20
        x = t * length
        y = math.sin(math.pi * t) * length * 0.22
        pts_a.append((cx + x * ca - y * sa, cy + x * sa + y * ca))
        pts_b.append((cx + x * ca + y * sa, cy + x * sa - y * ca))
    d.line(pts_a + pts_b[::-1] + [pts_a[0]], fill=color, width=width, joint="curve")
    d.line([(cx, cy), (cx + length * 0.8 * ca, cy + length * 0.8 * sa)], fill=color, width=max(1, width - 1))


def _sprig(d, p0, p1, p2, color, width, leaf_len, seed):
    """Zweig: geschwungener Stiel mit Blättern abwechselnd links/rechts."""
    import math
    rnd = random.Random(seed)
    pts = _bezier(p0, p1, p2)
    d.line(pts, fill=color, width=width, joint="curve")
    for k in range(4, len(pts) - 1, 5):
        (x0, y0), (x1, y1) = pts[k - 1], pts[k]
        ang = math.atan2(y1 - y0, x1 - x0)
        side = 1 if (k // 5) % 2 else -1
        _leaf(d, x1, y1, leaf_len * rnd.uniform(0.75, 1.1), ang + side * rnd.uniform(0.6, 0.9), color, width)
    _leaf(d, *pts[-1], leaf_len * 0.9, math.atan2(pts[-1][1] - pts[-2][1], pts[-1][0] - pts[-2][0]), color, width)


def _lotus(d, cx, cy, size, color, width):
    """Lotusblüte als Linienzeichnung."""
    import math
    for ang, ln in ((-90, 1.0), (-62, 0.9), (-118, 0.9), (-35, 0.72), (-145, 0.72)):
        a = math.radians(ang)
        _leaf(d, cx, cy, size * ln, a, color, width)
    d.arc((cx - size * 0.7, cy - size * 0.25, cx + size * 0.7, cy + size * 0.25), 0, 180, fill=color, width=width)


def botanical(size: tuple[int, int], color, seed: int = 5, alpha: int = 120, layout: str = "left") -> Image.Image:
    """Feine Pflanzen-Zeichnungen im Hintergrund (wie in Carinas Thumbnails): Zweige in den Ecken, kleiner Lotus.
    Doppelt so groß gezeichnet und verkleinert → weiche Linien."""
    W, H = size
    S = 2
    layer = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    c = (*color, alpha)
    w = 3 * S
    # oben links: Zweig, der von der Ecke nach innen schwingt
    _sprig(d, (-20 * S, 210 * S), (60 * S, 120 * S), (190 * S, 40 * S), c, w, 46 * S, seed)
    _sprig(d, (-10 * S, 120 * S), (40 * S, 60 * S), (120 * S, -10 * S), c, w, 34 * S, seed + 1)
    # unten links: kleiner Zweig + Lotus
    _sprig(d, (-10 * S, H * S - 40 * S), (50 * S, H * S - 120 * S), (40 * S, H * S - 230 * S), c, w, 36 * S, seed + 2)
    lx = (W * 0.43 if layout == "left" else W * 0.12) * S
    _lotus(d, lx, H * S - 70 * S, 42 * S, c, w)
    # ein paar Pünktchen
    rnd = random.Random(seed)
    for _ in range(9):
        x, y = rnd.uniform(0.05, 0.45) * W * S, rnd.uniform(0.04, 0.96) * H * S
        r = rnd.uniform(2, 4) * S
        d.ellipse((x - r, y - r, x + r, y + r), fill=(*color, alpha // 2))
    return layer.resize((W, H), Image.LANCZOS)


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
                    pill: str = "", theme: str = "rosa") -> Image.Image:
    W, H = 1280, 720
    th = THUMB_THEMES.get(theme, THUMB_THEMES["rosa"])
    canvas = soft_background((W, H), *th["bg"])
    # Aquarell nur am Rand: Ecke oben links + Pinselstrich ganz unten (nie hinter dem Text), feine Pflanzen-Linien
    for layer in (corner_wash((W, H), th["wash"]), brush_band((W, H), 0.985, 0.07, th["band"]),
                  botanical((W, H), th["line"], alpha=95)):
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
        d.text((left, y), ln, font=kf if key else nf, fill=th["key"] if key else BRAUN_DUNKEL)
        y += h
    if pill:
        pf = font("Poppins-Bold.ttf", 32)
        label = pill.upper()
        while d.textlength(label, font=pf) > max_w - 48 and pf.size > 18:
            pf = font("Poppins-Bold.ttf", pf.size - 2)
        tw = d.textlength(label, font=pf)
        py = min(H - 100, y + 18)
        d.rounded_rectangle((left - 4, py, left - 4 + tw + 48, py + pf.size + 30), radius=14, fill=th["pill"])
        d.text((left + 20, py + 13), label, font=pf, fill=(255, 255, 255))
    return canvas


# ---------- YouTube C: "Mitte" – Carina freigestellt in der Mitte, schräge Text-Balken davor ----------

CENTER_DARK = {"rosa": (92, 32, 44), "lila": (46, 30, 82), "gruen": (52, 62, 36)}
CENTER_ACCENT = {"rosa": (255, 196, 208), "lila": (226, 214, 250), "gruen": (222, 236, 170)}


def _tint(img: Image.Image, color, amount: float = 0.55) -> Image.Image:
    """Farbstimmung wie im Beispiel (ganzes Bild in einer Farbe): Graustufen → Duoton in Carinas Farbe."""
    g = ImageOps.grayscale(img)
    dark = tuple(int(c * 0.25) for c in color)
    light = tuple(min(255, int(c + (255 - c) * 0.7)) for c in color)
    duo = ImageOps.colorize(g, dark, light).convert("RGB")
    return Image.blend(img.convert("RGB"), duo, amount)


def _text_groups(text: str) -> list[tuple[str, bool]]:
    """"I can't *anymore*" → höchstens 3 Balken in Lese-Reihenfolge (links, Mitte, rechts); *Wort* wird groß."""
    segs = parse_marked(text)
    if any(k for _, k in segs):
        i = next(n for n, (_, k) in enumerate(segs) if k)
        before = " ".join(t.strip() for t, _ in segs[:i]).strip()
        after = " ".join(t.strip() for t, _ in segs[i + 1:]).strip()
        return [g for g in ((before, False), (segs[i][0].strip(), True), (after, False)) if g[0]]
    words = text.replace("*", "").split()
    if len(words) <= 2:
        return [(" ".join(words), False)] if words else []
    n = 3 if len(words) >= 3 else 2
    cuts = [round(len(words) * k / n) for k in range(n + 1)]
    return [(" ".join(words[cuts[k]:cuts[k + 1]]), False) for k in range(n)]


def _bar(text: str, fnt, fg, bg, pad: int, angle: float) -> Image.Image:
    tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    box = tmp.textbbox((0, 0), text, font=fnt)
    w, h = box[2] - box[0] + 2 * pad, box[3] - box[1] + int(pad * 1.2)
    im = Image.new("RGBA", (w, h), (*bg, 245))
    ImageDraw.Draw(im).text((pad - box[0], int(pad * 0.6) - box[1]), text, font=fnt, fill=fg)
    return im.rotate(angle, resample=Image.BICUBIC, expand=True)


def youtube_center(photo: Image.Image, face, text: str, theme: str = "lila",
                   mask: Image.Image | None = None) -> Image.Image:
    W, H = 1280, 720
    th = THUMB_THEMES.get(theme, THUMB_THEMES["lila"])
    dark, accent = CENTER_DARK.get(theme, CENTER_DARK["lila"]), CENTER_ACCENT.get(theme, CENTER_ACCENT["lila"])
    fx = ((face[0] + face[2]) / 2) if face else 0.5
    fy = ((face[1] + face[3]) / 2) if face else 0.35
    # Bild so zuschneiden, dass Carina in der Mitte steht (Gesicht im oberen Drittel)
    scale = max(W / photo.width, H / photo.height) * 1.05
    big = photo.convert("RGB").resize((round(photo.width * scale), round(photo.height * scale)), Image.LANCZOS)
    x = round(fx * big.width - W / 2)
    y = min(max(0, round(fy * big.height - H * 0.33)), big.height - H)
    shift = 0
    if x < 0 or x > big.width - W:  # Gesicht zu weit am Rand: Rest mit verschwommenem Hintergrund füllen
        shift = -x if x < 0 else (big.width - W) - x
        x = min(max(0, x), big.width - W)
    sharp = big.crop((x, y, x + W, y + H))
    m = (mask.convert("L").resize(big.size).crop((x, y, x + W, y + H)) if mask is not None else None)
    if shift:
        sharp = ImageOps.expand(sharp, (max(0, shift), 0, max(0, -shift), 0)).crop(
            (max(0, -shift), 0, max(0, -shift) + W, H)) if False else sharp.transform(
            (W, H), Image.AFFINE, (1, 0, -shift, 0, 1, 0), fillcolor=(0, 0, 0))
        if m is not None:
            m = m.transform((W, H), Image.AFFINE, (1, 0, -shift, 0, 1, 0), fillcolor=0)
    # Hintergrund: dasselbe Bild weich und in Carinas Farbe getönt + ihre Pflanzen-Linien
    bg = _tint(cover_fit(photo, W, H, (fx, fy)).filter(ImageFilter.GaussianBlur(14)), th["key"], 0.75)
    bg = Image.blend(bg, Image.new("RGB", (W, H), th["key"]), 0.18)
    deco = botanical((W, H), (255, 255, 255), seed=11, alpha=70, layout="corner")
    bg.paste(deco, (0, 0), deco)
    deco2 = botanical((W, H), (255, 255, 255), seed=4, alpha=55, layout="corner").transpose(Image.FLIP_LEFT_RIGHT)
    bg.paste(deco2, (0, 0), deco2)
    canvas = bg.copy()
    person = _tint(sharp, th["key"], 0.18)  # Carina nur leicht in der Farbstimmung, Haut bleibt natürlich
    if m is not None:
        canvas.paste(person, (0, 0), m.filter(ImageFilter.GaussianBlur(1.5)))
    else:  # ohne Freistellung: weiches Oval um sie herum
        oval = Image.new("L", (W, H), 0)
        ImageDraw.Draw(oval).ellipse((W * 0.27, -H * 0.1, W * 0.73, H * 1.3), fill=255)
        canvas.paste(person, (0, 0), oval.filter(ImageFilter.GaussianBlur(40)))
    # schräge Text-Balken: links, groß in der Mitte (vor ihr), rechts – versetzt wie im Beispiel
    groups = _text_groups(text) or [("YOUR TEXT", False)]
    n = len(groups)
    has_key = any(k for _, k in groups)
    slots = {1: [(0.5, 0.74)], 2: [(0.3, 0.64), (0.64, 0.78)], 3: [(0.22, 0.62), (0.52, 0.78), (0.8, 0.58)]}[n]
    angles = [-4, 3, -3, 2]
    for k, ((g, key), (cx, cy)) in enumerate(zip(groups, slots)):
        big_one = key or (not has_key and k == n // 2)
        size = 92 if big_one else 64
        fnt = font("Poppins-ExtraBold.ttf", size)
        while fnt.getlength(g) > W * (0.5 if big_one else 0.34) and fnt.size > 30:
            fnt = font("Poppins-ExtraBold.ttf", fnt.size - 4)
        bar = _bar(g, fnt, accent if big_one else (255, 255, 255), dark, int(fnt.size * 0.3), angles[k % 4])
        px = int(min(max(10, cx * W - bar.width / 2), W - bar.width - 10))
        py = int(min(max(10, cy * H - bar.height / 2), H - bar.height - 10))
        canvas.paste(bar, (px, py), bar)
    # kleine Signatur unten links
    d = ImageDraw.Draw(canvas)
    d.text((40, H - 62), "CARINA DORCA", font=font("CormorantGaramond-SemiBold.ttf", 34), fill=(255, 255, 255))
    return canvas


# ---------- YouTube B: "Meditation / Entspannung" ----------

def youtube_meditation(photo: Image.Image, face, title: str, subtitle: str = "", top_pill: str = "",
                       top_label: str = "", theme: str = "rosa") -> Image.Image:
    W, H = 1280, 720
    th = THUMB_THEMES.get(theme, THUMB_THEMES["rosa"])
    fx = ((face[0] + face[2]) / 2) if face else 0.6
    canvas = cover_fit(photo, W, H, (min(0.85, fx + 0.1), 0.45)).convert("RGB")
    veil = Image.new("RGB", (W, H), CREME_ROSA)
    grad = Image.linear_gradient("L").rotate(90, expand=True).resize((W, H))
    grad = ImageOps.invert(grad).point(lambda v: min(245, int(v * 1.35)))
    canvas.paste(veil, (0, 0), grad)
    for layer in (corner_wash((W, H), th["wash"]), botanical((W, H), th["line"], seed=9, alpha=110, layout="corner")):
        canvas.paste(layer, (0, 0), layer)
    d = ImageDraw.Draw(canvas)
    x, y = 64, 70
    if top_pill:
        pf = font("Poppins-SemiBold.ttf", 22)
        tw = d.textlength(top_pill.upper(), font=pf)
        d.rounded_rectangle((x, y, x + tw + 36, y + 40), radius=20, fill=th["band"])
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
