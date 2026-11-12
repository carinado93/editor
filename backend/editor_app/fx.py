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
    "clothesline": ("A", "Clothesline", ("side", "scene")),
    "lighttrail": ("C", "Light trail", ("side",)),
    "vanish": ("D", "Disappear / appear in smoke", ("side",)),
    "flash": ("D", "Flash poses (pop around the room)", ("scene",)),
    "sticker": ("C", "Sticker heads (bubble head)", ("scene",)),
    "counter": ("C", "Number counting up behind you", ("side",)),
    "typewriter": ("B", "Typewriter text", ("side",)),
    "ghost": ("C", "Ghost trail", ("side",)),
    "whip": ("B", "Zoom-blur transition", ("side",)),
    "statement": ("A", "Statement card (full screen)", ("scene",)),
    "quote": ("B", "Quote on the clip", ("side",)),
    "switch": ("C", "Switch reveal (your text)", ("side",)),
    "repeat": ("B", "Repeating line (& again …)", ("side",)),
    "wordswap": ("B", "Changing last word", ("side",)),
    "label": ("B", "Purple label", ("side",)),
    "quotepill": ("B", "Quote pill", ("side",)),
    "number": ("B", "Big number (word|×3)", ("side",)),
    "name": ("B", "Name + title", ("side",)),
    "stickers": ("B", "Sticker list", ("side",)),
    "buzzword": ("B", "Buzzword pop", ("side",)),
    "outro": ("B", "Outro: Like & Subscribe + Thank you", ("side",)),
}
NO_AUTO_FILL = {"switch"}  # Carina schreibt den Text selbst – Claude füllt ihn nie aus
NEEDS_MASK = {"behind", "glow", "background", "lighttrail", "clothesline", "vanish", "sticker", "counter", "ghost",
              "switch"}
# brauchen Standbilder aus dem Originalvideo (leerer Raum, Posen) – geht nur mit Stativ
NEEDS_STILLS = {"vanish", "flash"}


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
        self.base_u = min(w, h) / 1080
        self.u = self.base_u
        self.portrait = h > w
        self.face = face_box or [0.35, 0.12, 0.65, 0.5]
        self.words = words or []  # [{w, s, e}] in Zeit relativ zum Effekt-Beginn
        self.cache: dict = {}
        self.stills: dict = {}  # "plate": leerer Raum, "poses": [(Bild, Maske), …]

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


def draw_clothesline(layer, ctx, it, t, d, place):
    """Wäscheleine oben quer durchs Bild, Karten hängen an Holzklammern und schaukeln sanft.
    items = Texte auf den Karten (2–5). Mit title erscheint zusätzlich ein großes Wort (bei "Text hinter dir" dahinter)."""
    w, h = ctx.w, ctx.h
    items = (it.get("items") or [])[:5]
    n = max(1, len(items))
    times = item_times(n, it.get("times"), d, first=0.3)
    # über Carinas Kopf, aber nie in den oberen Rand (dort steht im Reel der Hook-Text)
    y_line = int(h * max(0.14 if ctx.portrait else 0.1, ctx.face[1] - 0.08))
    sag = int(h * 0.05)
    dr = ImageDraw.Draw(layer)
    grow = ease_out(t / 0.4)
    out = min(1.0, max(0.0, (d - t) / 0.25))
    al = int(255 * out)
    # Leine (leicht durchhängend), wächst von links nach rechts
    pts = []
    for k in range(41):
        x = w * k / 40
        if x > w * grow:
            break
        pts.append((x, y_line + sag * math.sin(math.pi * k / 40)))
    if len(pts) > 1:
        dr.line(pts, fill=TINTE + (al,), width=max(2, int(3 * ctx.u)))
    cw = int(min(w / (n + 0.6), 260 * ctx.u))
    ch = int(cw * 1.2)
    f = font("hand", int(cw * 0.2))
    for k, txt in enumerate(items):
        px = w * (k + 0.75) / (n + 0.5)
        py = y_line + sag * math.sin(math.pi * px / w)
        key = ("line", k, txt, cw)
        if key not in ctx.cache:
            card = card_sprite(cw, ch, ctx.u, fill=WEISS, radius=6)
            cd = ImageDraw.Draw(card)
            m = int(cw * 0.08)
            fill = [LAVENDEL, CREME, (226, 232, 214), LAVENDEL_HELL][k % 4]
            ink = [LILA, TINTE, SALBEI_TIEF, LILA][k % 4]
            cd.rectangle((m, m, cw - m, int(ch * 0.66)), fill=fill)
            big, _, small_txt = txt.partition("|")
            fb = font("head", int(cw * 0.17))
            lines = wrap(big.strip(), fb, cw - 3 * m)[:3]
            while lines and max(fb.getlength(ln) for ln in lines) > cw - 3 * m and fb.size > 12:
                fb = font("head", int(fb.size * 0.9))
                lines = wrap(big.strip(), fb, cw - 3 * m)[:3]
            lh = fb.size * 1.08
            y0 = m + (int(ch * 0.66) - m) / 2 - (len(lines) - 1) * lh / 2
            for j, ln in enumerate(lines):
                cd.text((cw / 2, y0 + j * lh), ln, font=fb, fill=ink, anchor="mm")
            if small_txt.strip():
                cd.text((cw / 2, int(ch * 0.83)), small_txt.strip(), font=f, fill=TINTE, anchor="mm")
            sp = Image.new("RGBA", (cw + 40, ch + int(60 * ctx.u)), (0, 0, 0, 0))
            sp.alpha_composite(_shadow(card, int(8 * ctx.u), int(6 * ctx.u)).resize((cw + 40, ch + 40)), (0, int(30 * ctx.u)))
            pd = ImageDraw.Draw(sp)
            pw, ph = int(cw * 0.12), int(60 * ctx.u)  # Holzklammer
            pd.rounded_rectangle((sp.width / 2 - pw / 2, 0, sp.width / 2 + pw / 2, ph), radius=int(4 * ctx.u),
                                 fill=(201, 165, 104, 255), outline=(150, 118, 70, 255), width=max(1, int(2 * ctx.u)))
            ctx.cache[key] = sp
        sp = ctx.cache[key]
        prog = ease_out((t - times[k]) / 0.5)
        if prog <= 0:
            continue
        # fällt von oben an die Leine und schaukelt aus
        swing = math.sin((t - times[k]) * 5.5) * 6 * math.exp(-(t - times[k]) * 1.6) + math.sin(t * 1.7 + k) * 1.2
        y = py - (1 - prog) * h * 0.25 + sp.height / 2 - int(14 * ctx.u)
        paste_scaled(layer, sp, (px, y), 1.0, out, rot=swing)
    if it.get("title") and place == "scene":
        _title(layer, ctx, (int(0.08 * w), int(h * 0.62), int(0.92 * w), h), it["title"], t, 0.2, d, size=90)


