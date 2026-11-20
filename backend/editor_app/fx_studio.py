"""Studio effects from the "Day in my life" reel (Nov 2026), trained with Carina in claude.ai.

Every effect is drawn frame by frame (Pillow) over the running video, like the other effects in fx.py.
Time t runs from 0 to d (effect length in seconds). Sizes scale with ctx.u (1.0 = 1080 px short side).

Group "E" in the app ("Studio – day in my life"):
  battery     tall "brain battery" drains 40 % → 3 % (lilac → red) + iPhone-style "Low Battery" popup
  codechips   dark code chips type themselves around Carina (items = snippets)
  nightfall   room gets a night tint, sun sets, moon rises, time counts (title "18:00|21:47|wait… it's night?")
  logoff      glitch on the picture, then a lilac pill "logging off…" with animated dots
  sportpill   lilac pill top left with ticking stopwatch (title "ZUMBA|30 min")
  ringtimer   meditation ring timer counts down + title written on (title "meditation time|30")
  savedcard   video dims, lilac "WORKOUT SAVED" card with stats, cursor clicks the button (title "WORKOUT SAVED|RESUME: WORK")
  subscribe   lilac fills the screen from the centre, "a subscribe or like" + buttons clicked, then opens again
  heartcover  "THANK YOU" behind Carina, then a lilac heart grows from her face and covers the screen
  sharestats  Strava-style ending: blurred dark background, Carina cut out, phone "Share Activity" with day stats,
              tap on Story, the stats sticker flies next to her (items = "Label|value")

Approved defaults (colours, timings) come from Carina's edits; see .claude/skills/ in this repo.
"""
from __future__ import annotations

import functools
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import fx

LILAC = (201, 179, 236)
LILAC_BG = (214, 198, 240)
LILAC_DARK = (122, 100, 158)
PLUM = (74, 52, 110)
WHITE = (255, 255, 255)
RED = (235, 64, 70)
YELLOW = (255, 214, 92)
DARK = (22, 18, 30)

_FILES = {"titan": "TitanOne-Regular.ttf", "fredoka": "Fredoka-SemiBold.ttf", "fredoka_b": "Fredoka-Bold.ttf",
          "inter_b": "Inter-ExtraBold.ttf", "inter_l": "Inter-Light.ttf"}


