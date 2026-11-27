"""Animated stickers (group "S") – CapCut-style stickers drawn from scratch in Carina's colours (Nov 2026).

No CapCut sticker images are used; every sticker is our own vector drawing. Colour dots pick the colour, the
size slider and position buttons work. Title = optional text (e.g. countdown start, label).

  s_circle     hand-drawn circle draws itself around a spot (+ optional label)
  s_arrow      hand-drawn curved arrow draws itself and bobs (+ optional label)
  s_countdown  3 · 2 · 1 in a ring (title = start number)
  s_hearts     little hearts float up
  s_sparkles   twinkling sparkles
  s_check      tick in a circle draws itself (+ optional label)
  s_cross      X in a circle (wrong / don't)
  s_bell       notification bell rings with a red dot
  s_emoji      round smiley face (title: happy | wow | sad | love | wink)
  s_question   bouncing question marks
  s_lightning  lightning bolt flashes
  s_censor     pixel mosaic box over part of the video (position buttons place it)
"""
from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw, ImageFilter

from . import fx
from .fx_text import ACCENT, INK, LILAC, PINK, PLUM, RED, WHITE, YELLOW, shadow

S = 2   # supersampling for smooth lines


def col_of(it, default):
    return ACCENT.get(it.get("color") or "", default)


def _label(it) -> str:
    return (it.get("title") or "").replace("|", " ").strip()


def _out(t, d):
    return min(1.0, max(0.0, (d - t) / 0.25))


def _center(ctx):
    return ctx.w / 2, ctx.h * 0.45


def _canvas(ctx):
    return Image.new("RGBA", (ctx.w * S, ctx.h * S), (0, 0, 0, 0))


def _down(img, ctx):
    return img.resize((ctx.w, ctx.h), Image.LANCZOS)


def _fade(layer, a):
    if a < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * a)))
    return layer


def _compose(base, layer):
    out = base.copy()
    out.alpha_composite(layer)
    return out


def _poly(dr, pts, col, width):
    if len(pts) > 1:
        dr.line([(x * S, y * S) for x, y in pts], fill=col, width=int(width * S), joint="curve")
        r = width * S / 2
        for x, y in (pts[0], pts[-1]):
            dr.ellipse((x * S - r, y * S - r, x * S + r, y * S + r), fill=col)


def _text_under(layer_dr, ctx, txt, x, y, col):
    if not txt:
        return
    f = fx.font("hand", int(70 * ctx.u * S))
    layer_dr.text((x * S, y * S), txt, font=f, fill=col, anchor="mm")


def draw_circle(base, ctx, it, t, d, mask):
    u = ctx.u
    col = col_of(it, RED) + (255,)
    cx, cy = _center(ctx)
    rx, ry = 190 * u, 120 * u
    p = fx.ease_out(t / 0.6)
    n = int(70 * p)
    pts = []
    for i in range(n + 1):
        a = -2.0 + i / 70 * (2 * math.pi + 0.5)
        wob = 1 + 0.05 * math.sin(i * 0.5)
        pts.append((cx + rx * wob * math.cos(a), cy + ry * wob * math.sin(a) + i * 0.15 * u))
    img = _canvas(ctx)
    dr = ImageDraw.Draw(img)
    _poly(dr, pts, col, 9 * u)
    if p > 0.9:
        _text_under(dr, ctx, _label(it), cx, cy + ry + 60 * u, col)
    return _compose(base, _fade(_down(img, ctx), _out(t, d)))