def _contour(mask: Image.Image, n: int = 220) -> list[tuple[float, float]]:
    """Umriss der Person als Punktfolge (Strahlen vom Mittelpunkt, je der äußerste Rand)."""
    small = mask.resize((mask.width // 4, mask.height // 4))
    a = np.asarray(small) > 128
    ys, xs = np.nonzero(a)
    if len(xs) < 50:
        return []
    cx, cy = xs.mean(), ys.mean()
    ang = np.arctan2(ys - cy, xs - cx)
    dist = np.hypot(xs - cx, ys - cy)
    bins = ((ang + math.pi) / (2 * math.pi) * n).astype(int) % n
    far = np.zeros(n)
    px = np.full(n, np.nan)
    py = np.full(n, np.nan)
    order = np.argsort(dist)
    far[bins[order]] = dist[order]
    px[bins[order]] = xs[order]
    py[bins[order]] = ys[order]
    pts = [(float(px[k]) * 4, float(py[k]) * 4) for k in range(n) if not np.isnan(px[k])]
    return pts


def draw_lighttrail(base: Image.Image, ctx, it, t, d, mask: Image.Image) -> Image.Image:
    """Leuchtspur: ein heller Strich läuft um Carinas Umriss, mit weich auslaufendem Schweif."""
    w, h = base.size
    pts = _contour(mask)
    if len(pts) < 10:
        return base
    n = len(pts)
    head = (t / max(0.8, d * 0.6)) * n  # eine Runde in ~60 % der Zeit, dann weiter
    tail = int(n * 0.45)
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    core = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    cdr = ImageDraw.Draw(core)
    out = min(1.0, max(0.0, (d - t) / 0.3)) * min(1.0, t / 0.2)
    for j in range(tail):
        k0 = int(head - j) % n
        k1 = int(head - j - 1) % n
        fade = (1 - j / tail) * out
        if fade <= 0:
            continue
        gd.line((pts[k1], pts[k0]), fill=PLUM + (int(255 * fade),), width=int(30 * ctx.u))
        cdr.line((pts[k1], pts[k0]), fill=WEISS + (int(255 * fade),), width=max(3, int(8 * ctx.u)))
    glow = glow.filter(ImageFilter.GaussianBlur(12 * ctx.u))
    res0 = base.copy()
    res0.alpha_composite(glow)
    res0.alpha_composite(glow)  # doppelt = kräftiger Schein
    base = res0
    res = base.copy()
    res.alpha_composite(glow)
    res.alpha_composite(core)
    return res


def draw_typewriter(layer, ctx, it, t, d, place):
    """Schreibmaschine: Text erscheint Buchstabe für Buchstabe oben (weiß, lila Schatten), Cursor blinkt."""
    txt = (it.get("title") or "").replace("|", " ").replace("*", "")
    if not txt:
        return
    f = font("head", int((90 if ctx.portrait else 76) * ctx.u))
    lines = wrap(txt, f, int(ctx.w * 0.84))
    total = sum(len(ln) for ln in lines)
    shown = int(min(total, t / max(0.03, min(0.09, d * 0.5 / max(1, total)))))
    out = min(1.0, max(0.0, (d - t) / 0.25))
    dr = ImageDraw.Draw(layer)
    y = ctx.h * (0.14 if ctx.portrait else 0.1)
    left = shown
    for ln in lines:
        part = ln[:max(0, left)]
        left -= len(ln)
        x = ctx.w * 0.08
        if part:
            dr.text((x + 5 * ctx.u, y + 6 * ctx.u), part, font=f, fill=LILA + (int(230 * out),), anchor="lt")
            dr.text((x, y), part, font=f, fill=WEISS + (int(255 * out),), anchor="lt")
        if len(part) < len(ln) or ln is lines[-1]:  # hier steht der Cursor
            if int(t * 3) % 2 == 0:
                cx = x + f.getlength(part) + 6 * ctx.u
                dr.rectangle((cx, y, cx + 6 * ctx.u, y + f.size), fill=WEISS + (int(255 * out),))
            break
        y += f.size * 1.1


def _smoke(layer, ctx, cx, cy, size, t, seed, life=1.4, peak=0.45):
    """Große, weiche Rauchwolke (weiß/lavendel), steigt leicht auf und löst sich auf."""
    rnd = random.Random(seed)
    # nur die Deckkraft zeichnen (Graustufen), Farbe ist überall hell → keine dunklen Ränder beim Verwischen
    smoke = Image.new("L", (layer.width // 4, layer.height // 4), 0)
    dr = ImageDraw.Draw(smoke)
    cx, cy, size = cx / 4, cy / 4, size / 4
    for k in range(90):
        ang = rnd.uniform(0, 2 * math.pi)
        dist = rnd.uniform(0.0, 0.85) * size
        r0 = rnd.uniform(0.25, 0.5) * size
        delay = rnd.uniform(0.0, peak * 0.6)
        p = (t - delay) / life
        if p <= 0 or p >= 1:
            continue
        grow = ease_out(min(1.0, p * 2.2))
        x = cx + math.cos(ang) * dist * (0.4 + 0.8 * grow)
        y = cy + math.sin(ang) * dist * 0.9 * (0.4 + 0.8 * grow) - size * 0.35 * p
        r = r0 * (0.4 + 0.8 * grow)
        a = int(255 * min(1.0, p * 6) * (1 - p) ** 0.8)
        # übereinanderliegende Wolken addieren sich (dichter Kern)
        blob = Image.new("L", smoke.size, 0)
        ImageDraw.Draw(blob).ellipse((x - r, y - r, x + r, y + r), fill=a)
        smoke = Image.fromarray(np.minimum(255, np.asarray(smoke, dtype=np.uint16) + np.asarray(blob, dtype=np.uint16)
                                           * 3 // 4).astype(np.uint8))
    alpha = smoke.filter(ImageFilter.GaussianBlur(5 * ctx.u))
    # Rauch-Struktur: weiche Wolken-Flecken, die langsam wandern (heller/dunkler, dichter/durchsichtiger)
    sw, sh = alpha.size
    rng = np.random.default_rng(abs(hash(seed)) % (2 ** 32))
    n1 = rng.random((12, 20)).astype(np.float32)
    n2 = rng.random((24, 40)).astype(np.float32)
    def up(a, shift):
        im = Image.fromarray((a * 255).astype(np.uint8)).resize((sw + 40, sh + 40), Image.BICUBIC)
        dx = int(shift * 30) % 40
        return np.asarray(im.crop((dx, 40 - dx // 2, dx + sw, 40 - dx // 2 + sh)), dtype=np.float32) / 255
    noise = 0.6 * up(n1, t * 0.6) + 0.4 * up(n2, t * 1.1)
    a = np.asarray(alpha, dtype=np.float32) * (0.75 + 0.55 * noise)
    a = np.minimum(240, a)
    shade = 253 - 24 * (1 - noise)  # helle Wolke mit zarten grauen Schatten
    rgba = np.dstack([shade, shade, shade + 3, a]).clip(0, 255).astype(np.uint8)
    cloud = Image.fromarray(rgba, "RGBA").resize(layer.size, Image.BILINEAR)
    layer.alpha_composite(cloud)


def _bbox_center(mask: Image.Image | None, ctx) -> tuple[float, float, float]:
    """Mitte und Größe der Person (aus der Maske), sonst aus dem Gesicht geschätzt."""
    if mask is not None:
        box = mask.point(lambda v: 255 if v > 128 else 0).getbbox()
        if box:
            x0, y0, x1, y1 = box
            return (x0 + x1) / 2, (y0 + y1) / 2, max(x1 - x0, (y1 - y0) * 0.6)
    fx0, fy0, fx1, fy1 = ctx.face
    return (fx0 + fx1) / 2 * ctx.w, min(ctx.h * 0.8, fy1 * ctx.h + (fy1 - fy0) * ctx.h), (fx1 - fx0) * ctx.w * 2.4


def draw_vanish(base, ctx, it, t, d, mask):
    """Verschwinden (oder Auftauchen) in einer Rauchwolke: am dichtesten Punkt wird zwischen Carina und dem
    leeren Raum (Standbild vom Stativ) gewechselt."""
    plate = ctx.stills.get("plate")
    peak = min(0.6, d * 0.35)
    mode = it.get("mode") or "vanish"
    if "center" not in ctx.cache:
        fx0, fy0, fx1, fy1 = ctx.face
        fh = (fy1 - fy0) * ctx.h
        # Wolke um Kopf und Oberkörper, nicht über das ganze Bild
        ctx.cache["center"] = ((fx0 + fx1) / 2 * ctx.w, min(ctx.h * 0.7, (fy0 + fy1) / 2 * ctx.h + fh * 0.45),
                               min(ctx.h * 0.5, fh * 1.45))
    cx, cy, size = ctx.cache["center"]
    show_plate = (t >= peak) if mode == "vanish" else (t < peak)
    img = base.copy()
    if show_plate and plate is not None:
        img = plate.convert("RGBA").copy()
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    _smoke(layer, ctx, cx, cy, size, t, it.get("id", "v"), life=min(1.6, d), peak=peak)
    img.alpha_composite(layer)
    return img


def draw_flash(base, ctx, it, t, d, mask):
    """Flash-Posen: Carina taucht nacheinander an verschiedenen Stellen im Raum auf (Standbilder aus dem Video,
    freigestellt auf dem leeren Raum). Jede neue Pose beginnt mit einer weiß leuchtenden Silhouette."""
    plate = ctx.stills.get("plate")
    poses = ctx.stills.get("poses") or []
    if not poses:
        return base
    if not ctx.stills.get("own_plate"):
        plate = None  # ohne eigene Aufnahme: jede Pose als ganzes Bild, Wechsel mit weißem Blitz
    hold = d / len(poses)
    k = min(len(poses) - 1, int(t / hold))
    local = t - k * hold
    still, m = poses[k]
    img = plate.convert("RGBA").copy() if plate is not None else still.convert("RGBA").copy()
    flash = 0.16
    if local < flash:
        # weiße Silhouette mit Schein (erst ganz weiß), die dann in die Person übergeht
        a = 1.0 if local < flash * 0.45 else 1 - (local - flash * 0.45) / (flash * 0.55)
        person = Image.composite(still.convert("RGBA"), img, m)
        white = Image.new("RGBA", img.size, WEISS + (0,))
        white.putalpha(m.point(lambda v: int(v * a)))
        halo = Image.new("RGBA", img.size, WEISS + (0,))
        halo.putalpha(m.filter(ImageFilter.MaxFilter(int(15 * ctx.u) | 1)).filter(ImageFilter.GaussianBlur(14 * ctx.u))
                      .point(lambda v: int(v * a * 0.9)))
        person.alpha_composite(halo)
        person.alpha_composite(white)
        return person
    return Image.composite(still.convert("RGBA"), img, m)


@functools.cache
def sticker_bg(w: int, h: int) -> Image.Image:
    """Hintergrund für die Sticker-Köpfe: Lavendel mit goldenen Sternen."""
    im = lavender_bg(w, h)
    d = ImageDraw.Draw(im)
    rnd = random.Random(7)
    u = min(w, h) / 1080
    for _ in range(14):
        x, y, r = rnd.uniform(0, w), rnd.uniform(0, h), rnd.uniform(18, 34) * u
        pts = []
        for j in range(10):
            ang = -math.pi / 2 + j * math.pi / 5
            rr = r if j % 2 == 0 else r * 0.45
            pts.append((x + math.cos(ang) * rr, y + math.sin(ang) * rr))
        d.polygon(pts, fill=GOLD + (230,))
    return im


def draw_sticker(base, ctx, it, t, d, mask):
    """Sticker-Köpfe: Carinas Kopf freigestellt mit dickem weißem Rand, zweimal auf Lavendel mit Sternen,
    wippt leicht; in der Mitte groß das gerade gesprochene Wort."""
    w, h = base.size
    bg = sticker_bg(w, h).copy()
    fx0, fy0, fx1, fy1 = ctx.face
    fw, fh = (fx1 - fx0) * w, (fy1 - fy0) * h
    box = (int(max(0, fx0 * w - fw * 0.35)), int(max(0, fy0 * h - fh * 0.45)),
           int(min(w, fx1 * w + fw * 0.35)), int(min(h, fy1 * h + fh * 0.25)))
    if mask is not None and box[2] > box[0] and box[3] > box[1]:
        head = base.crop(box)
        hm = mask.crop(box).point(lambda v: 255 if v > 150 else 0).filter(ImageFilter.GaussianBlur(1.5))
        # Kopf-Form: Maske, unten weich abgeschnitten
        cut = Image.new("L", head.size, 0)
        ImageDraw.Draw(cut).ellipse((-head.width * 0.1, -head.height * 0.2, head.width * 1.1, head.height * 1.02), fill=255)
        hm = Image.composite(hm, Image.new("L", head.size, 0), cut)
        border = hm.filter(ImageFilter.MaxFilter(int(17 * ctx.u) | 1))
        stk = Image.new("RGBA", head.size, WEISS + (0,))
        stk.putalpha(border)
        head_rgba = head.convert("RGBA")
        head_rgba.putalpha(hm)
        stk.alpha_composite(head_rgba)
        stk = _shadow(stk, int(10 * ctx.u), int(8 * ctx.u), alpha=50)
        target = h * (0.36 if ctx.portrait else 0.62)
        sc = target / stk.height
        pos = [(w * 0.5, h * 0.25), (w * 0.5, h * 0.75)] if ctx.portrait else [(w * 0.25, h * 0.5), (w * 0.75, h * 0.5)]
        for j, (px, py) in enumerate(pos):
            bob = math.sin(t * 4 + j * 1.7) * 10 * ctx.u
            s_, a = appear(t, 0.05 + j * 0.12, 0, d)
            paste_scaled(bg, stk, (px, py + bob), sc * s_, a, rot=math.sin(t * 2.5 + j) * 3)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    cur = [x for x in ctx.words if x["s"] - 0.02 <= t <= x["e"] + 0.2]
    if cur:
        word = cur[-1]["w"].strip(".,!?…;:")
        f = font("black", int(110 * ctx.u))
        while f.getlength(word) > w * 0.9 and f.size > 30:
            f = font("black", int(f.size * 0.9))
        ImageDraw.Draw(layer).text((w / 2, h / 2), word, font=f, fill=WEISS, anchor="mm",
                                   stroke_width=max(3, int(8 * ctx.u)), stroke_fill=LILA)
    bg.alpha_composite(layer)
    fade = min(1.0, t / 0.2, max(0.0, (d - t) / 0.2))
    return Image.blend(base, bg, fade)


def draw_counter(base, ctx, it, t, d, mask):
    """Große Zahl zählt hinter Carina hoch (z. B. 0 → 120), kleine Zeile darunter ("Tage")."""
    w, h = base.size
    raw = (it.get("title") or "100").split("|")
    num_txt = raw[0].strip()
    label = raw[1].strip() if len(raw) > 1 else ""
    digits = "".join(ch for ch in num_txt if ch.isdigit())
    target = int(digits) if digits else 0
    pre = num_txt[:len(num_txt) - len(num_txt.lstrip("+-€$ "))]
    suf = num_txt[len(pre) + len(digits):] if digits and num_txt.find(digits) >= 0 else ""
    p = ease_out(t / max(0.5, d * 0.55))
    val = f"{pre}{int(round(target * p)):,}{suf}".replace(",", ".")
    f = font("black", int((380 if not ctx.portrait else 300) * ctx.u))
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)
    out = min(1.0, max(0.0, (d - t) / 0.25)) * min(1.0, t / 0.15)
    cy = h * (0.3 if not ctx.portrait else 0.32)
    dr.text((w / 2, cy), val, font=f, fill=WEISS + (int(255 * out),), anchor="mm")
    if label:
        fl = font("serif_i", int(90 * ctx.u))
        dr.text((w / 2, cy + f.size * 0.55), label, font=fl, fill=GOLD + (int(255 * out),), anchor="mm")
    withtext = base.copy()
    withtext.alpha_composite(layer)
    return Image.composite(base, withtext, mask) if mask is not None else withtext


def draw_ghost(base, ctx, it, t, d, mask):
    """Geister-Spur: zwei durchsichtige Kopien von Carina aus den letzten Momenten bleiben hinter ihr zurück."""
    hist = ctx.cache.setdefault("ghost", [])
    out = base.copy()
    fade = min(1.0, t / 0.2, max(0.0, (d - t) / 0.25))
    for j, (img, m, _) in enumerate(hist[-3::-2][:2]):  # ältere Bilder
        a = (0.42 if j == 0 else 0.22) * fade
        ghost = img.convert("RGBA")
        ghost.putalpha(m.point(lambda v: int(v * a)))
        out.alpha_composite(ghost)
    if mask is not None:
        out = Image.composite(base, out, mask)  # die echte Carina immer vorn
        if not hist or t - hist[-1][2] >= 0.12:
            hist.append((base.copy(), mask.copy(), t))
            del hist[:-8]
    return out


def draw_whip(base, ctx, it, t, d):
    """Zoom-Blur-Übergang: zur Mitte hin zoomt das Bild schnell und verwischt (gut über einem Schnitt)."""
    mid = d / 2
    k = max(0.0, 1 - abs(t - mid) / mid)  # 0 → 1 → 0
    k = k * k
    if k < 0.02:
        return base
    w, h = base.size
    acc = None
    steps = 6
    for j in range(steps):
        z = 1 + k * 0.35 * (j / (steps - 1))
        cw, ch = int(w / z), int(h / z)
        crop = base.crop(((w - cw) // 2, (h - ch) // 2, (w + cw) // 2, (h + ch) // 2)).resize((w, h), Image.BILINEAR)
        arr = np.asarray(crop, dtype=np.float32)
        acc = arr if acc is None else acc + arr
    blur = Image.fromarray((acc / steps).astype(np.uint8), base.mode)
    return Image.blend(base, blur, min(1.0, k * 1.4))


@functools.cache
def radial_bg(w: int, h: int) -> Image.Image:
    """Weicher Farbverlauf von der Mitte nach außen: kräftiges Lila innen, helles Lavendel außen."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((x - w / 2) / (w * 0.62)) ** 2 + ((y - h * 0.45) / (h * 0.55)) ** 2)
    k = np.clip(r, 0, 1)[..., None] ** 1.2
    inner = np.array((150, 112, 205), np.float32)
    outer = np.array(LAVENDEL_HELL, np.float32)
    arr = (inner * (1 - k) + outer * k).astype(np.uint8)
    return Image.fromarray(arr, "RGB").convert("RGBA")


def draw_statement(base, ctx, it, t, d):
    """Statement-Karte: ganzer Bildschirm weicher Lila-Verlauf, mittig eine kurze Zeile in kleinen fetten Großbuchstaben."""
    w, h = base.size
    card = radial_bg(w, h).copy()
    txt = (it.get("title") or "").replace("|", " ").replace("*", "").upper()
    if txt:
        f = font("head", int(44 * ctx.u))
        lines = wrap(txt, f, int(w * 0.7))
        dr = ImageDraw.Draw(card)
        a = int(255 * min(1.0, t / 0.3, max(0.0, (d - t) / 0.2)))
        y = h * 0.45 - (len(lines) - 1) * f.size * 0.6
        for ln in lines:
            dr.text((w / 2, y), ln, font=f, fill=CREME + (a,), anchor="mm")
            y += f.size * 1.2
    fade = min(1.0, t / 0.12, max(0.0, (d - t) / 0.12))
    return Image.blend(base, card, fade)


def draw_quote(layer, ctx, it, t, d, place):
    """Zitat auf dem Clip: kursive Serifenschrift in Creme, mittig im unteren Drittel, weich eingeblendet."""
    txt = (it.get("title") or "").replace("|", "\n")
    if not txt.strip():
        return
    f = font("serif_i", int((64 if ctx.portrait else 58) * ctx.u))
    lines = []
    for part in txt.split("\n"):
        lines += wrap(part, f, int(ctx.w * 0.78))
    a = min(1.0, t / 0.4, max(0.0, (d - t) / 0.3))
    dr = ImageDraw.Draw(layer)
    y = ctx.h * (0.6 if ctx.portrait else 0.7) - (len(lines) - 1) * f.size * 0.55
    for ln in lines:
        dr.text((ctx.w / 2 + 3 * ctx.u, y + 3 * ctx.u), ln, font=f, fill=(0, 0, 0, int(110 * a)), anchor="mm")
        dr.text((ctx.w / 2, y), ln, font=f, fill=CREME + (int(255 * a),), anchor="mm")
        y += f.size * 1.1


def draw_repeat(layer, ctx, it, t, d, place):
    """Wiederholte Zeile: oben der Satz, darunter erscheint immer wieder dieselbe Wendung ("& again")."""
    title = (it.get("title") or "").replace("|", " ").replace("*", "")
    rep_txt = ((it.get("items") or [""])[0] or "").strip()
    if not rep_txt and title:
        rep_txt = "& " + title.split()[-1]
    if not title and not rep_txt:
        return
    f = font("semi", int((42 if ctx.portrait else 38) * ctx.u))
    lh = f.size * 1.12
    x = ctx.w * (0.62 if ctx.portrait else 0.66)
    y0 = ctx.h * 0.18
    out = min(1.0, max(0.0, (d - t) / 0.3))
    dr = ImageDraw.Draw(layer)
    tl = wrap(title, f, int(ctx.w * 0.34)) if title else []
    kw = dict(font=f, anchor="ma", stroke_width=max(1, int(2 * ctx.u)), stroke_fill=(0, 0, 0, int(60 * out)))
    for k, ln in enumerate(tl):
        dr.text((x, y0 + k * lh), ln, fill=WEISS + (int(255 * out),), **kw)
    max_lines = max(0, int((ctx.h * 0.86 - y0) / lh) - len(tl))
    shown = min(max_lines, int(max(0.0, t - 0.4) / 0.16) + (1 if t >= 0.4 else 0))
    for k in range(shown):
        dr.text((x, y0 + (len(tl) + k) * lh), rep_txt, fill=WEISS + (int(255 * out),), **kw)


def draw_wordswap(layer, ctx, it, t, d, place):
    """Fester Satz in Serifenschrift, das letzte Wort wechselt alle ~0,8 s (größer gesetzt)."""
    fixed = (it.get("title") or "").replace("|", " ").replace("*", "")
    words = [w.strip() for w in it.get("items") or [] if w.strip()]
    if not fixed and not words:
        return
    f = font("serif", int((60 if ctx.portrait else 52) * ctx.u))
    fb = font("serif", int((84 if ctx.portrait else 74) * ctx.u))
    lines: list[str] = []
    for wd in fixed.split():  # wie im Vorbild: kurze Zeilen
        if lines and len(lines[-1]) + 1 + len(wd) <= 14:
            lines[-1] += " " + wd
        else:
            lines.append(wd)
    out = min(1.0, t / 0.3, max(0.0, (d - t) / 0.3))
    dr = ImageDraw.Draw(layer)
    x = ctx.w * 0.1
    y = ctx.h * (0.52 if ctx.portrait else 0.4)
    for ln in lines:
        dr.text((x, y), ln, font=f, fill=CREME + (int(255 * out),), anchor="ls")
        y += f.size * 0.95
    if words:
        k = int(t / 0.8) % len(words)
        local = (t % 0.8) / 0.8
        a = out if len(words) == 1 else out * min(1.0, local / 0.15, (1 - local) / 0.12)
        dr.text((x, y + fb.size * 0.15), words[k], font=fb, fill=WEISS + (int(255 * max(0.0, a)),), anchor="ls")


def draw_switch(base, ctx, it, t, d, mask):
    """Schalter-Enthüllung: oben ein großer Schalter (grau → Salbeigrün); sobald Carina "drückt", leuchtet hinter
    ihr ein Rahmen-Plakat auf (Lila, Gold-Schrift). Den Text schreibt Carina selbst (Überschrift + kleine Zeile)."""
    w, h = base.size
    tap = (it.get("times") or [min(0.8, d * 0.3)])[0]
    on = ease_out((t - tap) / 0.25)
    poster_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if on > 0:
        pw, ph = int(w * (0.72 if ctx.portrait else 0.42)), int(h * (0.42 if ctx.portrait else 0.62))
        px, py = (w - pw) // 2, int(h * (0.24 if ctx.portrait else 0.2))
        key = ("poster", pw, ph, it.get("title"), tuple(it.get("items") or []))
        if key not in ctx.cache:
            poster = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
            pd = ImageDraw.Draw(poster)
            pd.rectangle((0, 0, pw - 1, ph - 1), fill=LILA_TIEF)
            m = int(16 * ctx.u)
            pd.rectangle((m, m, pw - 1 - m, ph - 1 - m), outline=GOLD, width=max(2, int(4 * ctx.u)))
            title = (it.get("title") or "").replace("|", "\n").replace("*", "").upper()
            if title.strip():
                fh = font("black", int(min(130, ph / 4.2 / ctx.u) * ctx.u))
                parts = title.split("\n")
                lines = [ln for part in parts for ln in wrap(part, fh, pw - 4 * m)]
                while lines and max(fh.getlength(x) for x in lines) > pw - 4 * m and fh.size > 20:
                    fh = font("black", int(fh.size * 0.9))
                    lines = [ln for part in parts for ln in wrap(part, fh, pw - 4 * m)]
                y = ph * 0.42 - (len(lines) - 1) * fh.size * 0.5
                for ln in lines:
                    pd.text((pw / 2, y), ln, font=fh, fill=GOLD, anchor="mm")
                    y += fh.size * 1.0
            pill = ((it.get("items") or [""])[0] or "").strip().upper()
            if pill:
                fp = font("head", int(34 * ctx.u))
                while fp.getlength(pill) > pw * 0.8 and fp.size > 12:
                    fp = font("head", int(fp.size * 0.9))
                tw = fp.getlength(pill)
                bx0, by = pw / 2 - tw / 2 - 26 * ctx.u, ph * 0.78
                pd.rounded_rectangle((bx0, by - fp.size * 0.85, pw - bx0, by + fp.size * 0.85), radius=int(40 * ctx.u),
                                     fill=LAVENDEL, outline=GOLD, width=max(2, int(3 * ctx.u)))
                pd.text((pw / 2, by), pill, font=fp, fill=LILA, anchor="mm")
            glow = Image.new("RGBA", (pw + 120, ph + 120), (0, 0, 0, 0))
            ImageDraw.Draw(glow).rectangle((60, 60, pw + 60, ph + 60), fill=(255, 236, 190, 200))
            glow = glow.filter(ImageFilter.GaussianBlur(28 * ctx.u))
            glow.alpha_composite(poster, (60, 60))
            ctx.cache[key] = glow
        paste_scaled(poster_layer, ctx.cache[key], (px + pw / 2, py + ph / 2), 0.92 + 0.08 * on, on)
    out = base.copy()
    out.alpha_composite(poster_layer)
    if mask is not None:
        out = Image.composite(base, out, mask)  # Carina steht vor dem Plakat
    # Schalter oben, immer ganz vorn
    sw_, sh_ = int(w * (0.36 if ctx.portrait else 0.16)), int(w * (0.36 if ctx.portrait else 0.16) * 0.42)
    sx, sy = (w - sw_) // 2, int(h * (0.08 if ctx.portrait else 0.05))
    col = tuple(int(a * (1 - on) + b * on) for a, b in zip((150, 150, 150), SALBEI))
    pad = int(sh_ * 0.1)
    kr = sh_ // 2 - pad
    kx = sx + pad + kr + (sw_ - 2 * pad - 2 * kr) * on
    sd = ImageDraw.Draw(out)
    sd.rounded_rectangle((sx, sy, sx + sw_, sy + sh_), radius=sh_ // 2, fill=col + (255,))
    sd.ellipse((kx - kr, sy + pad, kx + kr, sy + pad + 2 * kr), fill=WEISS + (255,))
    fade = min(1.0, t / 0.2, max(0.0, (d - t) / 0.3))
    return Image.blend(base, out, fade)


def _chest(ctx):
    fx0, fy0, fx1, fy1 = ctx.face
    return (fx0 + fx1) / 2 * ctx.w, ctx.h * min(0.82, max(0.56, fy1 + 0.22))


def _side(ctx):
    fx0, fy0, fx1, fy1 = ctx.face
    right = (fx0 + fx1) / 2 < 0.55
    x = ctx.w * (min(0.8, fx1 + 0.05) if right else max(0.2, fx0 - 0.05))
    return x, ctx.h * max(0.18, (fy0 + fy1) / 2), right


def _box_text(text, f, fg, bg, pad_x, pad_y, radius, f_acc=None, acc=None):
    w = rich_width(text, f, f_acc or f) if f_acc else int(f.getlength(text))
    hgt = int(f.size * 1.25)
    im = Image.new("RGBA", (w + 2 * pad_x, hgt + 2 * pad_y), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=radius, fill=bg)
    if f_acc:
        rich_line(d, (pad_x, pad_y + int(f.size * 0.95)), text, f, f_acc, fg, acc)
    else:
        d.text((pad_x, pad_y + int(f.size * 0.95)), text, font=f, fill=fg, anchor="ls")
    return im


def draw_label(layer, ctx, it, t, d, place):
    """Lila Kasten, weiße Großbuchstaben (Poppins ExtraBold) auf Brusthöhe – Kernaussage, SEO-Wort."""
    txt = (it.get("title") or "").replace("*", "").replace("|", " ").upper()
    if not txt:
        return
    f = font("head", int(56 * ctx.u))
    lines = wrap(txt, f, int(ctx.w * 0.5))
    cx, cy = _chest(ctx)
    for k, ln in enumerate(lines):
        key = ("lbl", ln, f.size)
        if key not in ctx.cache:
            ctx.cache[key] = _box_text(ln, f, WEISS, LILA, int(18 * ctx.u), int(6 * ctx.u), int(6 * ctx.u))
        s_, a = appear(t, 0.0 + k * 0.08, 0, d)
        sp = ctx.cache[key]
        paste_scaled(layer, sp, (cx, cy + k * sp.height * 1.02), s_, a)


def draw_quotepill(layer, ctx, it, t, d, place):
    """Cremefarbene Pille, Cormorant, *Wort* lila-kursiv – ruhiger Merksatz."""
    txt = (it.get("title") or "").replace("|", " ")
    if not txt:
        return
    f = font("serif", int(56 * ctx.u))
    fa = font("serif_i", int(56 * ctx.u))
    cx, cy = _chest(ctx)
    key = ("qp", txt, f.size)
    if key not in ctx.cache:
        ctx.cache[key] = _shadow(_box_text(txt, f, TINTE, CREME, int(26 * ctx.u), int(10 * ctx.u), int(22 * ctx.u), fa, LILA),
                                 int(8 * ctx.u), int(5 * ctx.u))
    s_, a = appear(t, 0.0, 0, d)
    paste_scaled(layer, ctx.cache[key], (cx, cy), s_, a)


def draw_number(layer, ctx, it, t, d, place):
    """Wort + große Zahl ("BURNOUT" + "×3") neben Carina."""
    word, _, num = (it.get("title") or "").partition("|")
    if not num and it.get("items"):
        num = it["items"][0]
    x, y, right = _side(ctx)
    f = font("head", int(54 * ctx.u))
    fn = font("black", int(130 * ctx.u))
    if word.strip():
        key = ("nw", word, f.size)
        if key not in ctx.cache:
            ctx.cache[key] = _box_text(word.strip().upper(), f, WEISS, LILA, int(16 * ctx.u), int(6 * ctx.u), int(6 * ctx.u))
        sp = ctx.cache[key]
        s_, a = appear(t, 0.0, 0, d)
        paste_scaled(layer, sp, (x + (sp.width / 2 if right else -sp.width / 2), y), s_, a)
    if num.strip():
        key = ("nn", num, fn.size)
        if key not in ctx.cache:
            ctx.cache[key] = _box_text(num.strip(), fn, GOLD, LILA_TIEF, int(18 * ctx.u), int(4 * ctx.u), int(8 * ctx.u))
        sp = ctx.cache[key]
        s_, a = appear(t, 0.2, 0, d)
        paste_scaled(layer, sp, (x + (sp.width / 2 if right else -sp.width / 2), y + sp.height * 0.9), s_, a)


def draw_name(layer, ctx, it, t, d, place):
    """Bauchbinde: Name (Cormorant auf Creme) + Titel (kleine lila Zeile)."""
    name, _, title = (it.get("title") or "").partition("|")
    if not name.strip():
        return
    x, y, right = _side(ctx)
    f = font("serif", int(48 * ctx.u))
    ft = font("semi", int(24 * ctx.u))
    key = ("nm", name, title, f.size)
    if key not in ctx.cache:
        a = _box_text(name.strip(), f, TINTE, CREME, int(16 * ctx.u), int(4 * ctx.u), int(4 * ctx.u))
        b = _box_text(title.strip(), ft, WEISS, LILA, int(12 * ctx.u), int(4 * ctx.u), int(4 * ctx.u)) if title.strip() else None
        w = max(a.width, b.width if b else 0)
        im = Image.new("RGBA", (w, a.height + (b.height + int(4 * ctx.u) if b else 0)), (0, 0, 0, 0))
        im.alpha_composite(a, (0, 0))
        if b:
            im.alpha_composite(b, (0, a.height + int(4 * ctx.u)))
        ctx.cache[key] = im
    sp = ctx.cache[key]
    s_, al = appear(t, 0.0, 0, d)
    paste_scaled(layer, sp, (x + (sp.width / 2 if right else -sp.width / 2), y), s_, al)


def draw_stickers(layer, ctx, it, t, d, place):
    """Weiße Zettel mit Handschrift, erscheinen nacheinander untereinander neben Carina (Aufzählung)."""
    items = (it.get("items") or [])[:6]
    if not items:
        return
    times = item_times(len(items), it.get("times"), d, first=0.15)
    x, y, right = _side(ctx)
    f = font("hand", int(46 * ctx.u))
    step = f.size * 1.5
    for k, txt in enumerate(items):
        key = ("stk", txt.upper(), f.size)
        if key not in ctx.cache:
            ctx.cache[key] = _shadow(_box_text(txt.upper(), f, TINTE, WEISS, int(14 * ctx.u), int(4 * ctx.u), int(4 * ctx.u)),
                                     int(6 * ctx.u), int(4 * ctx.u))
        sp = ctx.cache[key]
        s_, a = appear(t, times[k], 0, d)
        paste_scaled(layer, sp, (x + (sp.width / 2 if right else -sp.width / 2), y + k * step), s_, a,
                     rot=(-2 if k % 2 == 0 else 1.5))


def draw_buzzword(layer, ctx, it, t, d, place):
    """Buzzword-Pop: ein Wort groß in Cormorant auf hellem Flieder neben Carinas Gesicht."""
    txt = (it.get("title") or "").replace("*", "").replace("|", " ").strip()
    if not txt:
        return
    x, y, right = _side(ctx)
    f = font("serif", int(84 * ctx.u))
    key = ("bz", txt, f.size)
    if key not in ctx.cache:
        ctx.cache[key] = _box_text(txt, f, LILA_TIEF, (205, 191, 224), int(18 * ctx.u), int(4 * ctx.u), int(8 * ctx.u))
    sp = ctx.cache[key]
    s_, a = appear(t, 0.0, 0, d, pop=0.26)
    paste_scaled(layer, sp, (x + (sp.width / 2 if right else -sp.width / 2), y), s_, a)


def _heart(size: int, color) -> Image.Image:
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = size * 0.27
    d.ellipse((size * 0.06, size * 0.12, size * 0.06 + 2 * r, size * 0.12 + 2 * r), fill=color)
    d.ellipse((size * 0.94 - 2 * r, size * 0.12, size * 0.94, size * 0.12 + 2 * r), fill=color)
    d.polygon([(size * 0.08, size * 0.42), (size * 0.92, size * 0.42), (size * 0.5, size * 0.9)], fill=color)
    return im


def _outro_button(text, f, fg, bg, u, icon=None):
    pad_x, pad_y = int(30 * u), int(14 * u)
    ic = int(f.size * 0.9) if icon else 0
    gap = int(12 * u) if icon else 0
    w = int(f.getlength(text)) + ic + gap + 2 * pad_x
    hgt = int(f.size * 1.3) + 2 * pad_y
    im = Image.new("RGBA", (w, hgt), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, hgt - 1), radius=hgt // 2, fill=bg)
    if icon:
        im.alpha_composite(_heart(ic, icon), (pad_x, (hgt - ic) // 2))
    d.text((pad_x + ic + gap, hgt / 2), text, font=f, fill=fg, anchor="lm")
    return _with_shadow(im, u)


def _with_shadow(sprite: Image.Image, u: float) -> Image.Image:
    sh = _shadow(sprite, int(10 * u), int(6 * u), 70).filter(ImageFilter.GaussianBlur(int(10 * u)))
    pad = (sh.width - sprite.width) // 2
    sh.alpha_composite(sprite, (pad, pad - int(6 * u) if pad - int(6 * u) >= 0 else pad))
    return sh


def draw_outro(layer, ctx, it, t, d, place):
    """Schluss fürs YouTube-Video: "Thank you for watching" oben, unten Like- und Abo-Knopf,
    ein Mauszeiger klickt beide an (Herz wird gold, Abo wird zu "Subscribed")."""
    w, h, u = ctx.w, ctx.h, ctx.u
    title = (it.get("title") or "Thank you for watching").replace("|", " ").replace("*", "")
    items = [x for x in (it.get("items") or []) if str(x).strip()]
    like = (items[0] if items else "Like").upper()
    sub = (items[1] if len(items) > 1 else "Subscribe").upper()
    subbed = (items[2] if len(items) > 2 else "Subscribed").upper()

    # oben: cremefarbene Karte mit Serif-Kursiv
    f_t = font("serif_i", int(84 * u))
    lines = wrap(title, f_t, int(w * 0.8))
    key = ("outro_t", title, f_t.size)
    if key not in ctx.cache:
        lw = max(int(f_t.getlength(ln)) for ln in lines)
        lh = int(f_t.size * 1.1)
        im = Image.new("RGBA", (lw + int(70 * u), lh * len(lines) + int(40 * u)), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=int(26 * u), fill=PAPIER + (235,))
        for k, ln in enumerate(lines):
            dr.text((im.width / 2, int(20 * u) + lh * k + lh / 2), ln, font=f_t, fill=LILA, anchor="mm")
        ctx.cache[key] = _with_shadow(im, u)
    s_, a = appear(t, 0.1, 0, d)
    paste_scaled(layer, ctx.cache[key], (w / 2, h * 0.16 + ctx.cache[key].height / 2), s_, a)

    # unten: zwei Knöpfe, Zeiger klickt erst Like (t≈1.2), dann Subscribe (t≈2.3)
    f_b = font("head", int(44 * u))
    t_like, t_sub = min(1.2, d * 0.3), min(2.3, d * 0.55)
    liked, subbed_now = t >= t_like, t >= t_sub
    b_like = ctx.cache.setdefault(("ob", like, liked, f_b.size),
                                  _outro_button(like, f_b, LILA if not liked else WEISS,
                                                WEISS if not liked else GOLD, u, icon=LILA if not liked else WEISS))
    b_sub = ctx.cache.setdefault(("ob", sub, subbed, subbed_now, f_b.size),
                                 _outro_button(subbed if subbed_now else sub, f_b, WEISS,
                                               SALBEI if subbed_now else LILA, u))
    gap = int(36 * u)
    tot = b_like.width + b_sub.width + gap
    y = h * 0.80
    x_like = w / 2 - tot / 2 + b_like.width / 2
    x_sub = w / 2 + tot / 2 - b_sub.width / 2

    def pulse(tc):  # kurzes Eindrücken beim Klick
        k = (t - tc) / 0.25
        return 1 - 0.12 * math.sin(math.pi * k) if 0 <= k <= 1 else 1.0
    s1, a1 = appear(t, 0.35, 0, d)
    s2, a2 = appear(t, 0.5, 0, d)
    paste_scaled(layer, b_like, (x_like, y), s1 * pulse(t_like), a1)
    paste_scaled(layer, b_sub, (x_sub, y), s2 * pulse(t_sub), a2)

    # Mauszeiger
    if 0.6 < t < t_sub + 0.7 and t < d - 0.3:
        p0 = (w * 0.62, h * 0.98)
        p1 = (x_like + b_like.width * 0.15, y + 10 * u)
        p2 = (x_sub + b_sub.width * 0.15, y + 10 * u)
        if t < t_like:
            k = ease_out((t - 0.6) / max(0.1, t_like - 0.6))
            cx, cy = p0[0] + (p1[0] - p0[0]) * k, p0[1] + (p1[1] - p0[1]) * k
        elif t < t_like + 0.3:
            cx, cy = p1
        else:
            k = ease_out((t - t_like - 0.3) / max(0.1, t_sub - t_like - 0.3))
            cx, cy = p1[0] + (p2[0] - p1[0]) * k, p1[1] + (p2[1] - p1[1]) * k
        sz = 46 * u
        pts = [(0, 0), (0, 1.0), (0.27, 0.76), (0.45, 1.12), (0.6, 1.05), (0.42, 0.7), (0.75, 0.7)]
        poly = [(cx + x * sz, cy + y_ * sz) for x, y_ in pts]
        dr = ImageDraw.Draw(layer)
        dr.polygon(poly, fill=WEISS, outline=TINTE, width=max(2, int(3 * u)))


# Zeichner, die nur eine Ebene über dem Bild brauchen
LAYER_DRAWERS = {"steps": draw_steps, "cards": draw_cards, "tags": draw_tags, "scores": draw_scores,
                 "headline": draw_headline, "checklist": draw_checklist, "endcard": draw_endcard,
                 "bigwords": draw_bigwords, "pill": draw_pill, "poof": draw_poof,
                 "clothesline": draw_clothesline, "typewriter": draw_typewriter, "quote": draw_quote,
                 "repeat": draw_repeat, "wordswap": draw_wordswap, "label": draw_label, "quotepill": draw_quotepill,
                 "number": draw_number, "name": draw_name, "stickers": draw_stickers, "buzzword": draw_buzzword,
                 "outro": draw_outro}


def render_frame(frame: Image.Image, it: dict, t: float, d: float, ctx: Ctx, mask: Image.Image | None) -> Image.Image:
    """Ein Bild des Effekts. frame: RGB-Bild des Videos in diesem Moment. mask: Person (L, 255 = Carina)."""
    typ = it.get("type", "headline")
    place = it.get("place", "scene")
    try:  # Größe, die Carina mit dem Schieberegler eingestellt hat
        ctx.u = ctx.base_u * max(0.4, min(2.5, float(it.get("scale") or 1)))
    except (TypeError, ValueError):
        ctx.u = ctx.base_u
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
            if typ == "clothesline" and mask is not None:
                out = Image.composite(base, out, mask)  # Carina steht VOR der Leine
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

    if typ == "statement":
        return draw_statement(base, ctx, it, t, d).convert("RGB")
    if typ == "switch":
        return draw_switch(base, ctx, it, t, d, mask).convert("RGB")
    if typ == "whip":
        return draw_whip(base, ctx, it, t, d).convert("RGB")
    if typ == "flash":
        return draw_flash(base, ctx, it, t, d, mask).convert("RGB")
    if typ == "vanish":
        return draw_vanish(base, ctx, it, t, d, mask).convert("RGB")
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
    if typ == "sticker":
        return draw_sticker(base, ctx, it, t, d, mask).convert("RGB")
    if typ == "counter":
        return draw_counter(base, ctx, it, t, d, mask).convert("RGB")
    if typ == "ghost":
        return draw_ghost(base, ctx, it, t, d, mask).convert("RGB")
    if typ == "lighttrail":
        return draw_lighttrail(base, ctx, it, t, d, mask).convert("RGB")
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


def with_placeholders(it: dict) -> dict:
    """Für die Vorschau: leere Texte mit Beispieltext füllen, damit man den Stil sieht."""
    it = dict(it)
    if not (it.get("title") or "").strip() and it.get("type") not in ("poof", "glow", "lighttrail", "ghost", "whip",
                                                                       "vanish", "flash", "sticker", "bigwords",
                                                                       "outro"):
        it["title"] = {"counter": "120|Tage", "behind": "TEXT", "switch": "YOUR HEADLINE", "number": "Burnout|×3",
                       "name": "Carina Dorca|Stress- & Burnout-Coach", "buzzword": "Burnout",
                       "statement": "YOUR SHORT LINE.", "quote": "\u201eyour quote\u201c",
                       "repeat": "Don't forget to try again", "wordswap": "trust the timing of your life even when it feels"
                       }.get(it.get("type"), "Dein *Text*|hier")
    if not it.get("items") and it.get("type") == "wordswap":
        it["items"] = ["heavy", "slow", "uncertain"]
    if not it.get("items") and it.get("type") in ("steps", "cards", "tags", "scores", "checklist", "clothesline",
                                                  "endcard", "stickers"):
        it["items"] = ["Punkt 1|7", "Punkt 2|5", "Punkt 3|8"] if it.get("type") != "endcard" else ["Kommentiere RUHE"]
    return it


def preview_png(it: dict, w: int, h: int, face_box, frame: Image.Image | None, out: Path,
                segmenter: Segmenter | None = None, stills: dict | None = None) -> None:
    """Standbild des Effekts (für die Vorschau in der App), ca. bei 75 % der Dauer.
    Leere Texte werden für die Vorschau mit Beispieltext gefüllt, damit man den Stil sieht."""
    it = with_placeholders(it)
    d = max(1.0, it["end"] - it["start"])
    ctx = Ctx(w, h, face_box, it.get("_words") or [{"w": "Beispiel", "s": 0, "e": 99}])
    ctx.stills = stills or {}
    frame = frame or Image.new("RGB", (w, h), (90, 90, 90))
    mask = segmenter.mask(frame) if (segmenter and it.get("type") in NEEDS_MASK) else None
    t = 0.3 if it.get("type") == "poof" else d * 0.75  # Puff: im dichtesten Moment zeigen
    render_frame(frame, it, t, d, ctx, mask).save(out)
