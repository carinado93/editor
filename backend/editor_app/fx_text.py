"""Text templates (group "T") – CapCut-style text looks, drawn from scratch in Carina's colours (Nov 2026).

None of CapCut's assets are used: every look is our own drawing (Pillow) with her fonts and colours.
All templates: text from the title field (Enter = new line, "|" = new line too), colour dots choose the accent
colour, size slider + position buttons work (movable), fade/scale out at the end.

  stamp     rubber stamp (SOLD-OUT look): double frame, rough ink, slams in tilted
  badge     starburst badge ("-50 %"), pops in with a spin
  saleblock bold block lines on alternating bars, each line slides in from the side
  neon      glowing neon outline text, flickers on
  bubble    white speech bubble with tail, pops in
  brush     painted brush stroke wipes in, white text on top
  marker    highlighter sweeps behind each line, dark text
  outline   big white text with thick colour outline, words bounce in one after another
  glitch    RGB-split glitch with slice jumps, settles into clean white text
  tape      text on a washi-tape strip, slides down slightly tilted
  sticky    sticky note with handwriting, drops in
  scribble  white text, hand-drawn underline draws itself
  letters   letters pop in one by one
  gradient  lilac→pink gradient title with white edge, rises in
"""
from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import fx

LILAC = (201, 179, 236)
LILAC_DARK = (122, 100, 158)
PLUM = (74, 52, 110)
PINK = (240, 150, 185)
RED = (226, 64, 76)
YELLOW = (250, 226, 140)
WHITE = (255, 253, 249)
INK = (40, 30, 55)

ACCENT = {"white": WHITE, "pink": PINK, "yellow": YELLOW, "lilac": LILAC, "lila": LILAC, "green": (160, 214, 150)}


def accent(it: dict, default) -> tuple:
    return ACCENT.get(it.get("color") or "", default)


def _lines(it: dict, default: str) -> list[str]:
    raw = (it.get("title") or "").replace("*", "").strip() or default
    return [ln.strip() for ln in raw.replace("|", "\n").split("\n") if ln.strip()] or [default]


def _fit(lines: list[str], fname: str, size: int, max_w: float, upper: bool = False):
    """Font size so that the widest line fits max_w (shrinks, never overflows)."""
    txt = [ln.upper() if upper else ln for ln in lines]
    f = fx.font(fname, size) if fname in ("head", "bold", "semi", "serif", "serif_i", "hand", "jost", "black") \
        else _sfont(fname, size)
    while size > 14 and max(f.getlength(t) for t in txt) > max_w:
        size = int(size * 0.92)
        f = f.font_variant(size=size)
    return f, txt


def _sfont(name: str, size: int):
    from . import fx_studio
    return fx_studio.sfont(name, size)


def text_img(lines, f, fill, stroke=0, stroke_fill=None, spacing=1.12, pad=None) -> Image.Image:
    """Centered multi-line text on a tight transparent sprite."""
    pad = pad if pad is not None else int(f.size * 0.25) + stroke
    lh = f.size * spacing
    w = int(max(f.getlength(t) for t in lines) + 2 * pad + 2 * stroke)
    h = int(lh * len(lines) + 2 * pad)
    im = Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for k, t in enumerate(lines):
        d.text((w / 2, pad + lh * (k + 0.5)), t, font=f, fill=fill, anchor="mm",
               stroke_width=stroke, stroke_fill=stroke_fill)
    return im