@functools.lru_cache(maxsize=256)
def sfont(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = fx.FONTS / _FILES.get(name, "")
    if name in _FILES and path.exists():
        return ImageFont.truetype(str(path), max(8, size))
    return fx.font("head", size)  # fallback: Poppins


def ease(x: float) -> float:
    return fx.ease_out(x)


def ease_in(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x ** 3


def back(x: float) -> float:
    return max(0.01, fx.ease_back(x))


def _parts(text: str, n: int, defaults: list[str]) -> list[str]:
    p = [s.strip() for s in (text or "").split("|")]
    return [(p[k] if k < len(p) and p[k] else defaults[k]) for k in range(n)]


def _pop_text(layer: Image.Image, txt: str, f, center, u_scale: float, alpha: float, col, shadow=PLUM, sh_a=0.55):
    if not txt or alpha <= 0:
        return
    b = f.getbbox(txt)
    pad = 30
    im = Image.new("RGBA", (b[2] - b[0] + 2 * pad, b[3] - b[1] + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - b[0], pad - b[1]), txt, font=f, fill=col + (255,))
    if shadow:
        sh = Image.new("RGBA", im.size, shadow + (0,))
        sh.putalpha(im.getchannel("A").point(lambda v: int(v * sh_a)))
        sh = sh.filter(ImageFilter.GaussianBlur(6))
        out = Image.new("RGBA", (im.width + 8, im.height + 10), (0, 0, 0, 0))
        out.alpha_composite(sh, (4, 7))
        out.alpha_composite(im, (0, 0))
        im = out
    fx.paste_scaled(layer, im, center, u_scale, alpha)


def _pill(text: str, f, bg=LILAC, fg=WHITE, u: float = 1.0) -> Image.Image:
    b = f.getbbox(text)
    px, py = int(34 * u), int(18 * u)
    w, h = b[2] - b[0] + 2 * px, b[3] - b[1] + 2 * py
    im = Image.new("RGBA", (w + 12, h + 14), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((6, 10, w + 6, h + 10), h // 2, fill=(60, 40, 90, 80))
    d.rounded_rectangle((6, 6, w + 6, h + 6), h // 2, fill=bg + (255,))
    d.text((6 + w / 2, 6 + h / 2), text, font=f, fill=fg, anchor="mm")
    return im


def _cursor(scale: float) -> Image.Image:
    pts = [(0, 0), (0, 34), (9, 26), (15, 40), (21, 37), (15, 24), (27, 24)]
    im = Image.new("RGBA", (70, 90), (0, 0, 0, 0))
    ImageDraw.Draw(im).polygon([(x * 2 + 4, y * 2 + 4) for x, y in pts], fill=(255, 255, 255, 255),
                               outline=(0, 0, 0, 255), width=4)
    return im.resize((max(2, int(70 * scale)), max(2, int(90 * scale))), Image.LANCZOS)


def _heart_pts(cx: float, cy: float, size: float, n: int = 200):
    t = np.linspace(0, 2 * np.pi, n)
    x = 16 * np.sin(t) ** 3
    y = -(13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t))
    k = size / 34
    return [(cx + xx * k, cy + yy * k + size * 0.05) for xx, yy in zip(x, y)]


def _lilac_bg(ctx) -> Image.Image:
    key = ("studio_lilac", ctx.w, ctx.h)
    if key not in ctx.cache:
        im = Image.new("RGBA", (ctx.w, ctx.h))
        d = ImageDraw.Draw(im)
        for yy in range(ctx.h):
            k = yy / ctx.h
            d.line([(0, yy), (ctx.w, yy)], fill=(int(222 - 16 * k), int(208 - 18 * k), int(246 - 8 * k), 255))
        ctx.cache[key] = im
    return ctx.cache[key]


def _free_x(ctx, width: float) -> float:
    """Centre x for an element beside Carina (the side away from her face)."""
    fx0, _, fx1, _ = ctx.face
    if ctx.portrait or ctx.no_face:
        return ctx.w / 2
    if (fx0 + fx1) / 2 < 0.55:
        return min(ctx.w - width / 2 - 60 * ctx.u, max(fx1 * ctx.w + width / 2 + 40 * ctx.u, ctx.w * 0.76))
    return max(width / 2 + 60 * ctx.u, min(fx0 * ctx.w - width / 2 - 40 * ctx.u, ctx.w * 0.24))


# ------------------------------------------------------------------ battery

def draw_battery(base, ctx, it, t, d, mask):
    w, h, u = ctx.w, ctx.h, ctx.u
    k = t / max(0.1, d)
    lvl = 40 - 37 * ease(k * 1.1)
    col = tuple(int(a + (b - a) * min(1, k * 1.4)) for a, b in zip(LILAC, RED))
    label, l1, l2, l3 = _parts(it.get("title", ""), 4, ["brain battery", "Low Battery", "3% remaining",
                                                       "connect to coffee"])
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bw, bh = int(160 * u), int(300 * u)
    cx = _free_x(ctx, bw * 2.2)
    cy = h * (0.55 if not ctx.portrait else 0.62)
    s = back(t / 0.3)
    bat = Image.new("RGBA", (bw + 20, bh + 40), (0, 0, 0, 0))
    dd = ImageDraw.Draw(bat)
    dd.rounded_rectangle((bw * 0.35 + 10, 0, bw * 0.65 + 10, 24 * u), int(8 * u), fill=WHITE)
    dd.rounded_rectangle((10, 18 * u, bw + 10, bh + 30), int(30 * u), outline=WHITE, width=max(4, int(11 * u)))
    fh = int((bh - 30 * u) * lvl / 100)
    dd.rounded_rectangle((24 * u, bh + 16 - max(fh, int(20 * u)), bw - 4 * u, bh + 16), int(22 * u), fill=col)
    fx.paste_scaled(layer, bat, (cx, cy), s, 1.0)
    _pop_text(layer, f"{int(lvl)}%", sfont("titan", int(56 * u)), (cx, cy + bh * 0.62), back(t / 0.3), 1, WHITE)
    if t > 0.15:
        p = _pill(label, sfont("fredoka_b", int(40 * u)), u=u)
        fx.paste_scaled(layer, p, (cx, cy + bh * 0.62 + 70 * u), back((t - 0.15) / 0.3), 1)
    if k > 0.62:  # iPhone popup
        s2 = back((t - 0.62 * d) / 0.3)
        pw, ph = int(760 * u), int(300 * u)
        pop = Image.new("RGBA", (pw + 40, ph + 40), (0, 0, 0, 0))
        dp = ImageDraw.Draw(pop)
        dp.rounded_rectangle((20, 28, pw + 20, ph + 28), int(44 * u), fill=(0, 0, 0, 70))
        pop = pop.filter(ImageFilter.GaussianBlur(10))
        dp = ImageDraw.Draw(pop)
        dp.rounded_rectangle((20, 20, pw + 20, ph + 20), int(44 * u), fill=(250, 248, 252, 245))
        dp.text((20 + pw / 2, 20 + ph * 0.22), l1, font=sfont("inter_b", int(54 * u)), fill=(25, 25, 25), anchor="mm")
        dp.text((20 + pw / 2, 20 + ph * 0.45), l2, font=sfont("inter_l", int(40 * u)), fill=(60, 60, 60), anchor="mm")
        dp.line([(20, 20 + ph * 0.62), (20 + pw, 20 + ph * 0.62)], fill=(210, 205, 215), width=3)
        dp.text((20 + pw / 2, 20 + ph * 0.81), l3, font=sfont("inter_b", int(44 * u)), fill=LILAC_DARK, anchor="mm")
        px = w / 2 if ctx.portrait else min(max(cx, pw / 2 + 40 * u), w - pw / 2 - 40 * u)
        fx.paste_scaled(layer, pop, (px, h * (0.19 if not ctx.portrait else 0.42)), s2, 1)
    out = base.copy()
    out.alpha_composite(layer)
    return out


# ------------------------------------------------------------------ code chips

DEFAULT_SNIPPETS = ["if (tired) { keepGoing() }", "const coffee = 3;", "// why is this not working",
                    "fix_bug_final_v7()", "while(!done) edit();"]


def draw_codechips(base, ctx, it, t, d, mask):
    w, h, u = ctx.w, ctx.h, ctx.u
    snips = [s for s in (it.get("items") or []) if str(s).strip()] or DEFAULT_SNIPPETS
    f = sfont("inter_b", int(36 * u))
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    maxw = max(f.getlength(s) for s in snips) + 70 * u
    cx = _free_x(ctx, maxw)
    top = h * (0.12 if not ctx.portrait else 0.58)
    step = (h * (0.72 if not ctx.portrait else 0.28)) / max(1, len(snips))
    for q, sn in enumerate(snips):
        st = q * 0.17
        if t < st:
            continue
        k = t - st
        n = min(len(sn), int(k * 66))
        txt = sn[:n] + ("|" if int(k * 10) % 2 == 0 and n < len(sn) else "")
        tw = f.getlength(sn)
        chip = Image.new("RGBA", (int(tw + 74 * u), int(90 * u)), (0, 0, 0, 0))
        dc = ImageDraw.Draw(chip)
        dc.rounded_rectangle((4, 8, chip.width - 1, chip.height - 1), int(22 * u), fill=(40, 30, 60, 90))
        dc.rounded_rectangle((0, 0, chip.width - 6, chip.height - 10), int(22 * u), fill=(30, 24, 44, 235))
        dc.ellipse((18 * u, 30 * u, 34 * u, 46 * u), fill=LILAC)
        dc.text((46 * u, 38 * u), txt, font=f, fill=LILAC if q % 2 else WHITE, anchor="lm")
        x = cx + (q % 2 * 2 - 1) * 40 * u
        fx.paste_scaled(layer, chip, (x, top + step * q + step / 2), back(k / 0.23), 1)
    out = base.copy()
    out.alpha_composite(layer)
    return out


# ------------------------------------------------------------------ nightfall

def draw_nightfall(base, ctx, it, t, d, mask):
    w, h, u = ctx.w, ctx.h, ctx.u
    k = t / max(0.1, d)
    t0, t1, line = _parts(it.get("title", ""), 3, ["18:00", "21:47", "wait… it's night?"])

    def mins(s):
        try:
            a, b = s.split(":")
            return int(a) * 60 + int(b)
        except ValueError:
            return 18 * 60

    out = base.copy()
    out.alpha_composite(Image.new("RGBA", (w, h), (40, 30, 90, int(90 * ease(k * 1.5)))))
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dl = ImageDraw.Draw(layer)
    cx, cy, R = _free_x(ctx, 500 * u), h * 0.48, 330 * u
    a1 = math.pi * (1.15 + 0.5 * ease(k * 1.3))
    sx, sy = cx + R * math.cos(a1), cy + R * math.sin(a1) * 0.8 + 200 * u
    r = 60 * u
    dl.ellipse((sx - r, sy - r, sx + r, sy + r), fill=YELLOW + (int(255 * (1 - ease(k * 1.6))),))
    if k > 0.2:
        a2 = math.pi * (1.95 - 0.5 * ease((k - 0.25) * 1.6))
        mx, my = cx + R * math.cos(a2) - 80 * u, cy + R * math.sin(a2) * 0.8 + 60 * u
        al = int(255 * ease((k - 0.2) * 3))
        moon = Image.new("RGBA", (int(4 * r), int(4 * r)), (0, 0, 0, 0))
        dm = ImageDraw.Draw(moon)
        dm.ellipse((r, r, 3 * r, 3 * r), fill=(245, 240, 255, al))
        dm.ellipse((1.5 * r, 0.75 * r, 3.3 * r, 2.6 * r), fill=(0, 0, 0, 0))
        layer.alpha_composite(moon, (int(mx - 2 * r), int(my - 2 * r)))
    m = mins(t0) + (mins(t1) - mins(t0)) * ease(k * 1.2)
    _pop_text(layer, f"{int(m) // 60:02d}:{int(m) % 60:02d}", sfont("titan", int(120 * u)), (cx, h * 0.14),
              back(t / 0.3), 1, WHITE)
    if t > 0.6 * d * 0.5:
        p = _pill(line, sfont("fredoka_b", int(48 * u)), u=u)
        fx.paste_scaled(layer, p, (cx, h * 0.28), back((t - 0.3 * d) / 0.3), 1)
    out.alpha_composite(layer.filter(ImageFilter.GaussianBlur(0.6)))
    return out


# ------------------------------------------------------------------ logoff

def draw_logoff(base, ctx, it, t, d, mask):
    w, h, u = ctx.w, ctx.h, ctx.u
    text = (it.get("title") or "logging off").replace("…", "").rstrip(".")
    gl = min(0.4 * d, 1.2)
    out = base
    if t < gl:
        a = np.asarray(base.convert("RGB")).astype(np.int16)
        j = int(t * 30)
        rng = np.random.default_rng(j)
        sh = int((8 + 3 * j) * u)
        o = a.copy()
        o[..., 0] = np.roll(a[..., 0], sh, 1)
        o[..., 2] = np.roll(a[..., 2], -sh, 1)
        for _ in range(6):
            y = int(rng.integers(0, max(1, h - 60)))
            hh = int(rng.integers(10, 60))
            o[y:y + hh] = np.roll(o[y:y + hh], int(rng.integers(-120, 120) * u), 1)
        o[::4] = (o[::4] * 0.75).astype(np.int16)
        out = Image.fromarray(np.clip(o, 0, 255).astype(np.uint8)).convert("RGBA")
    else:
        out = base.copy()
        q = t - gl
        dots = "." * (1 + int(q * 7.5) % 3)
        p = _pill(text + dots + " " * (3 - len(dots)), sfont("titan", int(70 * u)), u=u)
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        fx.paste_scaled(layer, p, (w / 2, h * 0.82), back(q / 0.25), 1)
        out.alpha_composite(layer)
    return out


# ------------------------------------------------------------------ sport pill

def _stopwatch(d, cx, cy, r, ang, col):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=max(3, int(r // 5)))
    d.rectangle((cx - r * 0.25, cy - r * 1.45, cx + r * 0.25, cy - r * 1.15), fill=col)
    d.line([cx, cy, cx + r * 0.7 * math.sin(ang), cy - r * 0.7 * math.cos(ang)], fill=col, width=max(3, int(r // 6)))


def draw_sportpill(base, ctx, it, t, d, mask):
    w, h, u = ctx.w, ctx.h, ctx.u
    name, mins = _parts(it.get("title", ""), 2, ["ZUMBA", "30 min"])
    f1, f2 = sfont("titan", int(62 * u)), sfont("fredoka_b", int(50 * u))
    tw, mw = f1.getlength(name), f2.getlength("× " + mins)
    ph = int(108 * u)
    pw = int(110 * u + tw + 30 * u + mw + 50 * u)
    p = Image.new("RGBA", (pw + 20, ph + 20), (0, 0, 0, 0))
    dp = ImageDraw.Draw(p)
    dp.rounded_rectangle((10, 14, pw + 10, ph + 14), ph // 2, fill=(90, 70, 125, 90))
    dp.rounded_rectangle((10, 10, pw + 10, ph + 10), ph // 2, fill=LILAC + (255,))
    _stopwatch(dp, 10 + 62 * u, 10 + ph / 2 + 6 * u, 26 * u, t * 10.5, WHITE)
    dp.text((10 + 110 * u, 10 + ph / 2), name, font=f1, fill=WHITE, anchor="lm")
    x0 = 10 + 110 * u + tw + 20 * u
    dp.rounded_rectangle((x0, 10 + 18 * u, x0 + mw + 30 * u, ph - 8 * u), int(30 * u), fill=WHITE)
    dp.text((x0 + 15 * u, 10 + ph / 2 + 2), "× " + mins, font=f2, fill=LILAC_DARK, anchor="lm")
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out_k = ease((t - (d - 0.3)) / 0.3) if t > d - 0.3 else 0
    s = back(t / 0.3) * (1 - 0.3 * out_k)
    fx.paste_scaled(layer, p, (60 * u + p.width / 2, 60 * u + p.height / 2 - 120 * u * out_k), s, 1 - out_k)
    out = base.copy()
    out.alpha_composite(layer)
    return out


# ------------------------------------------------------------------ ring timer

def _num(x: str) -> float | None:
    try:
        return float(str(x).replace(".", "").replace(",", ".").replace(" ", ""))
    except ValueError:
        return None


def fmt_count(v: float) -> str:
    """190000 → 190.000 (deutsche Tausenderpunkte)."""
    return f"{int(round(v)):,}".replace(",", ".")


def draw_ringtimer(base, ctx, it, t, d, mask):
    w, h, u = ctx.w, ctx.h, ctx.u
    title, total, upto = _parts(it.get("title", ""), 3, ["meditation time", "30", ""])
    count_up = _num(upto) is not None and _num(total) is not None   # "Text|1|190000" = hochzählen
    try:
        total_s = float(total) * 60
    except ValueError:
        total_s = 1800
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    k = min(1.0, max(0.0, (t - 0.3) / max(0.3, d - 0.8)))
    R = 150 * u
    cx = _free_x(ctx, 2 * R + 80 * u)
    cy = h * (0.55 if not ctx.portrait else 0.66)
    s = back(t / 0.3)
    ring = Image.new("RGBA", (int(2 * R + 40), int(2 * R + 40)), (0, 0, 0, 0))
    dr = ImageDraw.Draw(ring)
    box = (20, 20, 20 + 2 * R, 20 + 2 * R)
    dr.ellipse(box, outline=(255, 255, 255, 110), width=max(6, int(16 * u)))
    col = fx.text_color(it, LILAC)
    if count_up:   # Ring füllt sich, Zahl zählt hoch (z. B. Gedanken 1 → 190.000)
        if k > 0:
            dr.arc(box, -90, -90 + 360 * k, fill=col + (255,), width=max(6, int(16 * u)))
        a0, a1 = _num(total), _num(upto)
        val = fmt_count(a0 + (a1 - a0) * (1 - (1 - k) ** 3))
        fs = int(70 * u)
        while sfont("titan", fs).getlength(val) > 1.7 * R and fs > 20:
            fs = int(fs * 0.9)
        dr.text((20 + R, 20 + R), val, font=sfont("titan", fs), fill=WHITE, anchor="mm")
    else:
        if k < 1:
            dr.arc(box, -90 + 360 * k, 270, fill=col + (255,), width=max(6, int(16 * u)))
        left = total_s * (1 - k)
        dr.text((20 + R, 20 + R), f"{int(left) // 60:02d}:{int(left) % 60:02d}", font=sfont("titan", int(70 * u)),
                fill=WHITE, anchor="mm")
    pulse = 1 + (0.08 * math.sin((t - (d - 0.5)) * 12) if k >= 1 else 0)
    fx.paste_scaled(layer, ring, (cx, cy), s * pulse, 1)
    # write-on title
    f = sfont("fredoka_b", int(76 * u))
    tw = f.getlength(title)
    im = Image.new("RGBA", (int(tw + 60), int(f.size * 1.6)), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((30, im.height / 2), title, font=f, fill=WHITE, anchor="lm")
    rev = ease(t / 0.9)
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rectangle((0, 0, int(im.width * rev), im.height), fill=255)
    im.putalpha(Image.fromarray(np.minimum(np.asarray(im.getchannel("A")), np.asarray(m))))
    fx.paste_scaled(layer, fx._shadow(im, 8, 6, 120), (cx, cy - R - 90 * u), 1, 1)
    out = base.copy()
    out.alpha_composite(layer)
    return out


# ------------------------------------------------------------------ workout saved card

def draw_savedcard(base, ctx, it, t, d, mask):
    w, h, u = ctx.w, ctx.h, ctx.u
    head, button = _parts(it.get("title", ""), 2, ["WORKOUT SAVED", "RESUME: WORK"])
    stats = [s for s in (it.get("items") or []) if str(s).strip()] or ["Time|2h 00m", "Activities|3", "Mood|reset"]
    stats = [(s.split("|") + [""])[:2] for s in stats[:3]]
    k_in = ease(t / 0.3)
    k_out = ease((t - (d - 0.35)) / 0.35) if t > d - 0.35 else 0
    g = base.convert("L").convert("RGBA")
    out = Image.blend(base, g, 0.5 * k_in * (1 - k_out))
    out.alpha_composite(Image.new("RGBA", (w, h), (0, 0, 0, int(90 * k_in * (1 - k_out)))))
    cw, ch = int(760 * u), int(440 * u)
    click = 0.62 * d
    pb = 0 if t < click else math.exp(-(t - click) * 10) * abs(math.cos((t - click) * 27))
    card = Image.new("RGBA", (cw + 40, ch + 50), (0, 0, 0, 0))
    dc = ImageDraw.Draw(card)
    dc.rounded_rectangle((20, 30, cw + 20, ch + 30), int(36 * u), fill=(0, 0, 0, 90))
    card = card.filter(ImageFilter.GaussianBlur(12))
    dc = ImageDraw.Draw(card)
    dc.rounded_rectangle((20, 20, cw + 20, ch + 20), int(36 * u), fill=WHITE + (255,))
    dc.rounded_rectangle((20, 20, cw + 20, 20 + 100 * u), int(36 * u), fill=LILAC + (255,))
    dc.rectangle((20, 20 + 60 * u, cw + 20, 20 + 100 * u), fill=LILAC + (255,))
    dc.rectangle((58 * u, 20 + 30 * u, 70 * u, 20 + 70 * u), fill=WHITE)
    dc.rectangle((80 * u, 20 + 30 * u, 92 * u, 20 + 70 * u), fill=WHITE)
    dc.text((120 * u, 20 + 50 * u), head, font=sfont("inter_b", int(44 * u)), fill=WHITE, anchor="lm")
    for q, (lab, val) in enumerate(stats):
        x = 20 + 40 * u + q * (cw - 80 * u) / 3
        dc.text((x, 20 + 140 * u), lab, font=sfont("inter_l", int(30 * u)), fill=(110, 110, 110))
        dc.text((x, 20 + 180 * u), val, font=sfont("inter_b", int(52 * u)), fill=LILAC_DARK)
    sb = 1 + 0.12 * pb
    bw, bh = int(520 * u * sb), int(96 * u * sb)
    bx, by = 20 + cw / 2, 20 + 340 * u
    dc.rounded_rectangle((bx - bw / 2, by - bh / 2, bx + bw / 2, by + bh / 2), bh // 2, fill=LILAC + (255,))
    ff = sfont("inter_b", int(42 * u * sb))
    tl = ff.getlength(button)
    x0 = bx - (tl + 46 * u) / 2
    dc.text((x0, by), button, font=ff, fill=WHITE, anchor="lm")
    tx = x0 + tl + 20 * u
    dc.polygon([(tx, by - 15 * u), (tx, by + 15 * u), (tx + 25 * u, by)], fill=WHITE)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sc = back(t / 0.33) * (1.15 if not ctx.portrait else 1.0)
    cy = h / 2 + 30 * u
    fx.paste_scaled(layer, card, (w / 2, cy), sc, 1 - k_out)
    # cursor flies to the button and clicks
    if 0.3 * d < t < click + 0.3 and k_out == 0:
        p = ease((t - 0.3 * d) / max(0.1, click - 0.3 * d))
        tgx = w / 2 + 40 * u
        tgy = cy + (by - (ch + 50) / 2 - 20) * sc + 10 * u
        x = w * 0.86 + (tgx - w * 0.86) * p
        y = h * 0.95 + (tgy - h * 0.95) * p
        layer.alpha_composite(_cursor(u * (0.82 if abs(t - click) < 0.05 else 1)), (int(x), int(y)))
    out.alpha_composite(layer)
    return out


# ------------------------------------------------------------------ subscribe (lilac iris)

def draw_subscribe(base, ctx, it, t, d, mask):
    w, h, u = ctx.w, ctx.h, ctx.u
    l1, l2, l3 = _parts(it.get("title", ""), 3, ["any support in the form of", "a subscribe or like",
                                                 "would be highly appreciated"])
    items = [s for s in (it.get("items") or []) if str(s).strip()]
    sub_txt = (items[0] if items else "SUBSCRIBE").upper()
    subbed = (items[1] if len(items) > 1 else "SUBSCRIBED").upper()
    r_in = ease(t / 0.3)
    r_out = ease((t - (d - 0.35)) / 0.35) if t > d - 0.35 else 0
    R = int(math.hypot(w, h) * 0.62 * r_in * (1 - r_out))
    card = _lilac_bg(ctx).copy()
    L = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    portrait = ctx.portrait
    y0 = h * (0.3 if portrait else 0.28)
    gap = (95 if portrait else 120) * u
    f_small = sfont("fredoka", int((54 if portrait else 64) * u))
    f_big = sfont("titan", int((92 if portrait else 120) * u))
    while f_big.getlength(l2) > w * 0.9 and f_big.size > 30:
        f_big = sfont("titan", int(f_big.size * 0.9))
    _pop_text(L, l1, f_small, (w / 2, y0), back((t - 0.25) / 0.3), min(1, (t - 0.25) * 4), PLUM, sh_a=0.35)
    _pop_text(L, l2, f_big, (w / 2, y0 + gap), back((t - 0.5) / 0.3), min(1, (t - 0.5) * 4), WHITE, sh_a=0.45)
    _pop_text(L, l3, f_small, (w / 2, y0 + 2.15 * gap), back((t - 0.85) / 0.3), min(1, (t - 0.85) * 4), PLUM,
              sh_a=0.35)
    c1, c2 = 0.53 * d, 0.68 * d
    if t > 1.1:
        s = back((t - 1.1) / 0.3)
        subbed_now = t >= c1
        fb = sfont("inter_b", int(46 * u))
        lab = subbed if subbed_now else sub_txt
        bw = int(fb.getlength(lab) + 120 * u)
        bh = int(118 * u)
        btn = Image.new("RGBA", (bw + 20, bh + 24), (0, 0, 0, 0))
        db = ImageDraw.Draw(btn)
        db.rounded_rectangle((10, 18, bw + 10, bh + 18), bh // 2, fill=(60, 30, 90, 90))
        btn = btn.filter(ImageFilter.GaussianBlur(8))
        db = ImageDraw.Draw(btn)
        db.rounded_rectangle((10, 10, bw + 10, bh + 10), bh // 2,
                             fill=((238, 232, 246) if subbed_now else LILAC_DARK) + (255,))
        db.text((10 + bw / 2, 10 + bh / 2), lab, font=fb, fill=PLUM if subbed_now else WHITE, anchor="mm")
        likew = int(220 * u)
        like = Image.new("RGBA", (likew + 20, bh + 24), (0, 0, 0, 0))
        dk = ImageDraw.Draw(like)
        dk.rounded_rectangle((10, 18, likew + 10, bh + 18), bh // 2, fill=(60, 30, 90, 90))
        like = like.filter(ImageFilter.GaussianBlur(8))
        dk = ImageDraw.Draw(like)
        dk.rounded_rectangle((10, 10, likew + 10, bh + 10), bh // 2,
                             fill=(LILAC if t >= c2 else (238, 232, 246)) + (255,))
        # thumbs-up drawn as a simple heart (fonts have no emoji)
        hs = int(64 * u)
        like.alpha_composite(fx._heart(hs, LILAC_DARK if t < c2 else WHITE), (int(10 + likew / 2 - hs / 2), int(10 + bh / 2 - hs / 2)))
        by = y0 + 3.5 * gap
        total = likew + 40 * u + bw
        lx = w / 2 - total / 2 + likew / 2
        sx = w / 2 + total / 2 - bw / 2
        ps1 = s * (1 + 0.12 * math.exp(-(t - c1) * 10) if t >= c1 else 1)
        ps2 = s * (1 + 0.25 * math.exp(-(t - c2) * 10) if t >= c2 else 1)
        fx.paste_scaled(L, btn, (sx, by), ps1, 1)
        fx.paste_scaled(L, like, (lx, by), ps2, 1)
        if 1.4 < t < c2 + 0.4:
            if t < c1:
                p = ease((t - 1.4) / max(0.1, c1 - 1.4))
                x, y = w * 0.88 + (sx + 30 * u - w * 0.88) * p, h * 0.97 + (by + 20 * u - h * 0.97) * p
            elif t < c2:
                p = ease((t - c1) / max(0.1, c2 - c1))
                x, y = sx + 30 * u + (lx + 20 * u - sx - 30 * u) * p, by + 20 * u
            else:
                x, y = lx + 20 * u, by + 20 * u
            near = min(abs(t - c1), abs(t - c2)) < 0.05
            L.alpha_composite(_cursor(u * (0.82 if near else 1)), (int(x), int(y)))
    card.alpha_composite(L)
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).ellipse((w / 2 - R, h / 2 - R, w / 2 + R, h / 2 + R), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(max(1, int(30 * u))))
    out = base.copy()
    out.paste(card, (0, 0), m)
    return out


# ------------------------------------------------------------------ heart cover

def draw_heartcover(base, ctx, it, t, d, mask):
    w, h, u = ctx.w, ctx.h, ctx.u
    left, right = _parts(it.get("title", ""), 2, ["THANK", "YOU"])
    grow0 = 0.55 * d
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    fx0, fy0, fx1, fy1 = ctx.face
    f = sfont("titan", int((130 if ctx.portrait else 160) * u))
    ty = max(f.size * 0.7, (fy0 + (fy1 - fy0) * 0.4) * h) if not ctx.portrait else h * 0.12
    if ctx.portrait:
        words = [(f"{left} {right}", w / 2 - f.getlength(f"{left} {right}") / 2)]
    else:
        words = [(left, fx0 * w - 30 * u - f.getlength(left)), (right, fx1 * w + 30 * u)]
    dl = ImageDraw.Draw(layer)
    n = 0
    for word, x in words:
        for ch in word:
            k = (t - n * 0.04) / 0.2
            n += 1
            if k > 0:
                y = ty - 120 * u * (1 - back(k))
                a = int(255 * min(1, k * 2))
                dl.text((x + 6 * u, y + 8 * u), ch, font=f, fill=PLUM + (int(a * 0.55),), anchor="lm")
                dl.text((x, y), ch, font=f, fill=LILAC + (a,), anchor="lm")
            x += f.getlength(ch)
    out = base.copy()
    out.alpha_composite(layer)
    if mask is not None:
        out = Image.composite(base, out, mask)
    if t >= grow0:
        p = ease_in((t - grow0) / max(0.1, d - grow0 - 0.1))
        mx, my = (fx0 + fx1) / 2 * w, (fy0 + (fy1 - fy0) * 0.75) * h
        size = 30 * u + max(w, h) * 2.0 * p
        cx, cy = mx + (w / 2 - mx) * p, my + (h / 2 - my) * p
        hm = Image.new("L", (w, h), 0)
        ImageDraw.Draw(hm).polygon(_heart_pts(cx, cy, size), fill=255)
        glow = Image.new("L", (w, h), 0)
        ImageDraw.Draw(glow).polygon(_heart_pts(cx, cy, size * 1.08), fill=255)
        glow = glow.filter(ImageFilter.GaussianBlur(max(2, int(18 * u))))
        out.paste(Image.new("RGBA", (w, h), WHITE + (255,)), (0, 0), glow.point(lambda v: int(v * 0.8)))
        out.paste(_lilac_bg(ctx), (0, 0), hm.filter(ImageFilter.GaussianBlur(2)))
    return out


# ------------------------------------------------------------------ share stats (Strava style)

def _checker(ctx, alpha=40) -> Image.Image:
    key = ("studio_checker", ctx.w, ctx.h)
    if key not in ctx.cache:
        sz = max(16, int(40 * ctx.u))
        im = Image.new("RGBA", (ctx.w, ctx.h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for y in range(0, ctx.h, sz):
            for x in range(0, ctx.w, sz):
                if (x // sz + y // sz) % 2:
                    d.rectangle((x, y, x + sz, y + sz), fill=(255, 255, 255, alpha))
        ctx.cache[key] = im
    return ctx.cache[key]


def _route(x0, y0, w, h, n=160):
    tt = np.linspace(0, 1, n)
    xs = x0 + w * tt
    ys = y0 + h * (0.5 + 0.32 * np.sin(tt * 2 * math.pi * 1.6) + 0.12 * np.sin(tt * 2 * math.pi * 4.3 + 1))
    return list(zip(xs, ys))


def _wordmark(text, size, col=WHITE):
    f = sfont("inter_b", size)
    tw = int(f.getlength(text)) + 40
    im = Image.new("RGBA", (tw + 60, size + 40), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((20, 10), text, font=f, fill=col)
    return im.transform(im.size, Image.AFFINE, (1, 0.28, -10, 0, 1, 0), Image.BICUBIC)


def _stats_sticker(ctx, stats, name, scale):
    u = ctx.u * scale
    key = ("studio_sticker", tuple(map(tuple, stats)), name, round(u, 3))
    if key in ctx.cache:
        return ctx.cache[key]
    sw, sh = int(560 * u), int(760 * u)
    im = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    lab, val = sfont("inter_b", int(28 * u)), sfont("inter_b", int(72 * u))
    for q, (l, v) in enumerate(stats[:3]):
        y = 10 * u + q * 155 * u
        d.text((sw / 2, y), l, font=lab, fill=WHITE, anchor="ma")
        d.text((sw / 2, y + 36 * u), v, font=val, fill=WHITE, anchor="ma")
    d.line(_route(110 * u, 490 * u, 340 * u, 130 * u), fill=LILAC, width=max(4, int(12 * u)), joint="curve")
    wm = _wordmark(name, int(54 * u))
    im.alpha_composite(wm, (int(sw / 2 - wm.width / 2), int(sh - wm.height - 4 * u)))
    ctx.cache[key] = im
    return im


def draw_sharestats(base, ctx, it, t, d, mask):
    w, h, u = ctx.w, ctx.h, ctx.u
    cta = (it.get("title") or "give kudos & follow for part 2").replace("|", " ")
    raw = [s for s in (it.get("items") or []) if str(s).strip()]
    name = "CARINA"
    if raw and raw[-1].lower().startswith("name|"):
        name = raw.pop().split("|", 1)[1] or name
    stats = [(s.split("|") + [""])[:2] for s in raw] or [["Work", "11h 00m"], ["Sports", "2h 00m"],
                                                         ["Meditation", "30m"]]
    k = ease(t / 0.4)
    bg = base.filter(ImageFilter.GaussianBlur(max(1, int(18 * u * k)))) if k > 0.02 else base.copy()
    bg.alpha_composite(Image.new("RGBA", (w, h), DARK + (int(170 * k),)))
    chk = _checker(ctx).copy()
    chk.putalpha(chk.getchannel("A").point(lambda v: int(v * k)))
    bg.alpha_composite(chk)
    out = bg
    tap, fly = 0.42 * d, 0.48 * d
    pw, ph = int(560 * u), int(980 * u)
    px = w - pw - 80 * u if not ctx.portrait else w / 2 - pw / 2
    phone_y = h * 0.04 + h * (1 - ease((t - 0.2) / 0.5))
    if t > fly:
        phone_y += h * ease((t - fly) / 0.35)
    phone = None
    if phone_y < h:
        pt = 0 if t < tap else math.exp(-(t - tap) * 10)
        phone = Image.new("RGBA", (pw + 40, ph + 40), (0, 0, 0, 0))
        dp = ImageDraw.Draw(phone)
        dp.rounded_rectangle((20, 30, pw + 20, ph + 30), int(66 * u), fill=(0, 0, 0, 110))
        phone = phone.filter(ImageFilter.GaussianBlur(14))
        dp = ImageDraw.Draw(phone)
        dp.rounded_rectangle((20, 20, pw + 20, ph + 20), int(66 * u), fill=(18, 16, 22, 255))
        dp.rounded_rectangle((34, 34, pw + 6, ph + 6), int(54 * u), fill=(30, 28, 36, 255))
        dp.text((60 * u, 100 * u), "Close", font=sfont("inter_l", int(24 * u)), fill=WHITE, anchor="lm")
        dp.text((20 + pw / 2 + 30 * u, 100 * u), "Share Activity", font=sfont("inter_b", int(28 * u)), fill=WHITE,
                anchor="mm")
        sx0, sy0, sx1, sy1 = int(70 * u), int(150 * u), int(pw - 30 * u), int(730 * u)
        sq = max(8, int(24 * u))
        for yy in range(sy0, sy1, sq):
            for xx in range(sx0, sx1, sq):
                dp.rectangle((xx, yy, min(xx + sq, sx1), min(yy + sq, sy1)),
                             fill=(70, 68, 76) if ((xx - sx0) // sq + (yy - sy0) // sq) % 2 else (52, 50, 58))
        if t < fly:
            st = _stats_sticker(ctx, stats, name, 0.74)
            phone.alpha_composite(st, (int((sx0 + sx1) / 2 - st.width / 2), int(sy0 + 20 * u)))
        dp.text((60 * u, 790 * u), "Share to", font=sfont("inter_b", int(26 * u)), fill=WHITE)
        r = int(44 * u * (1 + 0.15 * pt))
        cx, cy = int(120 * u), int(880 * u)
        dp.ellipse((cx - r - 6, cy - r - 6, cx + r + 6, cy + r + 6), fill=LILAC)
        dp.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(30, 28, 36))
        dp.ellipse((cx - r + 10, cy - r + 10, cx + r - 10, cy + r - 10), fill=LILAC_DARK)
        dp.text((cx, cy + r + 24 * u), "Story", font=sfont("inter_l", int(20 * u)), fill=WHITE, anchor="mm")
        for q, lab in enumerate(["Copy", "Save", "Link", "More"]):
            x = 240 * u + q * 88 * u
            dp.ellipse((x - 28 * u, cy - 28 * u, x + 28 * u, cy + 28 * u), outline=WHITE, width=max(2, int(3 * u)))
            dp.text((x, cy + r + 24 * u), lab, font=sfont("inter_l", int(18 * u)), fill=WHITE, anchor="mm")
        out.alpha_composite(phone, (int(px - 20), int(phone_y - 20)))
        if 0.25 * d < t < tap + 0.15:
            p = ease((t - 0.25 * d) / max(0.1, tap - 0.25 * d))
            tx, ty = px + cx, phone_y + cy
            x, y = w * 0.9 + (tx - w * 0.9) * p, h * 0.98 + (ty - h * 0.98) * p
            out.alpha_composite(_cursor(u * (0.82 if abs(t - tap) < 0.05 else 1)), (int(x), int(y)))
    if t >= fly:  # sticker flies out next to Carina
        e = ease((t - fly) / 0.45)
        sc = 0.74 + 0.31 * e
        st = _stats_sticker(ctx, stats, name, round(sc, 2))
        sx_from, sy_from = px + pw / 2, h * 0.04 + 170 * u + st.height * 0.4
        tx = w * (0.74 if not ctx.portrait else 0.5)
        ty = h * (0.48 if not ctx.portrait else 0.3)
        x, y = sx_from + (tx - sx_from) * e, sy_from + (ty - sy_from) * e
        shd = Image.new("RGBA", st.size, (0, 0, 0, 0))
        shd.putalpha(st.getchannel("A").point(lambda v: int(v * 0.5)))
        shd = shd.filter(ImageFilter.GaussianBlur(8))
        out.alpha_composite(shd, (int(x - st.width / 2 + 6), int(y - st.height / 2 + 10)))
        out.alpha_composite(st, (int(x - st.width / 2), int(y - st.height / 2)))
    if mask is not None:  # Carina sharp in front
        out = Image.composite(base, out, mask.point(lambda v: int(v * k)))
    if t > 0.75 * d:
        L = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        p = _pill(cta, sfont("titan", int(60 * u)), u=u)
        fx.paste_scaled(L, p, (w / 2, h * 0.9), back((t - 0.75 * d) / 0.3), 1)
        out.alpha_composite(L)
    return out


# ------------------------------------------------------------------ Wort kreist ("Gedankenkreisen")

def _ring_of_word(word: str, R: float, size: int, color) -> Image.Image:
    """Das Wort mehrfach rund um einen Kreis geschrieben (Buchstaben zeigen nach außen)."""
    f = sfont("fredoka_b", size)
    unit = word.upper().strip() + "  •  "
    circ = 2 * math.pi * R
    reps = max(1, int(circ // max(1.0, f.getlength(unit))))
    text = unit * reps
    total = sum(f.getlength(ch) for ch in text)
    scale = circ / max(1.0, total)          # Abstände so strecken, dass der Kreis genau voll wird
    side = int(2 * (R + size * 1.2))
    img = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    c = side / 2
    ang = -math.pi / 2
    for ch in text:
        cw = f.getlength(ch) * scale
        mid = ang + cw / 2 / R
        if ch.strip():
            g = Image.new("RGBA", (int(size * 1.6), int(size * 1.6)), (0, 0, 0, 0))
            ImageDraw.Draw(g).text((g.width / 2, g.height / 2), ch, font=f, fill=color + (255,), anchor="mm")
            g = g.rotate(-math.degrees(mid) - 90, resample=Image.BICUBIC, expand=True)
            x, y = c + R * math.cos(mid), c + R * math.sin(mid)
            img.alpha_composite(g, (int(x - g.width / 2), int(y - g.height / 2)))
        ang += cw / R
    return img


def draw_circleword(base, ctx, it, t, d, mask):
    """Ein Wort kreist: rund um einen Kreis geschrieben und dreht sich (title 'Wort|Mitte (optional)')."""
    w, h, u = ctx.w, ctx.h, ctx.u
    word, center = _parts(it.get("title", ""), 2, ["Gedanken", ""])
    col = fx.text_color(it, WHITE)
    R = 250 * u * float(it.get("scale") or 1)
    size = int(58 * u * float(it.get("scale") or 1))
    key = ("circleword", word, int(R), size, col)
    if key not in ctx.cache:
        ctx.cache[key] = _ring_of_word(word, R, size, col)
    ring = ctx.cache[key].rotate(-t * 40, resample=Image.BICUBIC)   # 40° pro Sekunde
    cx = _free_x(ctx, ring.width)
    cy = h * (0.5 if not ctx.portrait else 0.6)
    k_in = back(t / 0.45)
    k_out = 1 - ease((t - (d - 0.4)) / 0.4) if t > d - 0.4 else 1
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    fx.paste_scaled(layer, fx._shadow(ring, 6, 5, 110), (cx, cy), k_in, k_out)
    if center:
        f = sfont("titan", int(64 * u))
        im = Image.new("RGBA", (int(f.getlength(center) + 40), int(f.size * 1.6)), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((im.width / 2, im.height / 2), center, font=f, fill=WHITE, anchor="mm")
        fx.paste_scaled(layer, fx._shadow(im, 6, 5, 120), (cx, cy), k_in, k_out)
    out = base.copy()
    out.alpha_composite(layer)
    return out


# ------------------------------------------------------------------ "Gedanken = 190.000" (Zähler mit Text)

def draw_countup(base, ctx, it, t, d, mask):
    """Text + Zahl, die immer größer wird (title 'Text|von|bis', z. B. 'Gedanken =|1|190000')."""
    w, h, u = ctx.w, ctx.h, ctx.u
    label, a, b = _parts(it.get("title", ""), 3, ["Gedanken =", "1", "190000"])
    a0, a1 = _num(a) or 0.0, _num(b) or 100.0
    k = min(1.0, max(0.0, (t - 0.25) / max(0.3, d * 0.8 - 0.25)))
    val = fmt_count(a0 + (a1 - a0) * (k ** 2.2))   # erst langsam, dann immer schneller (Gedanken rasen)
    col = fx.text_color(it, WHITE)
    sc = float(it.get("scale") or 1)
    f1 = sfont("fredoka_b", int(64 * u * sc))
    f2 = sfont("titan", int(110 * u * sc * (0.9 + 0.25 * k)))   # Zahl wächst auch optisch
    W1, W2 = f1.getlength(label), f2.getlength(fmt_count(a1))
    im = Image.new("RGBA", (int(max(W1, W2) + 80), int(f1.size * 1.4 + f2.size * 1.4)), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.text((im.width / 2, f1.size * 0.8), label, font=f1, fill=WHITE, anchor="mm")
    dr.text((im.width / 2, f1.size * 1.4 + f2.size * 0.7), val, font=f2, fill=col, anchor="mm")
    cx = _free_x(ctx, im.width)
    cy = h * (0.42 if not ctx.portrait else 0.55)
    k_in = back(t / 0.35)
    k_out = 1 - ease((t - (d - 0.35)) / 0.35) if t > d - 0.35 else 1
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    fx.paste_scaled(layer, fx._shadow(im, 8, 6, 130), (cx, cy), k_in, k_out)
    out = base.copy()
    out.alpha_composite(layer)
    return out


# ------------------------------------------------------------------ registry

STUDIO_TYPES = {
    "battery": ("E", "Low battery (brain battery + popup)", ("side",)),
    "codechips": ("E", "Code snippets typing", ("side",)),
    "nightfall": ("E", "Sunset → moon, time counts", ("side",)),
    "logoff": ("E", "Glitch + 'logging off…'", ("side",)),
    "sportpill": ("E", "Sport label with stopwatch", ("side",)),
    "ringtimer": ("E", "Meditation ring timer (counts down or up)", ("side",)),
    "circleword": ("E", "Word circling (e.g. Gedankenkreisen)", ("side",)),
    "countup": ("E", "Text + number counting up (e.g. Gedanken = 190.000)", ("side",)),
    "savedcard": ("E", "'Workout saved' card + click", ("scene",)),
    "subscribe": ("E", "Subscribe/like on lilac (iris)", ("scene",)),
    "heartcover": ("E", "THANK YOU behind you + lilac heart cover", ("side",)),
    "sharestats": ("E", "Strava-style day stats ending", ("scene",)),
}

STUDIO_DESCRIBE = {
    "battery": "Gehirn-Akku leert sich 40→3 % + iPhone-Popup 'Low Battery · connect to coffee' (title optional "
               "'Label|Zeile1|Zeile2|Zeile3') – wenn sie gähnt/müde ist, 2–3 s",
    "codechips": "Code-Schnipsel tippen sich neben ihr (items = 3–5 kurze Code-Zeilen, lustig) – Arbeiten am PC/App, 1–2 s",
    "nightfall": "Raum wird Nacht, Sonne geht unter, Mond auf, Uhr zählt (title 'Start|Ende|Satz', z. B. '18:00|21:47|wait… it's night?') – Abend, Zeit vergeht",
    "logoff": "Glitch, dann Pille 'logging off…' (title optional) – Feierabend, PC aus, 2–3 s",
    "sportpill": "Sport-Pille mit Stoppuhr oben links (title 'SPORT|Dauer', z. B. 'ZUMBA|30 min') – jede Sportart, ganze Szene",
    "ringtimer": "Meditations-Ring zählt runter + Titel schreibt sich (title 'Text|Minuten', z. B. 'meditation time|30'); "
                 "hochzählen mit 'Text|von|bis' (z. B. 'Gedanken|1|190000') – Meditation/Pause, 3–4 s",
    "circleword": "ein Wort kreist rund um einen Kreis und dreht sich (title 'Wort|Mitte optional', z. B. 'Gedanken') – Gedankenkreisen, Grübeln, 2–4 s",
    "countup": "Text + Zahl, die immer schneller hochzählt (title 'Text|von|bis', z. B. 'Gedanken =|1|190000') – wenn sie über viele Gedanken/Dinge spricht, 2–4 s",
    "savedcard": "Video gedimmt, lila Karte 'WORKOUT SAVED' mit 3 Werten, Cursor klickt Knopf (title 'Überschrift|Knopf', items 'Label|Wert') – Übergang nach Sport, ≥2 s",
    "subscribe": "Lila füllt das Bild von der Mitte, 'a subscribe or like' + Knöpfe werden angeklickt (title '3 Zeilen mit |') – Abo-Bitte, wenn etwas die Linse verdeckt, 3–4 s",
    "heartcover": "'THANK YOU' hinter ihr, dann wächst ein lila Herz aus ihrem Gesicht und deckt alles ab (title 'THANK|YOU') – Danke/Luftkuss am Ende, 2–3 s",
    "sharestats": "Strava-artiges Ende: Hintergrund dunkel, Handy 'Share Activity' mit Tageswerten, Sticker fliegt neben sie (items 'Label|Wert', optional 'name|CARINA'; title = Aufruf) – nur ganz am Ende, 5–6 s",
}

STUDIO_DRAWERS = {"battery": draw_battery, "codechips": draw_codechips, "nightfall": draw_nightfall,
                  "logoff": draw_logoff, "sportpill": draw_sportpill, "ringtimer": draw_ringtimer,
                  "circleword": draw_circleword, "countup": draw_countup,
                  "savedcard": draw_savedcard, "subscribe": draw_subscribe, "heartcover": draw_heartcover,
                  "sharestats": draw_sharestats}

STUDIO_MASK = {"heartcover", "sharestats"}
STUDIO_FULLSCREEN = {"savedcard", "subscribe", "sharestats"}