def draw_arrow(base, ctx, it, t, d, mask):
    u = ctx.u
    col = col_of(it, RED) + (255,)
    cx, cy = _center(ctx)
    bob = math.sin(t * 6) * 10 * u if t > 0.6 else 0
    x0, y0 = cx - 160 * u, cy - 150 * u
    x1, y1 = cx + 20 * u, cy + 90 * u + bob
    ctrl = (cx + 140 * u, cy - 170 * u)
    p = fx.ease_out(t / 0.5)
    n = max(2, int(30 * p))
    pts = [((1 - k) ** 2 * x0 + 2 * (1 - k) * k * ctrl[0] + k * k * x1,
            (1 - k) ** 2 * y0 + 2 * (1 - k) * k * ctrl[1] + k * k * y1) for k in (i / 30 for i in range(n))]
    img = _canvas(ctx)
    dr = ImageDraw.Draw(img)
    _poly(dr, pts, col, 10 * u)
    if p > 0.95:
        (xa, ya), (xb, yb) = pts[-3], pts[-1]
        ang = math.atan2(yb - ya, xb - xa)
        for sgn in (-1, 1):
            _poly(dr, [(xb, yb), (xb - 46 * u * math.cos(ang + sgn * 0.55), yb - 46 * u * math.sin(ang + sgn * 0.55))],
                  col, 10 * u)
        _text_under(dr, ctx, _label(it), x0, y0 - 50 * u, col)
    return _compose(base, _fade(_down(img, ctx), _out(t, d)))


def draw_countdown(base, ctx, it, t, d, mask):
    u = ctx.u
    col = col_of(it, LILAC)
    try:
        start = max(1, min(10, int(_label(it) or 3)))
    except ValueError:
        start = 3
    step = max(0.4, (d - 0.3) / start)
    k = int(t // step)
    if k >= start:
        return base
    frac = (t - k * step) / step
    num = str(start - k)
    cx, cy = _center(ctx)
    R = 150 * u
    img = _canvas(ctx)
    dr = ImageDraw.Draw(img)
    dr.ellipse(((cx - R) * S, (cy - R) * S, (cx + R) * S, (cy + R) * S), fill=WHITE + (235,))
    dr.arc(((cx - R) * S, (cy - R) * S, (cx + R) * S, (cy + R) * S), -90, -90 + 360 * frac, fill=col + (255,),
           width=int(16 * u * S))
    s = 1 + 0.25 * (1 - fx.ease_out(frac / 0.3))
    f = fx.font("black", int(170 * u * s * S))
    dr.text((cx * S, cy * S), num, font=f, fill=PLUM + (255,), anchor="mm")
    return _compose(base, _fade(_down(img, ctx), _out(t, d)))


def _heart(dr, x, y, r, fill):
    pts = []
    for i in range(60):
        a = i / 60 * 2 * math.pi
        hx = 16 * math.sin(a) ** 3
        hy = 13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)
        pts.append(((x + hx * r / 16) * S, (y - hy * r / 16) * S))
    dr.polygon(pts, fill=fill)


def draw_hearts(base, ctx, it, t, d, mask):
    u = ctx.u
    col = col_of(it, PINK)
    cx, cy = _center(ctx)
    img = _canvas(ctx)
    dr = ImageDraw.Draw(img)
    rnd = random.Random(5)
    o = _out(t, d)
    for i in range(14):
        t0 = rnd.uniform(0, max(0.1, d - 1.2))
        life = rnd.uniform(1.0, 1.8)
        p = (t - t0) / life
        if not 0 < p < 1:
            continue
        x = cx + rnd.uniform(-220, 220) * u + math.sin(p * 6 + i) * 25 * u
        y = cy + 160 * u - p * 380 * u
        r = rnd.uniform(18, 40) * u * min(1.0, p * 4)
        a = int(255 * min(1.0, (1 - p) * 2.5) * o)
        c = col if i % 3 else WHITE
        _heart(dr, x, y, r, c + (a,))
    return _compose(base, _down(img, ctx))


def _sparkle(dr, x, y, r, fill):
    pts = []
    for i in range(8):
        rr = r if i % 2 == 0 else r * 0.22
        a = i * math.pi / 4
        pts.append(((x + rr * math.cos(a)) * S, (y + rr * math.sin(a)) * S))
    dr.polygon(pts, fill=fill)


def draw_sparkles(base, ctx, it, t, d, mask):
    u = ctx.u
    col = col_of(it, YELLOW)
    cx, cy = _center(ctx)
    img = _canvas(ctx)
    dr = ImageDraw.Draw(img)
    rnd = random.Random(9)
    o = _out(t, d)
    for i in range(12):
        x = cx + rnd.uniform(-300, 300) * u
        y = cy + rnd.uniform(-200, 200) * u
        ph = rnd.uniform(0, 6)
        k = (math.sin(t * 5 + ph) + 1) / 2
        r = (16 + 30 * k) * u * min(1.0, t / 0.3)
        _sparkle(dr, x, y, r, (WHITE if i % 3 == 0 else col) + (int(255 * (0.4 + 0.6 * k) * o),))
    return _compose(base, _down(img, ctx))