def shadow(sp: Image.Image, blur: int, off: int, col=PLUM, a: float = 0.45) -> Image.Image:
    pad = blur * 3
    out = Image.new("RGBA", (sp.width + 2 * pad, sp.height + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", sp.size, col + (0,))
    sh.putalpha(sp.getchannel("A").point(lambda v: int(v * a)))
    out.alpha_composite(sh, (pad, pad + off))
    out = out.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(sp, (pad, pad))
    return out


def _cache(ctx, key, build):
    if key not in ctx.cache:
        ctx.cache[key] = build()
    return ctx.cache[key]


def _out(t: float, d: float, dur: float = 0.25) -> float:
    return min(1.0, max(0.0, (d - t) / dur))


def _center(ctx) -> tuple[float, float]:
    return ctx.w / 2, ctx.h * 0.32


def _finish(base, layer):
    out = base.copy()
    out.alpha_composite(layer)
    return out


def _paste(base, ctx, sprite, scale, alpha, rot=0.0, center=None):
    layer = Image.new("RGBA", (ctx.w, ctx.h), (0, 0, 0, 0))
    fx.paste_scaled(layer, sprite, center or _center(ctx), scale, alpha, rot)
    return _finish(base, layer)


def _key(it, name, ctx):
    return ("T", name, it.get("title"), it.get("color"), ctx.u, ctx.w, ctx.h)


# ------------------------------------------------------------------ templates

def draw_stamp(base, ctx, it, t, d, mask):
    u = ctx.u
    col = accent(it, RED)

    def build():
        f, txt = _fit(_lines(it, "SOLD OUT"), "black", int(120 * u), ctx.w * 0.62, upper=True)
        ti = text_img(txt, f, col + (255,), pad=int(26 * u))
        w, h = ti.width + int(40 * u), ti.height + int(30 * u)
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        lw = max(4, int(10 * u))
        dr.rounded_rectangle((lw, lw, w - lw, h - lw), int(14 * u), outline=col + (255,), width=lw)
        dr.rounded_rectangle((3 * lw, 3 * lw, w - 3 * lw, h - 3 * lw), int(8 * u), outline=col + (255,),
                             width=max(2, lw // 3))
        im.alpha_composite(ti, ((w - ti.width) // 2, (h - ti.height) // 2))
        # rough ink: random speckle holes
        rnd = np.random.default_rng(7)
        a = np.asarray(im.getchannel("A")).astype(np.float32)
        noise = rnd.random(a.shape)
        a[noise < 0.09] *= 0.25
        im.putalpha(Image.fromarray(a.astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6)))
        return im.rotate(8, expand=True, resample=Image.BICUBIC)
    sp = _cache(ctx, _key(it, "stamp", ctx), build)
    k = min(1.0, t / 0.18)
    scale = 2.2 - 1.2 * fx.ease_out(k)
    shake = math.sin(t * 90) * 6 * u * max(0.0, 1 - (t - 0.18) / 0.25) if t > 0.18 else 0
    cx, cy = _center(ctx)
    return _paste(base, ctx, sp, scale, min(1.0, k * 1.5) * _out(t, d), 0, (cx + shake, cy))


def _star(n, r_out, r_in, cx, cy, rot=0.0):
    pts = []
    for i in range(2 * n):
        r = r_out if i % 2 == 0 else r_in
        a = math.pi * i / n + rot
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def draw_badge(base, ctx, it, t, d, mask):
    u = ctx.u
    col = accent(it, PINK)

    def build():
        R = int(170 * u)
        f, txt = _fit(_lines(it, "-50 %"), "black", int(90 * u), R * 1.3, upper=True)
        S = 2
        im = Image.new("RGBA", (2 * R * S, 2 * R * S), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.polygon(_star(16, R * S * 0.98, R * S * 0.84, R * S, R * S), fill=col + (255,))
        dr.ellipse((R * S * 0.22, R * S * 0.22, R * S * 1.78, R * S * 1.78), outline=WHITE + (230,), width=4 * S)
        im = im.resize((2 * R, 2 * R), Image.LANCZOS)
        ti = text_img(txt, f, WHITE + (255,), stroke=max(1, int(2 * u)), stroke_fill=PLUM + (160,))
        im.alpha_composite(ti, (R - ti.width // 2, R - ti.height // 2))
        return shadow(im, int(10 * u), int(8 * u))
    sp = _cache(ctx, _key(it, "badge", ctx), build)
    k = t / 0.4
    s = max(0.01, fx.ease_back(k))
    rot = -30 * (1 - fx.ease_out(k)) - 8 + 2 * math.sin(t * 2.2)
    return _paste(base, ctx, sp, s * (1 + 0.03 * math.sin(t * 5)), min(1.0, k * 2) * _out(t, d), rot)


def draw_saleblock(base, ctx, it, t, d, mask):
    u = ctx.u
    col = accent(it, LILAC)
    lines = _lines(it, "SALE\nEVERY\nITEM")
    f, txt = _fit(lines, "black", int(96 * u), ctx.w * 0.66, upper=True)
    layer = Image.new("RGBA", (ctx.w, ctx.h), (0, 0, 0, 0))
    lh = int(f.size * 1.32)
    cx, cy = _center(ctx)
    y0 = cy - lh * len(txt) / 2
    o = _out(t, d)
    for k, ln in enumerate(txt):
        bg, fg = (col, WHITE) if k % 2 == 0 else (WHITE, PLUM if col != WHITE else LILAC_DARK)

        def build(ln=ln, bg=bg, fg=fg):
            tw = f.getlength(ln)
            im = Image.new("RGBA", (int(tw + 60 * u), lh - int(8 * u)), bg + (255,))
            ImageDraw.Draw(im).text((im.width / 2, im.height / 2), ln, font=f, fill=fg + (255,), anchor="mm")
            return im
        sp = _cache(ctx, _key(it, f"sale{k}", ctx) + (ln,), build)
        p = fx.ease_out((t - k * 0.12) / 0.35)
        if p <= 0:
            continue
        side = -1 if k % 2 == 0 else 1
        x = cx + side * (1 - p) * ctx.w * 0.6
        y = y0 + lh * (k + 0.5)
        fx.paste_scaled(layer, sp, (x, y), 1.0, o, -3 if k % 2 == 0 else 2)
    return _finish(base, layer)


def draw_neon(base, ctx, it, t, d, mask):
    u = ctx.u
    col = accent(it, PINK)

    def build():
        f, txt = _fit(_lines(it, "open late"), "semi", int(110 * u), ctx.w * 0.75)
        core = text_img(txt, f, (0, 0, 0, 0), stroke=max(2, int(4 * u)), stroke_fill=WHITE + (255,),
                        pad=int(60 * u))
        glow = Image.new("RGBA", core.size, col + (0,))
        glow.putalpha(core.getchannel("A"))
        g1 = glow.filter(ImageFilter.GaussianBlur(int(18 * u)))
        g2 = glow.filter(ImageFilter.GaussianBlur(int(6 * u)))
        im = Image.new("RGBA", core.size, (0, 0, 0, 0))
        for g in (g1, g1, g2):
            im.alpha_composite(g)
        tint = Image.new("RGBA", core.size, tuple(min(255, c + 40) for c in col) + (0,))
        tint.putalpha(core.getchannel("A"))
        im.alpha_composite(tint)
        return im
    sp = _cache(ctx, _key(it, "neon", ctx), build)
    rnd = random.Random(int(t * 30))
    flick = 1.0 if t > 0.7 else (0.15 if rnd.random() < 0.45 else 1.0) * min(1.0, t / 0.2)
    return _paste(base, ctx, sp, 1.0, flick * _out(t, d))


def draw_bubble(base, ctx, it, t, d, mask):
    u = ctx.u
    col = accent(it, WHITE)

    def build():
        f, txt = _fit(_lines(it, "Wait… what?"), "bold", int(70 * u), ctx.w * 0.6)
        ti = text_img(txt, f, PLUM + (255,), pad=int(34 * u))
        w, h = ti.width + int(20 * u), ti.height + int(10 * u)
        tail = int(46 * u)
        im = Image.new("RGBA", (w, h + tail), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((0, 0, w - 1, h - 1), int(min(h / 2, 60 * u)), fill=col + (255,))
        dr.polygon([(w * 0.22, h - 4), (w * 0.38, h - 4), (w * 0.16, h + tail)], fill=col + (255,))
        im.alpha_composite(ti, ((w - ti.width) // 2, (h - ti.height) // 2))
        return shadow(im, int(12 * u), int(8 * u))
    sp = _cache(ctx, _key(it, "bubble", ctx), build)
    s, a = fx.appear(t, 0, 0, d)
    return _paste(base, ctx, sp, max(0.01, s), a)


def _brush_shape(w, h, seed=3):
    rnd = random.Random(seed)
    top, bot = [], []
    n = 30
    for i in range(n + 1):
        x = w * i / n
        tap = min(1.0, i / 3, (n - i) / 3) * 0.7 + 0.3
        top.append((x, h * 0.5 - h * 0.46 * tap + rnd.uniform(-h * 0.05, h * 0.05)))
        bot.append((x, h * 0.5 + h * 0.46 * tap + rnd.uniform(-h * 0.05, h * 0.05)))
    return top + bot[::-1]


def draw_brush(base, ctx, it, t, d, mask):
    u = ctx.u
    col = accent(it, LILAC)

    def build():
        f, txt = _fit(_lines(it, "self care"), "black", int(96 * u), ctx.w * 0.7)
        ti = text_img(txt, f, WHITE + (255,), pad=int(20 * u))
        w, h = int(ti.width * 1.18), int(ti.height * 1.05)
        br = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(br).polygon(_brush_shape(w, h), fill=col + (245,))
        # dry-brush streaks
        a = np.asarray(br.getchannel("A")).astype(np.float32)
        rnd = np.random.default_rng(3)
        streak = (rnd.random((h, 1)) < 0.12) * rnd.uniform(0.3, 0.7, (h, 1))
        a *= 1 - streak * (np.linspace(0, 1, w)[None, :] > 0.85)
        br.putalpha(Image.fromarray(a.astype(np.uint8)))
        return br, ti
    br, ti = _cache(ctx, _key(it, "brush", ctx), build)
    p = fx.ease_out(t / 0.45)
    o = _out(t, d)
    sp = Image.new("RGBA", br.size, (0, 0, 0, 0))
    if p > 0:
        cw = max(1, int(br.width * p))
        sp.alpha_composite(br.crop((0, 0, cw, br.height)), (0, 0))
    ta = min(1.0, max(0.0, (t - 0.25) / 0.25))
    if ta > 0:
        tl = ti.copy()
        tl.putalpha(tl.getchannel("A").point(lambda v: int(v * ta)))
        sp.alpha_composite(tl, ((br.width - ti.width) // 2, (br.height - ti.height) // 2))
    return _paste(base, ctx, sp, 1.0, o, -2)


def draw_marker(base, ctx, it, t, d, mask):
    u = ctx.u
    col = accent(it, YELLOW)
    f, txt = _fit(_lines(it, "das ist wichtig"), "bold", int(80 * u), ctx.w * 0.72)
    lh = int(f.size * 1.35)
    cx, cy = _center(ctx)
    layer = Image.new("RGBA", (ctx.w, ctx.h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)
    o = _out(t, d)
    y0 = cy - lh * len(txt) / 2
    for k, ln in enumerate(txt):
        tw = f.getlength(ln)
        x0 = cx - tw / 2 - 18 * u
        y = y0 + lh * (k + 0.5)
        p = fx.ease_out((t - k * 0.25) / 0.4)
        if p <= 0:
            continue
        x1 = x0 + (tw + 36 * u) * p
        dr.rounded_rectangle((x0, y - f.size * 0.42, x1, y + f.size * 0.5), int(10 * u), fill=col + (int(235 * o),))
        dr.text((cx, y), ln, font=f, fill=INK + (int(255 * o * min(1.0, p * 2)),), anchor="mm")
    return _finish(base, layer)


def draw_outline(base, ctx, it, t, d, mask):
    u = ctx.u
    col = accent(it, LILAC)
    lines = _lines(it, "Burnout ist real")
    f, txt = _fit(lines, "black", int(118 * u), ctx.w * 0.8, upper=True)
    sw = max(3, int(9 * u))
    layer = Image.new("RGBA", (ctx.w, ctx.h), (0, 0, 0, 0))
    cx, cy = _center(ctx)
    lh = f.size * 1.12
    o = _out(t, d)
    n = 0
    y0 = cy - lh * len(txt) / 2
    for k, ln in enumerate(txt):
        words = ln.split()
        space = f.getlength(" ")
        widths = [f.getlength(wd) for wd in words]
        x = cx - (sum(widths) + space * (len(words) - 1)) / 2
        for wd, ww in zip(words, widths):
            sp = _cache(ctx, _key(it, "ol", ctx) + (wd,),
                        lambda wd=wd: shadow(text_img([wd], f, WHITE + (255,), stroke=sw, stroke_fill=col + (255,)),
                                             int(8 * u), int(7 * u)))
            s = fx.ease_back((t - n * 0.12) / 0.3)
            if s > 0.01:
                fx.paste_scaled(layer, sp, (x + ww / 2, y0 + lh * (k + 0.5)), s, o)
            x += ww + space
            n += 1
    return _finish(base, layer)


def draw_glitch(base, ctx, it, t, d, mask):
    u = ctx.u
    col = accent(it, PINK)

    def build():
        f, txt = _fit(_lines(it, "SYSTEM ERROR"), "black", int(110 * u), ctx.w * 0.8, upper=True)
        return text_img(txt, f, WHITE + (255,), pad=int(40 * u))
    sp = _cache(ctx, _key(it, "glitch", ctx), build)
    o = _out(t, d)
    calm = t > 0.75 and not (1.6 < (t % 2.2) < 1.72)
    layer = Image.new("RGBA", (ctx.w, ctx.h), (0, 0, 0, 0))
    cx, cy = _center(ctx)
    x0, y0 = int(cx - sp.width / 2), int(cy - sp.height / 2)
    if calm:
        layer.alpha_composite(shadow(sp, int(6 * u), int(5 * u)), (x0 - int(18 * u), y0 - int(18 * u) + int(5 * u)))
    else:
        rnd = random.Random(int(t * 24))
        off = int(rnd.uniform(6, 16) * u)
        a = sp.getchannel("A")
        for c, dx in ((col, -off), ((120, 220, 255), off)):
            ch = Image.new("RGBA", sp.size, c + (0,))
            ch.putalpha(a.point(lambda v: int(v * 0.85)))
            layer.alpha_composite(ch, (x0 + dx, y0))
        sl = sp.copy()
        for _ in range(4):   # slice jumps
            yy = rnd.randint(0, max(1, sp.height - 10))
            hh = rnd.randint(4, max(5, sp.height // 6))
            band = sl.crop((0, yy, sp.width, yy + hh))
            sl.paste((0, 0, 0, 0), (0, yy, sp.width, yy + hh))
            layer.alpha_composite(band, (x0 + rnd.randint(-int(30 * u), int(30 * u)), y0 + yy))
        layer.alpha_composite(sl, (x0, y0))
    if o < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * o)))
    return _finish(base, layer)


def draw_tape(base, ctx, it, t, d, mask):
    u = ctx.u
    col = accent(it, PINK)

    def build():
        f, txt = _fit(_lines(it, "note to self"), "hand", int(96 * u), ctx.w * 0.6)
        ti = text_img(txt, f, INK + (255,), pad=int(18 * u))
        w, h = ti.width + int(80 * u), ti.height + int(16 * u)
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        z = int(12 * u)
        pts = [(0, 0)] + [(w, 0)] + [(w - (z if i % 2 else 0), h * i / 8) for i in range(9)] + \
              [(0 + (z if i % 2 else 0), h * (8 - i) / 8) for i in range(9)]
        ImageDraw.Draw(im).polygon(pts, fill=col + (215,))
        # faint stripes
        dr = ImageDraw.Draw(im)
        for x in range(0, w, int(28 * u) or 1):
            dr.line((x, 0, x - h, h), fill=WHITE + (40,), width=max(1, int(6 * u)))
        im.alpha_composite(ti, ((w - ti.width) // 2, (h - ti.height) // 2))
        return shadow(im, int(6 * u), int(4 * u), a=0.25)
    sp = _cache(ctx, _key(it, "tape", ctx), build)
    p = fx.ease_out(t / 0.35)
    cx, cy = _center(ctx)
    return _paste(base, ctx, sp, 1.0, min(1.0, p * 2) * _out(t, d), 3, (cx, cy - (1 - p) * 60 * u))


def draw_sticky(base, ctx, it, t, d, mask):
    u = ctx.u
    col = accent(it, YELLOW)

    def build():
        S = int(330 * u)
        f, txt = _fit(_lines(it, "trink Wasser"), "hand", int(84 * u), S * 0.82)
        while len(txt) * f.size * 1.1 > S * 0.8 and f.size > 14:
            f = f.font_variant(size=int(f.size * 0.92))
        im = Image.new("RGBA", (S, S), col + (255,))
        dr = ImageDraw.Draw(im)
        dr.rectangle((0, 0, S, int(S * 0.12)), fill=tuple(int(c * 0.93) for c in col) + (255,))
        ti = text_img(txt, f, INK + (255,), spacing=1.05, pad=4)
        im.alpha_composite(ti, ((S - ti.width) // 2, int(S * 0.56 - ti.height / 2)))
        return shadow(im, int(14 * u), int(12 * u), col=(60, 40, 30), a=0.35)
    sp = _cache(ctx, _key(it, "sticky", ctx), build)
    p = t / 0.45
    s = max(0.01, fx.ease_back(p))
    rot = 12 * (1 - fx.ease_out(p)) - 4
    cx, cy = _center(ctx)
    return _paste(base, ctx, sp, s, min(1.0, p * 2) * _out(t, d), rot, (cx, cy - (1 - fx.ease_out(p)) * 80 * u))


def draw_scribble(base, ctx, it, t, d, mask):
    u = ctx.u
    col = accent(it, PINK)
    f, txt = _fit(_lines(it, "nicht vergessen"), "black", int(100 * u), ctx.w * 0.75)

    def build():
        return shadow(text_img(txt, f, WHITE + (255,)), int(8 * u), int(6 * u))
    sp = _cache(ctx, _key(it, "scr", ctx), build)
    cx, cy = _center(ctx)
    o = _out(t, d)
    s, a = fx.appear(t, 0, 0, d, pop=0.3)
    out = _paste(base, ctx, sp, max(0.01, s), a)
    # hand-drawn underline (two wavy passes) draws itself
    p = fx.ease_out((t - 0.3) / 0.5)
    if p > 0:
        layer = Image.new("RGBA", (ctx.w, ctx.h), (0, 0, 0, 0))
        dr = ImageDraw.Draw(layer)
        tw = max(f.getlength(x) for x in txt)
        y = cy + sp.height / 2 - 30 * u
        x0 = cx - tw / 2
        pts = [(x0 + tw * i / 40, y + math.sin(i * 0.9) * 5 * u + (i / 40) * 6 * u) for i in range(int(41 * p))]
        if len(pts) > 1:
            dr.line(pts, fill=col + (int(255 * o),), width=max(3, int(9 * u)), joint="curve")
        p2 = fx.ease_out((t - 0.55) / 0.45)
        pts2 = [(x0 + tw * 0.1 + tw * 0.85 * i / 40, y + 16 * u + math.sin(i * 0.7 + 1) * 4 * u)
                for i in range(int(41 * p2))]
        if len(pts2) > 1:
            dr.line(pts2, fill=col + (int(220 * o),), width=max(2, int(6 * u)), joint="curve")
        out.alpha_composite(layer)
    return out


def draw_letters(base, ctx, it, t, d, mask):
    u = ctx.u
    col = accent(it, WHITE)
    f, txt = _fit(_lines(it, "Guten Morgen"), "black", int(110 * u), ctx.w * 0.8)
    layer = Image.new("RGBA", (ctx.w, ctx.h), (0, 0, 0, 0))
    cx, cy = _center(ctx)
    lh = f.size * 1.15
    o = _out(t, d)
    n = 0
    total = sum(len(x) for x in txt)
    step = min(0.06, 0.8 / max(1, total))
    y0 = cy - lh * len(txt) / 2
    for k, ln in enumerate(txt):
        x = cx - f.getlength(ln) / 2
        for ch in ln:
            cw = f.getlength(ch)
            if ch.strip():
                sp = _cache(ctx, _key(it, "let", ctx) + (ch,),
                            lambda ch=ch: shadow(text_img([ch], f, col + (255,), pad=int(10 * u)), int(5 * u), int(5 * u)))
                s = fx.ease_back((t - n * step) / 0.28)
                if s > 0.01:
                    fx.paste_scaled(layer, sp, (x + cw / 2, y0 + lh * (k + 0.5) - (1 - min(1, s)) * 30 * u), s, o)
            x += cw
            n += 1
    return _finish(base, layer)


def draw_gradient(base, ctx, it, t, d, mask):
    u = ctx.u
    col = accent(it, PINK)

    def build():
        f, txt = _fit(_lines(it, "Not All At Once"), "black", int(120 * u), ctx.w * 0.8)
        m = text_img(txt, f, (255, 255, 255, 255))
        w, h = m.size
        g = np.zeros((h, w, 4), np.uint8)
        x = np.linspace(0, 1, w)[None, :, None]
        a, b = np.array(LILAC, float), np.array(col if col != LILAC else PINK, float)
        g[..., :3] = (a * (1 - x) + b * x).astype(np.uint8)
        g[..., 3] = np.asarray(m.getchannel("A"))
        im = Image.fromarray(g, "RGBA")
        edge = text_img(txt, f, (0, 0, 0, 0), stroke=max(2, int(4 * u)), stroke_fill=WHITE + (255,))
        out = Image.new("RGBA", edge.size, (0, 0, 0, 0))
        out.alpha_composite(edge)
        out.alpha_composite(im, ((edge.width - w) // 2, (edge.height - h) // 2))
        return shadow(out, int(10 * u), int(8 * u))
    sp = _cache(ctx, _key(it, "grad", ctx), build)
    p = fx.ease_out(t / 0.5)
    cx, cy = _center(ctx)
    return _paste(base, ctx, sp, 0.92 + 0.08 * p, p * _out(t, d), 0, (cx, cy + (1 - p) * 50 * u))


TEXT_TYPES = {
    "t_stamp": ("T", "Stamp (SOLD OUT look)", ("side",)),
    "t_badge": ("T", "Starburst badge (-50 %)", ("side",)),
    "t_saleblock": ("T", "Block lines (SALE / EVERY / ITEM)", ("side",)),
    "t_neon": ("T", "Neon glow", ("side",)),
    "t_bubble": ("T", "Speech bubble", ("side",)),
    "t_brush": ("T", "Brush stroke", ("side",)),
    "t_marker": ("T", "Highlighter marker", ("side",)),
    "t_outline": ("T", "Big outline words (bounce)", ("side",)),
    "t_glitch": ("T", "Glitch", ("side",)),
    "t_tape": ("T", "Washi tape", ("side",)),
    "t_sticky": ("T", "Sticky note", ("side",)),
    "t_scribble": ("T", "Scribble underline", ("side",)),
    "t_letters": ("T", "Letters pop in", ("side",)),
    "t_gradient": ("T", "Gradient title", ("side",)),
}

TEXT_DESCRIBE = {
    "t_stamp": "Stempel-Text (wie SOLD OUT), knallt schräg rein – für ein klares Urteil, 2–3 s",
    "t_badge": "runder Zacken-Button mit 1–3 Wörtern/Zahl (z. B. '-50 %', 'NEU') – Zahl/Angebot, 2–3 s",
    "t_saleblock": "2–4 kurze Zeilen auf Balken, fahren abwechselnd rein (Zeilen mit Enter) – Aufzählung, 2–4 s",
    "t_neon": "Neon-Leuchtschrift flackert an – Stimmung/Nacht, 2–3 s",
    "t_bubble": "Sprechblase mit kurzem Satz – Gedanke/Frage, 2–3 s",
    "t_brush": "Pinselstrich wischt rein, weißer Text darauf – Kernbegriff, 2–3 s",
    "t_marker": "Textmarker läuft hinter jede Zeile – wichtiger Satz, 2–4 s",
    "t_outline": "große Wörter mit farbigem Rand hüpfen nacheinander rein – Hook/Aussage, 2–3 s",
    "t_glitch": "Glitch-Text (Fehler-Look) – Überforderung/Stress, 1–2 s",
    "t_tape": "Text auf Washi-Tape – Notiz/Tipp, 2–3 s",
    "t_sticky": "Klebezettel mit Handschrift – Erinnerung/Tipp, 2–3 s",
    "t_scribble": "Text mit handgezeichneter Unterstreichung – Betonung, 2–3 s",
    "t_letters": "Buchstaben poppen einzeln rein – Begrüßung/Titel, 2–3 s",
    "t_gradient": "Titel mit Lila→Rosa-Verlauf – Kapitel/Titel, 2–3 s",
}

TEXT_DRAWERS = {"t_stamp": draw_stamp, "t_badge": draw_badge, "t_saleblock": draw_saleblock, "t_neon": draw_neon,
                "t_bubble": draw_bubble, "t_brush": draw_brush, "t_marker": draw_marker, "t_outline": draw_outline,
                "t_glitch": draw_glitch, "t_tape": draw_tape, "t_sticky": draw_sticky, "t_scribble": draw_scribble,
                "t_letters": draw_letters, "t_gradient": draw_gradient}
