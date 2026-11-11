"""Effekte im Stil von Carinas Inspirations-Reel, in ihren Farben (Instagram-Lila, Website-Salbei/Gold).

Jeder Effekt wird Bild für Bild gezeichnet (Pillow), über das fertige Video gelegt oder als eigene Szene gezeigt.

Gruppe A – Kästen (Szene auf Lavendel oder neben ihr):
  steps     "So geht's": Schritt-Kästen erscheinen nacheinander, verbunden durch eine Linie
  cards     weiße Karten mit Titel poppen um die Mitte
  tags      kleine schräge Etiketten fliegen herein
  scores    Bewertungs-Karten mit Balken ("6/10")
  headline  Treppen-Überschrift wie in Carinas Post ("what if / i would quit / my job?")
  checklist Checkliste mit Haken
  endcard   Schluss-Karte mit Aufforderung ("Kommentiere RUHE")
Gruppe B – Text über dem Video:
  bigwords  große Wort-für-Wort-Untertitel, Schlüsselwörter lila-kursiv
  pill      kleine Pille oben ("+ Atemübung")
Gruppe C – Carina freigestellt (Personen-Erkennung):
  behind    großes Wort HINTER ihr
  glow      leuchtender Umriss
  background neuer Hintergrund (Lavendel mit Muster)
  card      Video als Karte auf Lavendel, Überschrift darüber (wie ihr Post)
"""
from __future__ import annotations

import functools
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import ROOT

FONTS = ROOT / "assets" / "fonts"

# Carinas Farben
LILA = (100, 68, 165)        # Instagram-Text
LILA_TIEF = (58, 40, 98)
LAVENDEL = (220, 212, 236)   # Instagram-Hintergrund
LAVENDEL_HELL = (238, 233, 246)
PLUM = (181, 150, 201)       # Website
SALBEI = (139, 154, 107)
SALBEI_TIEF = (109, 125, 81)
GOLD = (201, 165, 104)
CREME = (244, 236, 218)
PAPIER = (251, 248, 240)
TINTE = (63, 58, 44)
WEISS = (255, 255, 255)

TYPES = {
    # key: (Gruppe, Name für die Oberfläche, Platzierungen)
    "steps": ("A", "Step boxes", ("scene", "side")),
    "cards": ("A", "Cards", ("scene", "side")),
    "tags": ("A", "Flying tags", ("scene", "side")),
    "scores": ("A", "Score cards", ("scene", "side")),
    "headline": ("A", "Staircase headline", ("scene", "side")),
    "checklist": ("A", "Checklist", ("scene", "side")),
    "endcard": ("A", "End card", ("scene",)),
    "bigwords": ("B", "Big word captions", ("side",)),
    "pill": ("B", "Pill label", ("side",)),
    "behind": ("C", "Text behind you", ("side",)),
    "glow": ("C", "Glow outline", ("side",)),
    "background": ("C", "New background", ("side",)),
    "card": ("C", "Video as card", ("scene",)),
    "poof": ("C", "Poof (disappear / appear)", ("side",)),
}
NEEDS_MASK = {"behind", "glow", "background"}


@functools.cache
def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    files = {"head": "Poppins-ExtraBold.ttf", "bold": "Poppins-Bold.ttf", "semi": "Poppins-SemiBold.ttf",
             "serif": "CormorantGaramond-SemiBold.ttf", "serif_i": "CormorantGaramond-SemiBoldItalic.ttf",
             "hand": "Caveat.ttf", "jost": "Jost.ttf", "black": "Poppins-Black.ttf"}
    return ImageFont.truetype(str(FONTS / files[name]), max(8, size))


# ---------------------------------------------------------------- Bewegung