def _ring_mark(base, ctx, it, t, d, col, mark):
    u = ctx.u
    cx, cy = _center(ctx)
    R = 110 * u
    s = max(0.01, fx.ease_back(t / 0.3))
    img = _canvas(ctx)
    dr = ImageDraw.Draw(img)
    rr = R * s
    dr.ellipse(((cx - rr) * S, (cy - rr) * S, (cx + rr) * S, (cy + rr) * S), fill=col + (255,))
    p = fx.ease_out((t - 0.25) / 0.35)
    for seg in mark:
        n = max(0, int(len(seg) * p))
        _poly(dr, [(cx + x * R, cy + y * R) for x, y in seg[:max(2, n)]] if n >= 2 else [], WHITE + (255,), 16 * u)
    _text_under(dr, ctx, _label(it), cx, cy + R + 60 * u, col + (255,))
    return _compose(base, _fade(_down(img, ctx), _out(t, d)))


def _line(a, b, n=12):
    return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]


def draw_check(base, ctx, it, t, d, mask):
    tick = _line((-0.45, 0.02), (-0.12, 0.35), 6)[:-1] + _line((-0.12, 0.35), (0.48, -0.3), 12)
    return _ring_mark(base, ctx, it, t, d, col_of(it, (130, 196, 140)), [tick])


def draw_cross(base, ctx, it, t, d, mask):
    return _ring_mark(base, ctx, it, t, d, col_of(it, RED),
                      [_line((-0.38, -0.38), (0.38, 0.38)), _line((0.38, -0.38), (-0.38, 0.38))])


def draw_bell(base, ctx, it, t, d, mask):
    u = ctx.u
    col = col_of(it, YELLOW)
    cx, cy = _center(ctx)
    swing = math.sin(t * 18) * 18 * max(0.0, 1 - t / 1.2) if t < 1.2 else math.sin(t * 18) * 6 * (1 if (t % 2) < 0.4 else 0)
    R = 90 * u
    sp = Image.new("RGBA", (int(3 * R * S), int(3 * R * S)), (0, 0, 0, 0))
    dr = ImageDraw.Draw(sp)
    c = 1.5 * R * S
    dr.pieslice((c - R * S, c - R * S * 1.05, c + R * S, c + R * S * 0.95), 180, 360, fill=col + (255,))
    dr.rectangle((c - R * S, c - 2, c + R * S, c + R * S * 0.55), fill=col + (255,))
    dr.rounded_rectangle((c - R * S * 1.25, c + R * S * 0.5, c + R * S * 1.25, c + R * S * 0.72), int(8 * S * u),
                         fill=col + (255,))
    dr.ellipse((c - R * S * 0.25, c + R * S * 0.68, c + R * S * 0.25, c + R * S * 1.0), fill=col + (255,))
    dr.ellipse((c + R * S * 0.45, c - R * S * 1.0, c + R * S * 1.05, c - R * S * 0.4), fill=RED + (255,))
    sp = sp.rotate(swing, resample=Image.BICUBIC, center=(c, c - R * S))
    sp = sp.resize((sp.width // S, sp.height // S), Image.LANCZOS)
    layer = Image.new("RGBA", (ctx.w, ctx.h), (0, 0, 0, 0))
    fx.paste_scaled(layer, shadow(sp, int(8 * u), int(6 * u)), (cx, cy), max(0.01, fx.ease_back(t / 0.3)), _out(t, d))
    return _compose(base, layer)


def draw_emoji(base, ctx, it, t, d, mask):
    u = ctx.u
    kind = (_label(it) or "happy").lower()
    face = col_of(it, YELLOW)
    cx, cy = _center(ctx)
    R = 120 * u
    s = max(0.01, fx.ease_back(t / 0.35)) * (1 + 0.04 * math.sin(t * 6))
    img = _canvas(ctx)
    dr = ImageDraw.Draw(img)
    r = R * s
    dr.ellipse(((cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S), fill=face + (255,), outline=INK + (255,),
               width=int(5 * u * S))
    ex, ey, er = 0.36 * r, -0.2 * r, 0.11 * r
    blink = kind == "wink"
    for sx in (-1, 1):
        x, y = cx + sx * ex, cy + ey
        if kind == "love":
            _heart(dr, x, y, er * 1.9, RED + (255,))
        elif blink and sx == 1:
            _poly(dr, [(x - er, y), (x + er, y)], INK + (255,), 5 * u)
        else:
            dr.ellipse(((x - er) * S, (y - er * 1.3) * S, (x + er) * S, (y + er * 1.3) * S), fill=INK + (255,))
    mx, my = cx, cy + 0.3 * r
    if kind == "wow":
        dr.ellipse(((mx - 0.16 * r) * S, (my - 0.2 * r) * S, (mx + 0.16 * r) * S, (my + 0.22 * r) * S), fill=INK + (255,))
    elif kind == "sad":
        dr.arc(((mx - 0.4 * r) * S, (my - 0.05 * r) * S, (mx + 0.4 * r) * S, (my + 0.5 * r) * S), 200, 340,
               fill=INK + (255,), width=int(6 * u * S))
    else:
        dr.chord(((mx - 0.45 * r) * S, (my - 0.45 * r) * S, (mx + 0.45 * r) * S, (my + 0.3 * r) * S), 10, 170,
                 fill=INK + (255,))
    for sx in (-1, 1):   # cheeks
        x = cx + sx * 0.55 * r
        dr.ellipse(((x - 0.12 * r) * S, (cy + 0.12 * r) * S, (x + 0.12 * r) * S, (cy + 0.25 * r) * S),
                   fill=PINK + (150,))
    return _compose(base, _fade(_down(img, ctx), _out(t, d)))


def draw_question(base, ctx, it, t, d, mask):
    u = ctx.u
    col = col_of(it, LILAC)
    cx, cy = _center(ctx)
    layer = Image.new("RGBA", (ctx.w, ctx.h), (0, 0, 0, 0))
    o = _out(t, d)
    for i, (dx, dy, sz, rot) in enumerate(((0, 0, 1.0, -8), (-150, 40, 0.6, -20), (150, 30, 0.7, 14))):
        s = max(0.01, fx.ease_back((t - i * 0.15) / 0.3))
        if s <= 0.02:
            continue
        f = fx.font("black", int(200 * u * sz))
        sp = Image.new("RGBA", (int(f.size * 1.2), int(f.size * 1.4)), (0, 0, 0, 0))
        ImageDraw.Draw(sp).text((sp.width / 2, sp.height / 2), "?", font=f, fill=(col if i == 0 else WHITE) + (255,),
                                anchor="mm", stroke_width=max(2, int(5 * u)), stroke_fill=PLUM + (255,))
        bob = math.sin(t * 5 + i) * 10 * u
        fx.paste_scaled(layer, sp, (cx + dx * u, cy + dy * u + bob), s, o, rot)
    return _compose(base, layer)


def draw_lightning(base, ctx, it, t, d, mask):
    u = ctx.u
    col = col_of(it, YELLOW)
    cx, cy = _center(ctx)
    pts = [(0.1, -1), (-0.45, 0.1), (-0.05, 0.1), (-0.2, 1), (0.45, -0.15), (0.05, -0.15), (0.3, -1)]
    R = 150 * u
    img = _canvas(ctx)
    dr = ImageDraw.Draw(img)
    flash = 1.0 if t > 0.5 else (1.0 if int(t * 16) % 2 == 0 else 0.3)
    s = max(0.01, fx.ease_back(t / 0.25))
    dr.polygon([((cx + x * R * s) * S, (cy + y * R * s) * S) for x, y in pts], fill=col + (255,),
               outline=PLUM + (255,))
    layer = _down(img, ctx)
    glow = layer.filter(ImageFilter.GaussianBlur(int(14 * u)))
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    out.alpha_composite(glow)
    out.alpha_composite(layer)
    return _compose(base, _fade(out, flash * _out(t, d)))


def draw_censor(base, ctx, it, t, d, mask):
    """Pixel mosaic over a box of the video. Position buttons: left/center/right, top/middle/bottom."""
    u = ctx.u
    w, h = ctx.w, ctx.h
    bw, bh = int(360 * u * float(it.get("scale") or 1)), int(220 * u * float(it.get("scale") or 1))
    px = {"left": 0.22, "right": 0.78}.get(it.get("pos_x") or "", 0.5)
    py = {"top": 0.22, "bottom": 0.78}.get(it.get("pos_y") or "", 0.5)
    try:
        nx, ny = fx._nudge(it)
    except Exception:  # noqa: BLE001
        nx, ny = 0, 0
    x0 = int(min(max(0, px * w - bw / 2 + nx * w), w - bw))
    y0 = int(min(max(0, py * h - bh / 2 + ny * h), h - bh))
    box = base.crop((x0, y0, x0 + bw, y0 + bh))
    blk = max(4, int(26 * u))
    mos = box.resize((max(1, bw // blk), max(1, bh // blk)), Image.BILINEAR).resize((bw, bh), Image.NEAREST)
    a = _out(t, d) * min(1.0, t / 0.15)
    m = Image.new("L", (bw, bh), int(255 * a))
    out = base.copy()
    out.paste(mos, (x0, y0), m)
    return out


STICKER_TYPES = {
    "s_circle": ("S", "Hand-drawn circle", ("side",)),
    "s_arrow": ("S", "Hand-drawn arrow", ("side",)),
    "s_countdown": ("S", "Countdown 3 · 2 · 1", ("side",)),
    "s_hearts": ("S", "Floating hearts", ("side",)),
    "s_sparkles": ("S", "Sparkles", ("side",)),
    "s_check": ("S", "Tick ✓", ("side",)),
    "s_cross": ("S", "Cross ✗", ("side",)),
    "s_bell": ("S", "Notification bell", ("side",)),
    "s_emoji": ("S", "Smiley face", ("side",)),
    "s_question": ("S", "Question marks", ("side",)),
    "s_lightning": ("S", "Lightning bolt", ("side",)),
    "s_censor": ("S", "Pixel / censor box", ("side",)),
}

STICKER_DESCRIBE = {
    "s_circle": "handgezeichneter Kreis zeichnet sich um eine Stelle (title = kurzes Label optional) – auf etwas zeigen, 2 s",
    "s_arrow": "handgezeichneter Pfeil (title = Label optional) – auf etwas zeigen, 2 s",
    "s_countdown": "Countdown in einem Ring (title = Startzahl, z. B. 3) – vor einer Übung/Auflösung, so lang wie gezählt wird",
    "s_hearts": "Herzchen steigen auf – Liebe, Dankbarkeit, 2–3 s",
    "s_sparkles": "funkelnde Sterne – etwas Schönes/Neues, 2 s",
    "s_check": "Häkchen im Kreis (title = Label optional) – richtig/erledigt, 1,5 s",
    "s_cross": "Kreuz im Kreis (title = Label optional) – falsch/nicht machen, 1,5 s",
    "s_bell": "Glocke klingelt – Abo/Benachrichtigung, 2 s",
    "s_emoji": "Smiley (title = happy|wow|sad|love|wink) – Gefühl, 1,5–2 s",
    "s_question": "hüpfende Fragezeichen – Frage/Verwirrung, 2 s",
    "s_lightning": "Blitz – plötzlicher Stress/Erkenntnis, 1 s",
    "s_censor": "Pixel-Mosaik über einem Bereich (Position wählen) – etwas verdecken, so lang wie nötig",
}

STICKER_DRAWERS = {"s_circle": draw_circle, "s_arrow": draw_arrow, "s_countdown": draw_countdown,
                   "s_hearts": draw_hearts, "s_sparkles": draw_sparkles, "s_check": draw_check, "s_cross": draw_cross,
                   "s_bell": draw_bell, "s_emoji": draw_emoji, "s_question": draw_question,
                   "s_lightning": draw_lightning, "s_censor": draw_censor}
STICKER_MOVABLE = set(STICKER_DRAWERS) - {"s_censor"}   # the censor box places itself (it needs the video pixels)