def ease_back(x: float) -> float:
    """Schnell rein, kurz über das Ziel hinaus, zurück (Pop)."""
    x = min(1.0, max(0.0, x))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ease_out(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def appear(t: float, t0: float, dur: float, end: float, pop: float = 0.32) -> tuple[float, float]:
    """(Größe 0..1+, Deckkraft 0..1) eines Elements, das bei t0 erscheint und zum Ende ausblendet."""
    if t < t0:
        return 0.0, 0.0
    k = (t - t0) / pop
    out = min(1.0, max(0.0, (end - t) / 0.25))
    return ease_back(k), min(1.0, k * 2) * out


def item_times(n: int, given: list[float] | None, dur: float, first: float = 0.15) -> list[float]:
    """Wann die einzelnen Punkte erscheinen (relativ): wie gesagt, sonst gleichmäßig nacheinander."""
    if given and len(given) >= n:
        return [max(0.0, min(dur - 0.6, g)) for g in given[:n]]
    step = min(0.6, max(0.25, (dur * 0.5) / max(1, n)))
    return [first + k * step for k in range(n)]


# ---------------------------------------------------------------- Bausteine (einmal gezeichnet, dann bewegt)

def _shadow(sprite: Image.Image, radius: int, offset: int, alpha: int = 60) -> Image.Image:
    pad = radius * 3
    w, h = sprite.size
    sh = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    a = sprite.getchannel("A").point(lambda v: v * alpha // 255)
    sh.paste((LILA_TIEF[0], LILA_TIEF[1], LILA_TIEF[2], 255), (pad, pad + offset), a)
    sh = sh.filter(ImageFilter.GaussianBlur(radius))
    sh.alpha_composite(sprite, (pad, pad))
    return sh


def text_size(text: str, f: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = f.getbbox(text)
    return box[2] - box[0], box[3] - box[1]


def rich_line(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, f: ImageFont.FreeTypeFont,
              f_acc: ImageFont.FreeTypeFont, color, acc_color, anchor_left: bool = True) -> int:
    """Zeichnet eine Zeile; *Wort* in Sternchen in der Akzent-Schrift/-Farbe. Gibt die Breite zurück."""
    parts = [p for p in text.replace("**", "*").split("*")]
    x, y = xy
    for k, p in enumerate(parts):
        if not p:
            continue
        acc = k % 2 == 1
        ff = f_acc if acc else f
        draw.text((x, y), p, font=ff, fill=acc_color if acc else color, anchor="ls")
        x += int(ff.getlength(p))
    return x - xy[0]


def rich_width(text: str, f, f_acc) -> int:
    return sum(int((f_acc if k % 2 else f).getlength(p)) for k, p in enumerate(text.replace("**", "*").split("*")))


def card_sprite(w: int, h: int, u: float, fill=WEISS, radius: float = 22, border=None) -> Image.Image:
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=int(radius * u), fill=fill,
                        outline=border, width=max(2, int(3 * u)) if border else 0)
    return im


def wrap(text: str, f, max_w: int) -> list[str]:
    lines, cur = [], ""
    for wd in text.split():
        trial = f"{cur} {wd}".strip()
        if cur and f.getlength(trial.replace("*", "")) > max_w:
            lines.append(cur)
            cur = wd
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def paste_scaled(layer: Image.Image, sprite: Image.Image, center: tuple[float, float], scale: float, alpha: float,
                 rot: float = 0.0) -> None:
    if scale <= 0.02 or alpha <= 0.01:
        return
    sp = sprite
    if abs(scale - 1) > 0.01:
        sp = sp.resize((max(1, int(sp.width * scale)), max(1, int(sp.height * scale))), Image.BILINEAR)
    if rot:
        sp = sp.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 0.999:
        a = sp.getchannel("A").point(lambda v: int(v * alpha))
        sp = sp.copy()
        sp.putalpha(a)
    layer.alpha_composite(sp, (int(center[0] - sp.width / 2), int(center[1] - sp.height / 2)))


def lavender_bg(w: int, h: int) -> Image.Image:
    """Weicher Lavendel-Verlauf wie in Carinas Post."""
    top = np.array(LAVENDEL_HELL, dtype=np.float32)
    bot = np.array(LAVENDEL, dtype=np.float32)
    k = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    col = top * (1 - k) + bot * k
    arr = np.repeat(col[:, None, :], w, axis=1).astype(np.uint8)
    return Image.fromarray(arr.reshape(h, w, 3), "RGB").convert("RGBA")


@functools.cache
def pattern_bg(w: int, h: int) -> Image.Image:
    """Neuer Hintergrund: Lavendel mit kleinen Kreisen und Herzen in Lila/Salbei."""
    im = lavender_bg(w, h)
    d = ImageDraw.Draw(im)
    u = min(w, h) / 1080
    step = int(120 * u)
    r = int(14 * u)
    for row, y in enumerate(range(step // 2, h + step, step)):
        for col, x in enumerate(range((row % 2) * step // 2, w + step, step)):
            c = LILA if (row + col) % 3 else SALBEI
            d.ellipse((x - r, y - r, x + r, y + r), outline=c + (170,), width=max(2, int(4 * u)))
    return im


# ---------------------------------------------------------------- Effekt-Zeichner

class Ctx:
    """Was ein Effekt zum Zeichnen braucht."""

    def __init__(self, w: int, h: int, face_box: list[float] | None, words: list[dict] | None = None):
        self.w, self.h = w, h
        self.u = min(w, h) / 1080
        self.portrait = h > w
        self.face = face_box or [0.35, 0.12, 0.65, 0.5]
        self.words = words or []  # [{w, s, e}] in Zeit relativ zum Effekt-Beginn
        self.cache: dict = {}

    def region(self, place: str) -> tuple[int, int, int, int]:
        """Fläche, in der Kästen gezeichnet werden."""
        w, h = self.w, self.h
        if place == "scene":
            m = int(0.08 * w)
            return (m, int(0.14 * h), w - m, int(0.86 * h)) if self.portrait else (m, int(0.12 * h), w - m, int(0.9 * h))
        fx0, fy0, fx1, fy1 = self.face
        if self.portrait:  # unter dem Gesicht, über der Untertitel-Zone
            return int(0.07 * w), int(min(0.66, fy1 + 0.04) * h), int(0.93 * w), int(0.86 * h)
        if (fx0 + fx1) / 2 < 0.55:  # Gesicht links/mittig → rechts daneben
            return int(min(0.62, fx1 + 0.03) * w), int(0.12 * h), int(0.96 * w), int(0.88 * h)
        return int(0.04 * w), int(0.12 * h), int(max(0.38, fx0 - 0.03) * w), int(0.88 * h)


def _title(layer, ctx, region, text, t, t0, end, size=70, color=LILA, top=True) -> int:
    """Überschrift oben in der Fläche (Poppins ExtraBold, *Wort* als Serif-Kursiv in Gold). Gibt die Höhe zurück."""
    if not text:
        return 0
    x0, y0, x1, _ = region
    f = font("head", int(size * ctx.u))
    fa = font("serif_i", int(size * 1.15 * ctx.u))
    lines = wrap(text, f, x1 - x0)
    s, a = appear(t, t0, 0, end, pop=0.35)
    if a <= 0:
        return int(len(lines) * size * 1.15 * ctx.u)
    key = ("title", text, size, x1 - x0)
    if key not in ctx.cache:
        lh = int(size * 1.15 * ctx.u)
        im = Image.new("RGBA", (x1 - x0, lh * len(lines) + int(20 * ctx.u)), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for k, ln in enumerate(lines):
            wdt = rich_width(ln, f, fa)
            rich_line(d, ((x1 - x0 - wdt) // 2, int(lh * (k + 0.85))), ln, f, fa, color, GOLD)
        ctx.cache[key] = im
    im = ctx.cache[key]
    dy = int((1 - ease_out((t - t0) / 0.4)) * 30 * ctx.u)
    paste_scaled(layer, im, (x0 + im.width / 2, y0 + im.height / 2 + dy), 1.0, a)
    return im.height


def draw_steps(layer, ctx, it, t, d, place):
    """Schritt-Kästen untereinander, eine Linie wächst von Kasten zu Kasten."""
    reg = ctx.region(place)
    x0, y0, x1, y1 = reg
    th = _title(layer, ctx, reg, it.get("title", ""), t, 0, d, size=60 if place == "scene" else 46)
    items = it.get("items") or []
    n = max(1, len(items))
    times = item_times(n, it.get("times"), d, first=0.35)
    top = y0 + th + int(30 * ctx.u)
    avail = y1 - top
    box_h = min(int(150 * ctx.u), int(avail / n * 0.72))
    gap = (avail - box_h * n) / max(1, n)
    box_w = int((x1 - x0) * (0.82 if place == "scene" else 0.92))
    cx = (x0 + x1) / 2
    f = font("semi", int(min(46, box_h * 0.34 / ctx.u) * ctx.u))
    fn = font("head", int(min(52, box_h * 0.4 / ctx.u) * ctx.u))
    dr = ImageDraw.Draw(layer)
    for k, txt in enumerate(items):
        cy = top + k * (box_h + gap) + box_h / 2
        # Linie vom vorigen Kasten her wachsen lassen
        if k > 0:
            prog = ease_out((t - times[k] + 0.25) / 0.3)
            if prog > 0:
                ya = top + (k - 1) * (box_h + gap) + box_h
                dr.line((cx, ya, cx, ya + (gap) * prog), fill=LILA + (255,), width=max(3, int(5 * ctx.u)))
        key = ("step", k, txt, box_w, box_h)
        if key not in ctx.cache:
            sp = card_sprite(box_w, box_h, ctx.u, fill=WEISS, border=PLUM)
            sd = ImageDraw.Draw(sp)
            num = str(k + 1)
            r = int(box_h * 0.32)
            sd.ellipse((int(24 * ctx.u), box_h // 2 - r, int(24 * ctx.u) + 2 * r, box_h // 2 + r), fill=LILA)
            sd.text((int(24 * ctx.u) + r, box_h // 2), num, font=fn, fill=WEISS, anchor="mm")
            lines = wrap(txt, f, box_w - 2 * r - int(70 * ctx.u))[:2]
            lh = f.size * 1.15
            for j, ln in enumerate(lines):
                sd.text((int(24 * ctx.u) + 2 * r + int(26 * ctx.u), box_h / 2 + (j - (len(lines) - 1) / 2) * lh),
                        ln, font=f, fill=TINTE, anchor="lm")
            ctx.cache[key] = _shadow(sp, int(14 * ctx.u), int(8 * ctx.u))
        s, a = appear(t, times[k], 0, d)
        paste_scaled(layer, ctx.cache[key], (cx, cy), s, a)


def draw_cards(layer, ctx, it, t, d, place):
    """Weiße Karten (2–4) poppen nacheinander um die Mitte, in der Mitte ein lila Kreis."""
    reg = ctx.region(place)
    x0, y0, x1, y1 = reg
    th = _title(layer, ctx, reg, it.get("title", ""), t, 0, d, size=64 if place == "scene" else 46)
    items = (it.get("items") or [])[:4]
    n = max(1, len(items))
    times = item_times(n, it.get("times"), d, first=0.45)
    top = y0 + th + int(20 * ctx.u)
    cx, cy = (x0 + x1) / 2, (top + y1) / 2
    cw = int(min((x1 - x0) * 0.42, 330 * ctx.u))
    ch = int(cw * 0.95)
    dx, dy = cw * 0.62, ch * 0.62
    pos = {1: [(0, 0)], 2: [(-dx, 0), (dx, 0)], 3: [(-dx, -dy), (dx, -dy), (0, dy)],
           4: [(-dx, -dy), (dx, -dy), (-dx, dy), (dx, dy)]}[n]
    # Mitte: lila Kreis
    s, a = appear(t, 0.2, 0, d)
    key = ("hub",)
    if key not in ctx.cache:
        r = int(cw * 0.28)
        sp = Image.new("RGBA", (2 * r, 2 * r), (0, 0, 0, 0))
        ImageDraw.Draw(sp).rounded_rectangle((0, 0, 2 * r - 1, 2 * r - 1), radius=int(r * 0.45), fill=LILA)
        ImageDraw.Draw(sp).polygon([(r * 0.8, r * 0.6), (r * 0.8, r * 1.4), (r * 1.45, r)], fill=WEISS)
        ctx.cache[key] = _shadow(sp, int(12 * ctx.u), int(6 * ctx.u))
    if n > 1:
        paste_scaled(layer, ctx.cache[key], (cx, cy), s, a)
    f = font("head", int(cw * 0.13))
    fs = font("jost", int(cw * 0.085))
    for k, txt in enumerate(items):
        title, _, sub = txt.partition("|")
        key = ("card", k, txt, cw)
        if key not in ctx.cache:
            sp = card_sprite(cw, ch, ctx.u)
            sd = ImageDraw.Draw(sp)
            lines = wrap(title.strip(), f, int(cw * 0.84))[:3]
            lh = f.size * 1.12
            y = ch / 2 - (len(lines) - 1) * lh / 2 - (fs.size * 0.7 if sub else 0)
            for j, ln in enumerate(lines):
                sd.text((cw / 2, y + j * lh), ln, font=f, fill=LILA, anchor="mm")
            if sub.strip():
                sd.text((cw / 2, y + len(lines) * lh + fs.size * 0.3), sub.strip().upper(), font=fs, fill=SALBEI_TIEF,
                        anchor="mm")
            ctx.cache[key] = _shadow(sp, int(16 * ctx.u), int(10 * ctx.u))
        sc, al = appear(t, times[k], 0, d)
        px, py = pos[k]
        paste_scaled(layer, ctx.cache[key], (cx + px, cy + py), sc, al)


def draw_tags(layer, ctx, it, t, d, place):
    """Kleine Etiketten (Großbuchstaben, gesperrt) fliegen schräg herein und bleiben verstreut liegen."""
    reg = ctx.region(place)
    x0, y0, x1, y1 = reg
    th = _title(layer, ctx, reg, it.get("title", ""), t, 0, d, size=60 if place == "scene" else 44)
    items = (it.get("items") or [])[:6]
    n = max(1, len(items))
    times = item_times(n, it.get("times"), d, first=0.3)
    rnd = random.Random(it.get("id", "tags"))
    f = font("semi", int(30 * ctx.u))
    top = y0 + th + int(20 * ctx.u)
    rows = n
    for k, txt in enumerate(items):
        key = ("tag", k, txt)
        if key not in ctx.cache:
            label = " ".join(txt.upper())  # gesperrt wie im Vorbild
            tw, tht = text_size(label, f)
            pad = int(22 * ctx.u)
            sp = card_sprite(tw + 2 * pad + int(40 * ctx.u), tht + 2 * pad, ctx.u, radius=12)
            sd = ImageDraw.Draw(sp)
            c = [LILA, SALBEI, GOLD][k % 3]
            sd.ellipse((pad, sp.height / 2 - 9 * ctx.u, pad + 18 * ctx.u, sp.height / 2 + 9 * ctx.u), fill=c)
            sd.text((pad + int(36 * ctx.u), sp.height / 2), label, font=f, fill=TINTE, anchor="lm")
            ctx.cache[key] = (_shadow(sp, int(10 * ctx.u), int(6 * ctx.u)), rnd.uniform(-7, 7), rnd.uniform(-0.12, 0.12))
        sp, rot, jit = ctx.cache[key]
        row, colm = k, k % 2
        tx = x0 + (x1 - x0) * ((0.36 if colm == 0 else 0.64) + jit * 0.5)
        tx = min(max(tx, x0 + sp.width / 2), x1 - sp.width / 2)
        ty = top + (y1 - top) * ((row + 0.5) / rows)
        prog = ease_out((t - times[k]) / 0.45)
        if prog <= 0:
            continue
        # fliegt von der Seite herein
        start_x = -sp.width if colm == 0 else ctx.w + sp.width
        x = start_x + (tx - start_x) * prog
        out = min(1.0, max(0.0, (d - t) / 0.25))
        paste_scaled(layer, sp, (x, ty), 1.0, out, rot=rot * prog)


def draw_scores(layer, ctx, it, t, d, place):
    """Bewertungs-Karten: kleine Überschrift, Text, wachsender Balken in Segmenten, "6/10"."""
    reg = ctx.region(place)
    x0, y0, x1, y1 = reg
    th = _title(layer, ctx, reg, it.get("title", ""), t, 0, d, size=64 if place == "scene" else 46)
    items = (it.get("items") or [])[:4]
    n = max(1, len(items))
    times = item_times(n, it.get("times"), d, first=0.4)
    top = y0 + th + int(30 * ctx.u)
    box_w = int((x1 - x0) * (0.84 if place == "scene" else 0.94))
    box_h = min(int(200 * ctx.u), int((y1 - top) / n * 0.8))
    gap = ((y1 - top) - box_h * n) / max(1, n)
    f = font("semi", int(min(40, box_h * 0.22 / ctx.u) * ctx.u))
    fs = font("jost", int(24 * ctx.u))
    for k, raw in enumerate(items):
        txt, _, val = raw.partition("|")
        try:
            score = max(0, min(10, int(float(val.strip() or 0))))
        except ValueError:
            score = 0
        key = ("score", k, raw, box_w, box_h)
        if key not in ctx.cache:
            sp = card_sprite(box_w, box_h, ctx.u)
            sd = ImageDraw.Draw(sp)
            pad = int(30 * ctx.u)
            lines = wrap(txt.strip(), f, box_w - 2 * pad)[:2]
            for j, ln in enumerate(lines):
                sd.text((pad, pad + j * f.size * 1.15), ln, font=f, fill=TINTE, anchor="lt")
            ctx.cache[key] = _shadow(sp, int(14 * ctx.u), int(8 * ctx.u))
        cy = top + k * (box_h + gap) + box_h / 2
        rot = (-1.5, 1.2, -0.8, 1.0)[k % 4]
        s, a = appear(t, times[k], 0, d)
        if a <= 0:
            continue
        # Balken (wächst nach dem Erscheinen) direkt in die Karte zeichnen
        card = ctx.cache[key].copy()
        cd = ImageDraw.Draw(card)
        pad_s = int(14 * ctx.u) * 3
        pad = int(30 * ctx.u)
        seg_w = (box_w - 2 * pad - int(90 * ctx.u)) / 10
        bar_y = pad_s + box_h - pad - int(14 * ctx.u)
        grow = ease_out((t - times[k] - 0.2) / 0.6) * score
        for j in range(10):
            fill = LILA if j < grow else LAVENDEL
            bx = pad_s + pad + j * seg_w
            cd.rounded_rectangle((bx, bar_y, bx + seg_w - 6 * ctx.u, bar_y + int(14 * ctx.u)), radius=int(7 * ctx.u),
                                 fill=fill)
        cd.text((pad_s + box_w - pad, bar_y + int(7 * ctx.u)), f"{round(grow)}/10", font=fs, fill=TINTE, anchor="rm")
        paste_scaled(layer, card, ((x0 + x1) / 2, cy), s, a, rot=rot)


def draw_headline(layer, ctx, it, t, d, place):
    """Treppen-Überschrift wie in Carinas Post: Zeile für Zeile, jede etwas weiter rechts, Lila, Poppins ExtraBold.
    *Wort* wird Serif-Kursiv in Gold."""
    x0, y0, x1, y1 = ctx.region(place) if place == "scene" else (int(0.06 * ctx.w), int(0.08 * ctx.h),
                                                                   int(0.94 * ctx.w), int(0.5 * ctx.h))
    text = it.get("title", "")
    lines = [ln.strip() for ln in text.replace("|", "\n").split("\n") if ln.strip()]
    if len(lines) == 1:
        lines = wrap(lines[0], font("head", int(90 * ctx.u)), int((x1 - x0) * 0.6)) or lines
    n = max(1, len(lines))
    size = min(int((y1 - y0) / n / 1.1 / ctx.u), 120 if place == "scene" else 84)
    while True:  # so groß wie möglich, aber die Treppe muss in die Breite passen
        f = font("head", int(size * ctx.u))
        fa = font("serif_i", int(size * 1.15 * ctx.u))
        widths = [rich_width(ln, f, fa) for ln in lines]
        stair = (x1 - x0) * 0.08 * (n - 1)
        if max(widths) + stair <= (x1 - x0) or size <= 24:
            break
        size -= 4
    times = item_times(n, it.get("times"), d, first=0.1)
    lh = size * 1.05 * ctx.u
    total_shift = max(0, (x1 - x0) - max(widths))
    step = min(total_shift / max(1, n - 1), (x1 - x0) * 0.12) if n > 1 else 0
    x0 = x0 + (total_shift - step * (n - 1)) / 2  # Treppe mittig in der Fläche
    block_h = lh * n
    ty = y0 + ((y1 - y0) - block_h) / 2 if place == "scene" else y0
    color = it.get("color") == "white" and WEISS or LILA
    for k, ln in enumerate(lines):
        key = ("hl", k, ln, size)
        if key not in ctx.cache:
            im = Image.new("RGBA", (widths[k] + int(20 * ctx.u), int(lh * 1.35)), (0, 0, 0, 0))
            rich_line(ImageDraw.Draw(im), (int(10 * ctx.u), int(lh * 1.0)), ln, f, fa, color, GOLD)
            ctx.cache[key] = im
        im = ctx.cache[key]
        prog = ease_out((t - times[k]) / 0.35)
        if prog <= 0:
            continue
        out = min(1.0, max(0.0, (d - t) / 0.25))
        x = x0 + k * step
        y = ty + k * lh + (1 - prog) * 40 * ctx.u
        paste_scaled(layer, im, (x + im.width / 2, y + im.height / 2), 1.0, min(1.0, prog * 1.5) * out)


def draw_checklist(layer, ctx, it, t, d, place):
    """Checkliste: weiße Kästchen, Haken in Salbeigrün erscheint kurz nach dem Punkt."""
    reg = ctx.region(place)
    x0, y0, x1, y1 = reg
    th = _title(layer, ctx, reg, it.get("title", ""), t, 0, d, size=60 if place == "scene" else 46)
    items = (it.get("items") or [])[:6]
    n = max(1, len(items))
    times = item_times(n, it.get("times"), d, first=0.35)
    top = y0 + th + int(30 * ctx.u)
    row_h = min(int(120 * ctx.u), int((y1 - top) / n))
    f = font("hand", int(min(64, row_h * 0.55 / ctx.u) * ctx.u))
    box = int(row_h * 0.5)
    dr = ImageDraw.Draw(layer)
    for k, txt in enumerate(items):
        y = top + k * row_h + row_h / 2
        s, a = appear(t, times[k], 0, d)
        if a <= 0:
            continue
        key = ("chk", k, txt)
        if key not in ctx.cache:
            tw, _ = text_size(txt, f)
            pad = int(18 * ctx.u)
            sp = card_sprite(tw + 2 * pad, int(row_h * 0.72), ctx.u, radius=10)
            ImageDraw.Draw(sp).text((pad, sp.height / 2), txt, font=f, fill=TINTE, anchor="lm")
            ctx.cache[key] = _shadow(sp, int(8 * ctx.u), int(5 * ctx.u))
        bx = x0 + int(20 * ctx.u)
        al = int(255 * a)
        dr.rounded_rectangle((bx, y - box / 2, bx + box, y + box / 2), radius=int(6 * ctx.u), fill=WEISS + (al,),
                             outline=LILA + (al,), width=max(2, int(4 * ctx.u)))
        tick = ease_out((t - times[k] - 0.3) / 0.25)
        if tick > 0:
            pts = [(bx + box * 0.2, y), (bx + box * 0.42, y + box * 0.25), (bx + box * 0.85, y - box * 0.3)]
            if tick < 0.5:
                p = tick / 0.5
                pts = [pts[0], (pts[0][0] + (pts[1][0] - pts[0][0]) * p, pts[0][1] + (pts[1][1] - pts[0][1]) * p)]
            else:
                p = (tick - 0.5) / 0.5
                pts = [pts[0], pts[1], (pts[1][0] + (pts[2][0] - pts[1][0]) * p, pts[1][1] + (pts[2][1] - pts[1][1]) * p)]
            dr.line(pts, fill=SALBEI_TIEF + (al,), width=max(4, int(8 * ctx.u)), joint="curve")
        sp = ctx.cache[key]
        paste_scaled(layer, sp, (bx + box + int(24 * ctx.u) + sp.width / 2 - int(24 * ctx.u), y), s, a,
                     rot=(-1.5 if k % 2 else 1.0))


def draw_endcard(layer, ctx, it, t, d, place):
    """Volle lila Karte: kleine Zeile, großes Wort (z. B. "Kommentiere / RUHE"), Gold-Akzent."""
    w, h = ctx.w, ctx.h
    prog = ease_out(t / 0.35)
    layer.paste(LILA + (int(255 * min(1, prog * 1.4)),), (0, 0, w, h))
    title = it.get("title", "")
    big = (it.get("items") or [""])[0] if it.get("items") else it.get("accent", "")
    f1 = font("semi", int(56 * ctx.u))
    f2 = font("black", int(150 * ctx.u))
    big_txt = ((it.get("items") or [""])[0] if it.get("items") else it.get("accent", "")).upper()
    while big_txt and f2.getlength(big_txt) > w * 0.86 and f2.size > 30:
        f2 = font("black", int(f2.size * 0.9))
    dr = ImageDraw.Draw(layer)
    s, a = appear(t, 0.2, 0, d)
    al = int(255 * a)
    lines = wrap(title, f1, int(w * 0.8))
    y = h * 0.36
    for ln in lines:
        dr.text((w / 2, y), ln, font=f1, fill=LAVENDEL_HELL + (al,), anchor="mm")
        y += f1.size * 1.2
    if big:
        key = ("endbig", big)
        if key not in ctx.cache:
            tw, tht = text_size(big.upper(), f2)
            im = Image.new("RGBA", (tw + 40, tht + 80), (0, 0, 0, 0))
            ImageDraw.Draw(im).text((im.width / 2, im.height / 2), big.upper(), font=f2, fill=GOLD, anchor="mm")
            ctx.cache[key] = im
        s2, a2 = appear(t, 0.45, 0, d)
        paste_scaled(layer, ctx.cache[key], (w / 2, y + f2.size * 0.8), s2, a2)


def draw_bigwords(layer, ctx, it, t, d, place):
    """Große Untertitel, 1–2 Wörter auf einmal; Schlüsselwörter (aus "items") lila-kursiv in Serif."""
    words = ctx.words
    keys = {k.lower().strip(".,!?") for k in (it.get("items") or [])}
    cur = [w for w in words if w["s"] - 0.02 <= t <= w["e"] + 0.25]
    if not cur:
        return
    cur = cur[-2:]
    f = font("head", int(92 * ctx.u))
    fa = font("serif_i", int(110 * ctx.u))
    parts = []
    for wd in cur:
        clean = wd["w"].strip(".,!?…;:")
        parts.append((clean, clean.lower() in keys))
    widths = [int((fa if acc else f).getlength(p)) for p, acc in parts]
    space = int(f.getlength(" "))
    total = sum(widths) + space * (len(parts) - 1)
    y = ctx.h * (0.70 if ctx.portrait else 0.80)
    x = (ctx.w - total) / 2
    dr = ImageDraw.Draw(layer)
    for (p, acc), wdt in zip(parts, widths):
        ff = fa if acc else f
        col = LILA if acc else WEISS
        dr.text((x, y), p, font=ff, fill=col + (255,), anchor="ls", stroke_width=0 if acc else max(2, int(3 * ctx.u)),
                stroke_fill=(0, 0, 0, 70))
        x += wdt + space


def draw_pill(layer, ctx, it, t, d, place):
    """Kleine Pille oben in der Mitte ("+ Atemübung")."""
    txt = it.get("title", "")
    if not txt:
        return
    key = ("pill", txt)
    f = font("semi", int(38 * ctx.u))
    if key not in ctx.cache:
        tw, tht = text_size(txt, f)
        pad_x, pad_y = int(30 * ctx.u), int(16 * ctx.u)
        sp = card_sprite(tw + 2 * pad_x, tht + 2 * pad_y + int(8 * ctx.u), ctx.u, fill=LILA, radius=40)
        ImageDraw.Draw(sp).text((sp.width / 2, sp.height / 2), txt, font=f, fill=WEISS, anchor="mm")
        ctx.cache[key] = _shadow(sp, int(10 * ctx.u), int(5 * ctx.u))
    s, a = appear(t, 0.05, 0, d)
    paste_scaled(layer, ctx.cache[key], (ctx.w / 2, ctx.h * (0.12 if ctx.portrait else 0.1)), s, a)


def draw_poof(layer, ctx, it, t, d, place):
    """Puff! Eine Wolke aus weichen Kreisen (Lavendel, Weiß, Plum) und goldenen Funken platzt an der Stelle,
    an der Carina sitzt. Am dichtesten bei 0,25 s – genau dort liegt der Schnitt (sie ist weg / taucht auf)."""
    cx = (ctx.face[0] + ctx.face[2]) / 2 * ctx.w
    cy = min(ctx.h * 0.85, (ctx.face[1] + ctx.face[3]) / 2 * ctx.h + (ctx.face[3] - ctx.face[1]) * ctx.h * 0.6)
    if it.get("_center"):
        cx, cy = it["_center"]
    rnd = random.Random(it.get("id", "poof"))
    size = (ctx.face[3] - ctx.face[1]) * ctx.h * 1.4
    smoke = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(smoke)
    life = 0.9
    for k in range(46):
        ang = rnd.uniform(0, 2 * math.pi)
        dist = rnd.uniform(0.15, 1.0) * size
        r0 = rnd.uniform(0.18, 0.4) * size
        delay = rnd.uniform(0.0, 0.12)
        p = (t - delay) / life
        if p <= 0 or p >= 1:
            continue
        e = ease_out(p)
        x = cx + math.cos(ang) * dist * e
        y = cy + math.sin(ang) * dist * e * 0.8 - size * 0.25 * p
        r = r0 * (0.35 + 0.9 * e)
        a = int(255 * (1 - p) ** 1.3)
        col = (WEISS, LAVENDEL_HELL, WEISS, LAVENDEL, LAVENDEL_HELL, PLUM)[k % 6]
        dr.ellipse((x - r, y - r, x + r, y + r), fill=col + (a,))
    # weich wie Rauch: kleiner rechnen, verwischen, wieder groß
    sm = smoke.resize((smoke.width // 4, smoke.height // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(5 * ctx.u))
    layer.alpha_composite(sm.resize(layer.size, Image.BILINEAR))
    dr = ImageDraw.Draw(layer)
    for k in range(12):  # Funken
        ang = rnd.uniform(0, 2 * math.pi)
        dist = rnd.uniform(0.6, 1.3) * size
        p = (t - 0.05) / 0.7
        if p <= 0 or p >= 1:
            continue
        e = ease_out(p)
        x, y = cx + math.cos(ang) * dist * e, cy + math.sin(ang) * dist * e * 0.8
        r = (1 - p) * 22 * ctx.u
        a = int(255 * (1 - p))
        c = GOLD + (a,)
        dr.polygon([(x, y - r), (x + r * 0.28, y - r * 0.28), (x + r, y), (x + r * 0.28, y + r * 0.28), (x, y + r),
                    (x - r * 0.28, y + r * 0.28), (x - r, y), (x - r * 0.28, y - r * 0.28)], fill=c)


# Zeichner, die nur eine Ebene über dem Bild brauchen
LAYER_DRAWERS = {"steps": draw_steps, "cards": draw_cards, "tags": draw_tags, "scores": draw_scores,
                 "headline": draw_headline, "checklist": draw_checklist, "endcard": draw_endcard,
                 "bigwords": draw_bigwords, "pill": draw_pill, "poof": draw_poof}


def render_frame(frame: Image.Image, it: dict, t: float, d: float, ctx: Ctx, mask: Image.Image | None) -> Image.Image:
    """Ein Bild des Effekts. frame: RGB-Bild des Videos in diesem Moment. mask: Person (L, 255 = Carina)."""
    typ = it.get("type", "headline")
    place = it.get("place", "scene")
    if place not in TYPES.get(typ, ("", "", ("scene",)))[2]:
        place = TYPES.get(typ, ("", "", ("scene",)))[2][0]
    w, h = frame.size
    fade_in = min(1.0, t / 0.25)
    fade_out = min(1.0, max(0.0, (d - t) / 0.25))
    vis = min(fade_in, fade_out)
    base = frame.convert("RGBA")

    if typ in LAYER_DRAWERS:
        if place == "scene" and typ != "endcard":
            scene = lavender_bg(w, h) if "bg" not in ctx.cache else ctx.cache["bg"]
            ctx.cache["bg"] = scene
            layer = scene.copy()
            LAYER_DRAWERS[typ](layer, ctx, it, t, d, place)
            out = Image.blend(base, layer, vis)
        else:
            layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            LAYER_DRAWERS[typ](layer, ctx, it, t, d, place)
            out = base.copy()
            out.alpha_composite(layer)
        return out.convert("RGB")

    if typ == "card":
        # Video als abgerundete Karte auf Lavendel, Treppen-Überschrift darüber (wie Carinas Post)
        scene = ctx.cache.get("bg") or lavender_bg(w, h)
        ctx.cache["bg"] = scene
        layer = scene.copy()
        scale = 0.42 if ctx.portrait else 0.46
        k = ease_out(t / 0.45)
        sc = 1 - (1 - scale) * k
        cw, ch = int(w * sc), int(h * sc)
        small = frame.resize((cw, ch), Image.BILINEAR).convert("RGBA")
        m = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, cw - 1, ch - 1), radius=int(28 * ctx.u * k + 1), fill=255)
        small.putalpha(m)
        cy = h * (0.64 if ctx.portrait else 0.6) * k + (h / 2) * (1 - k)
        sh = _shadow(small, int(18 * ctx.u), int(12 * ctx.u), alpha=70) if k > 0.98 else small
        layer.alpha_composite(sh, (int(w / 2 - sh.width / 2), int(cy - sh.height / 2)))
        draw_headline(layer, ctx, dict(it, place="side"), max(0.0, t - 0.3), d, "side")
        return Image.blend(base, layer, vis).convert("RGB")

    if mask is None:
        return frame
    if typ == "behind":
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        txt = it.get("title", "")
        f = font("head", int((300 if not ctx.portrait else 220) * ctx.u))
        while f.getlength(txt) > w * 0.94 and f.size > 40:
            f = font("head", int(f.size * 0.9))
        s, a = appear(t, 0.05, 0, d, pop=0.4)
        key = ("behind", txt, f.size)
        if key not in ctx.cache:
            tw, tht = text_size(txt, f)
            im = Image.new("RGBA", (tw + 60, tht + 120), (0, 0, 0, 0))
            col = WEISS if it.get("color") != "lila" else LILA
            ImageDraw.Draw(im).text((im.width / 2, im.height / 2), txt, font=f, fill=col, anchor="mm")
            ctx.cache[key] = im
        fy = ctx.face[1] * h
        paste_scaled(layer, ctx.cache[key], (w / 2, max(f.size * 0.6, fy + f.size * 0.15)), s, a)
        withtext = base.copy()
        withtext.alpha_composite(layer)
        return Image.composite(base, withtext, mask).convert("RGB")
    if typ == "glow":
        edge = mask.filter(ImageFilter.MaxFilter(int(9 + 6 * ctx.u) | 1)).filter(ImageFilter.GaussianBlur(10 * ctx.u))
        a = edge.point(lambda v: min(255, int(v * 2 * vis)))
        glow = Image.new("RGBA", (w, h), LAVENDEL_HELL + (0,))
        glow.putalpha(a)
        out = base.copy()
        out.alpha_composite(glow)
        out = Image.composite(base, out, mask)
        if it.get("title"):
            layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw_pill(layer, ctx, it, t, d, "side")
            out.alpha_composite(layer)
        return out.convert("RGB")
    if typ == "background":
        bg = pattern_bg(w, h)
        mix = Image.composite(base, bg, mask)
        out = Image.blend(base, mix, vis)
        if it.get("title"):
            layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw_headline(layer, ctx, dict(it, place="side"), t, d, "side")
            out.alpha_composite(layer)
        return out.convert("RGB")
    return frame


# ---------------------------------------------------------------- Personen-Maske

SEG_URL = ("https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/"
           "selfie_multiclass_256x256.tflite")


class Segmenter:
    """Carina vom Hintergrund trennen (MediaPipe, läuft lokal). Das Modell (16 MB) wird beim ersten Mal geladen."""

    def __init__(self):
        import urllib.request

        from mediapipe.tasks.python import BaseOptions, vision

        from .config import MODELS_DIR
        p = MODELS_DIR / "selfie_multiclass.tflite"
        if not p.exists():
            tmp = p.with_suffix(".part")
            urllib.request.urlretrieve(SEG_URL, tmp)
            tmp.replace(p)
        self._seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
            base_options=BaseOptions(model_asset_path=str(p)), output_confidence_masks=True,
            running_mode=vision.RunningMode.IMAGE))

    def mask(self, frame: Image.Image) -> Image.Image:
        import mediapipe as mp
        small = frame if frame.width <= 960 else frame.resize((960, int(frame.height * 960 / frame.width)))
        res = self._seg.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(np.asarray(small))))
        person = 1 - res.confidence_masks[0].numpy_view().squeeze()
        m = Image.fromarray((np.clip(person, 0, 1) * 255).astype(np.uint8))
        return m.resize(frame.size, Image.BILINEAR).filter(ImageFilter.GaussianBlur(1.2))

    def close(self):
        try:
            self._seg.close()
        except Exception:  # noqa: BLE001
            pass


def preview_png(it: dict, w: int, h: int, face_box, frame: Image.Image | None, out: Path,
                segmenter: Segmenter | None = None) -> None:
    """Standbild des Effekts (für die Vorschau in der App), ca. bei 75 % der Dauer."""
    d = max(1.0, it["end"] - it["start"])
    ctx = Ctx(w, h, face_box, it.get("_words"))
    frame = frame or Image.new("RGB", (w, h), (90, 90, 90))
    mask = segmenter.mask(frame) if (segmenter and it.get("type") in NEEDS_MASK) else None
    render_frame(frame, it, d * 0.75, d, ctx, mask).save(out)
