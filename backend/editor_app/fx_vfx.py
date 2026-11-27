"""Video effects (group "V") – CapCut-style picture effects, our own implementation (Nov 2026).

Full-frame effects over the running video, drawn per frame with Pillow/numpy. No CapCut assets.
Colour dots pick the tint where it makes sense. They never change Carina's face colours permanently – every
effect is a short overlay/animation, the original clip is untouched.

  v_confetti    confetti rains down
  v_lightleak   warm light leak drifts over the picture
  v_flare       pulsing lens flare
  v_dust        floating glitter dust
  v_laser       laser lines sweep across
  v_radial      soft radial glow pulses from the middle
  v_develop     photo develops: from white/sepia to full colour
  v_zoompulse   picture zooms in on the beat (pulse)
  v_shake       camera shake
  v_rgbsplit    RGB split / chromatic shake
  v_flash       white flash
  v_film        film look: grain, flicker, scratches, rounded frame
  v_vhs         VHS look: scan lines, colour bleed, date stamp
  v_blurin      picture comes in from blur to sharp
  v_heartframe  soft heart-shaped frame (vignette) in a colour
"""
from __future__ import annotations

import math
import random
import time as _time

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from . import fx
from .fx_text import ACCENT, LILAC, PINK, WHITE, YELLOW

S = 2


def col_of(it, default):
    return ACCENT.get(it.get("color") or "", default)


def env(t, d, fin=0.25, fout=0.3):
    return min(1.0, t / fin if fin else 1.0, max(0.0, (d - t) / fout))


def _blend(base: Image.Image, top: Image.Image, a: float) -> Image.Image:
    if a >= 0.999:
        return top
    return Image.blend(base, top, max(0.0, min(1.0, a)))


def _add(base: Image.Image, light: np.ndarray, a: float) -> Image.Image:
    """Screen-blend a light layer (H×W×3 float 0..1) onto the picture."""
    b = np.asarray(base.convert("RGB")).astype(np.float32) / 255
    out = 1 - (1 - b) * (1 - light * a)
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).convert("RGBA")


def draw_confetti(base, ctx, it, t, d, mask):
    w, h, u = ctx.w, ctx.h, ctx.u
    cols = [LILAC, PINK, YELLOW, WHITE, (160, 214, 150)]
    rnd = random.Random(11)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)
    a = env(t, d, 0.05)
    for i in range(120):
        x0 = rnd.uniform(0, w)
        sp = rnd.uniform(0.35, 0.7) * h
        y = -40 * u + (t + rnd.uniform(0, 2.5)) * sp % (h + 80 * u) - 40 * u if t > 0 else -100
        x = x0 + math.sin(t * rnd.uniform(2, 5) + i) * 30 * u
        sz = rnd.uniform(8, 18) * u
        ang = t * rnd.uniform(3, 8) + i
        c = cols[i % len(cols)]
        dx, dy = math.cos(ang) * sz, math.sin(ang) * sz * 0.45
        dr.polygon([(x - dx, y - dy), (x + dy, y - dx * 0.4), (x + dx, y + dy), (x - dy, y + dx * 0.4)],
                   fill=c + (int(255 * a),))
    out = base.copy()
    out.alpha_composite(layer)
    return out


def _radial(w, h, cx, cy, r):
    y, x = np.ogrid[:h, :w]
    dd = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / max(1.0, r)
    return np.clip(1 - dd, 0, 1) ** 2


def draw_lightleak(base, ctx, it, t, d, mask):
    w, h = ctx.w, ctx.h
    col = np.array(col_of(it, (255, 170, 110)), np.float32) / 255
    key = ("vleak", w, h)
    if key not in ctx.cache:
        sw, sh = w // 4, h // 4
        ctx.cache[key] = (sw, sh)
    sw, sh = ctx.cache[key]
    cx = sw * (0.1 + 0.8 * (t / max(d, 0.1)))
    g = _radial(sw, sh, cx, sh * 0.3, sw * 0.6)[..., None] * col
    g2 = _radial(sw, sh, sw - cx * 0.7, sh * 0.8, sw * 0.45)[..., None] * np.array([1.0, 0.85, 0.6], np.float32)
    light = np.clip(g + g2 * 0.6, 0, 1)
    light = np.asarray(Image.fromarray((light * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)).astype(np.float32) / 255
    return _add(base, light, 0.85 * env(t, d, 0.4, 0.4))


def draw_flare(base, ctx, it, t, d, mask):
    w, h, u = ctx.w, ctx.h, ctx.u
    col = col_of(it, (255, 236, 200))
    pulse = 0.6 + 0.4 * math.sin(t * 4)
    sw, sh = w // 3, h // 3
    cx, cy = sw * 0.72, sh * 0.22
    light = _radial(sw, sh, cx, cy, sw * 0.35 * pulse)[..., None] * (np.array(col, np.float32) / 255)
    img = Image.fromarray((np.clip(light, 0, 1) * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)
    dr = ImageDraw.Draw(img)
    # streak + ghost rings along the line through the centre
    fx_, fy_ = cx * 3, cy * 3
    dr.line((fx_ - 380 * u * pulse, fy_, fx_ + 380 * u * pulse, fy_), fill=(255, 255, 255), width=max(2, int(4 * u)))
    for k, (r, c) in enumerate(((40, (200, 170, 255)), (70, (255, 190, 220)), (28, (180, 230, 255)))):
        px = fx_ + (w / 2 - fx_) * (0.6 + 0.4 * k)
        py = fy_ + (h / 2 - fy_) * (0.6 + 0.4 * k)
        rr = r * u * (0.8 + 0.4 * pulse)
        dr.ellipse((px - rr, py - rr, px + rr, py + rr), outline=c, width=max(2, int(5 * u)))
    img = img.filter(ImageFilter.GaussianBlur(2))
    return _add(base, np.asarray(img).astype(np.float32) / 255, 0.9 * env(t, d))


def draw_dust(base, ctx, it, t, d, mask):
    w, h, u = ctx.w, ctx.h, ctx.u
    col = col_of(it, YELLOW)
    rnd = random.Random(21)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)
    a = env(t, d, 0.4)
    for i in range(90):
        x = (rnd.uniform(0, w) + t * rnd.uniform(-30, 30) * u) % w
        y = (rnd.uniform(0, h) - t * rnd.uniform(10, 50) * u) % h
        tw = (math.sin(t * rnd.uniform(3, 7) + i) + 1) / 2
        r = rnd.uniform(1.5, 4.5) * u * (0.5 + tw)
        c = col if i % 3 else WHITE
        dr.ellipse((x - r, y - r, x + r, y + r), fill=c + (int(230 * tw * a),))
    glow = layer.filter(ImageFilter.GaussianBlur(3 * u))
    out = base.copy()
    out.alpha_composite(glow)
    out.alpha_composite(layer)
    return out


def draw_laser(base, ctx, it, t, d, mask):
    w, h, u = ctx.w, ctx.h, ctx.u
    col = col_of(it, PINK)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)
    a = env(t, d, 0.15)
    for k in range(5):
        ang = math.sin(t * (1.3 + k * 0.4) + k) * 0.9
        ox = w * (0.1 + 0.2 * k)
        x1, y1 = ox + math.sin(ang) * h * 1.2, h * 1.1
        c = col if k % 2 == 0 else LILAC
        dr.line((ox, -10, x1, y1), fill=c + (int(220 * a),), width=max(2, int(5 * u)))
    glow = layer.filter(ImageFilter.GaussianBlur(8 * u))
    out = base.copy()
    out.alpha_composite(glow)
    out.alpha_composite(glow)
    out.alpha_composite(layer)
    return out


def draw_radial(base, ctx, it, t, d, mask):
    w, h = ctx.w, ctx.h
    col = np.array(col_of(it, LILAC), np.float32) / 255
    pulse = 0.75 + 0.25 * math.sin(t * 5)
    sw, sh = w // 4, h // 4
    g = _radial(sw, sh, sw / 2, sh / 2, sw * 0.6 * pulse)[..., None] * col
    light = np.asarray(Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)).astype(np.float32) / 255
    return _add(base, light, 0.8 * env(t, d))


def draw_develop(base, ctx, it, t, d, mask):
    p = fx.ease_out(t / max(0.6, min(2.0, d * 0.6)))
    rgb = base.convert("RGB")
    sep = ImageEnhance.Color(rgb).enhance(0.15)
    sep = Image.blend(sep, Image.new("RGB", rgb.size, (250, 240, 225)), 0.35)
    white = Image.new("RGB", rgb.size, (255, 252, 248))
    stage = Image.blend(white, sep, min(1.0, p * 2)) if p < 0.5 else Image.blend(sep, rgb, (p - 0.5) * 2)
    return stage.convert("RGBA")


def _zoom(img: Image.Image, z: float, dx: float = 0, dy: float = 0) -> Image.Image:
    w, h = img.size
    cw, ch = w / z, h / z
    x0 = (w - cw) / 2 + dx
    y0 = (h - ch) / 2 + dy
    return img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((w, h), Image.BILINEAR)


def draw_zoompulse(base, ctx, it, t, d, mask):
    beat = 0.5
    k = (t % beat) / beat
    z = 1 + 0.08 * (1 - fx.ease_out(k)) * env(t, d, 0.05)
    return _zoom(base, z)


def draw_shake(base, ctx, it, t, d, mask):
    u = ctx.u
    a = env(t, d, 0.05)
    rnd = random.Random(int(t * 30))
    dx, dy = rnd.uniform(-14, 14) * u * a, rnd.uniform(-10, 10) * u * a
    return _zoom(base, 1.04, dx, dy)


def draw_rgbsplit(base, ctx, it, t, d, mask):
    u = ctx.u
    a = env(t, d, 0.05)
    off = int((6 + 10 * abs(math.sin(t * 9))) * u * a)
    r, g, b, al = base.split()
    r = r.transform(r.size, Image.AFFINE, (1, 0, off, 0, 1, 0))
    b = b.transform(b.size, Image.AFFINE, (1, 0, -off, 0, 1, 0))
    return Image.merge("RGBA", (r, g, b, al))


def draw_flash(base, ctx, it, t, d, mask):
    k = t / max(0.1, min(0.6, d))
    a = max(0.0, 1 - k) if k < 1 else 0.0
    a = min(1.0, t / 0.04) * a if t < 0.04 else a
    return _blend(base, Image.new("RGBA", base.size, WHITE + (255,)), a * 0.95)


def draw_film(base, ctx, it, t, d, mask):
    w, h, u = ctx.w, ctx.h, ctx.u
    a = env(t, d)
    rgb = base.convert("RGB")
    warm = Image.blend(rgb, Image.new("RGB", rgb.size, (240, 220, 190)), 0.12 * a)
    flick = 1 + 0.05 * math.sin(t * 37) * a
    warm = ImageEnhance.Brightness(warm).enhance(flick)
    rng = np.random.default_rng(int(t * 24))
    grain = (rng.standard_normal((h // 2, w // 2)) * 7 * a).astype(np.float32)
    grain = np.asarray(Image.fromarray(np.clip(grain + 128, 0, 255).astype(np.uint8)).resize((w, h))).astype(np.float32) - 128
    arr = np.clip(np.asarray(warm).astype(np.float32) + grain[..., None], 0, 255).astype(np.uint8)
    out = Image.fromarray(arr).convert("RGBA")
    dr = ImageDraw.Draw(out)
    rnd = random.Random(int(t * 12))
    for _ in range(2):
        x = rnd.uniform(0, w)
        dr.line((x, 0, x + rnd.uniform(-10, 10), h), fill=(255, 255, 255, int(70 * a)), width=1)
    # rounded dark frame
    fr = Image.new("L", (w, h), 0)
    ImageDraw.Draw(fr).rounded_rectangle((int(18 * u), int(18 * u), w - int(18 * u), h - int(18 * u)), int(40 * u), fill=255)
    fr = fr.filter(ImageFilter.GaussianBlur(10 * u))
    dark = Image.new("RGBA", (w, h), (18, 14, 12, 255))
    inv = Image.eval(fr, lambda v: int((255 - v) * a))
    out.paste(dark, (0, 0), inv)
    return out


def draw_vhs(base, ctx, it, t, d, mask):
    w, h, u = ctx.w, ctx.h, ctx.u
    a = env(t, d)
    out = draw_rgbsplit(base, ctx, {**it}, 1.0, 9e9, mask)
    out = _blend(base, out, a)
    arr = np.asarray(out).astype(np.float32)
    lines = (np.arange(h) % max(2, int(4 * u)) < max(1, int(2 * u))).astype(np.float32)[:, None, None]
    arr[..., :3] *= 1 - 0.12 * a * lines
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    dr = ImageDraw.Draw(out)
    f = fx.font("semi", int(40 * u))
    stamp = (it.get("title") or "").strip() or _time.strftime("%d.%m.%Y")
    dr.text((w - 40 * u, h - 40 * u), stamp, font=f, fill=(255, 240, 200, int(230 * a)), anchor="rs")
    if int(t * 2) % 2 == 0:
        dr.text((40 * u, 40 * u), "▶ PLAY", font=f, fill=(255, 255, 255, int(230 * a)), anchor="lt")
    return out


def draw_blurin(base, ctx, it, t, d, mask):
    p = fx.ease_out(t / max(0.4, min(1.2, d * 0.5)))
    r = 22 * ctx.u * (1 - p)
    if r < 0.5:
        return base
    return base.filter(ImageFilter.GaussianBlur(r))


def draw_heartframe(base, ctx, it, t, d, mask):
    w, h = ctx.w, ctx.h
    col = col_of(it, PINK)
    key = ("vheart", w, h)
    if key not in ctx.cache:
        m = Image.new("L", (w // 2, h // 2), 0)
        dr = ImageDraw.Draw(m)
        cx, cy, r = w / 4, h / 4 + h * 0.02, min(w, h) * 0.34
        pts = []
        for i in range(120):
            a = i / 120 * 2 * math.pi
            hx = 16 * math.sin(a) ** 3
            hy = 13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)
            pts.append((cx + hx * r / 16, cy - hy * r / 16))
        dr.polygon(pts, fill=255)
        ctx.cache[key] = m.filter(ImageFilter.GaussianBlur(min(w, h) * 0.03)).resize((w, h), Image.BILINEAR)
    m = ctx.cache[key]
    a = env(t, d, 0.4)
    inv = Image.eval(m, lambda v: int((255 - v) * 0.6 * a))
    out = base.copy()
    out.paste(Image.new("RGBA", (w, h), col + (255,)), (0, 0), inv)
    return out


VFX_TYPES = {
    "v_confetti": ("V", "Confetti", ("scene",)),
    "v_lightleak": ("V", "Light leak", ("scene",)),
    "v_flare": ("V", "Lens flare (pulsing)", ("scene",)),
    "v_dust": ("V", "Glitter dust", ("scene",)),
    "v_laser": ("V", "Laser lines", ("scene",)),
    "v_radial": ("V", "Radial glow", ("scene",)),
    "v_develop": ("V", "Photo develops", ("scene",)),
    "v_zoompulse": ("V", "Zoom pulse", ("scene",)),
    "v_shake": ("V", "Camera shake", ("scene",)),
    "v_rgbsplit": ("V", "RGB split", ("scene",)),
    "v_flash": ("V", "White flash", ("scene",)),
    "v_film": ("V", "Old film", ("scene",)),
    "v_vhs": ("V", "VHS", ("scene",)),
    "v_blurin": ("V", "Blur in", ("scene",)),
    "v_heartframe": ("V", "Heart frame", ("scene",)),
}

VFX_DESCRIBE = {
    "v_confetti": "Konfetti regnet – Erfolg/Feier, 2–3 s",
    "v_lightleak": "warmes Licht wandert über das Bild – Rückblick/Gefühl, 2–4 s",
    "v_flare": "pulsierender Lens-Flare – Aha-Moment/Sonne, 2 s",
    "v_dust": "glitzernder Staub – Magie/Ruhe, 2–4 s",
    "v_laser": "Laser-Linien – Party/Energie, 1–2 s",
    "v_radial": "weiches Leuchten aus der Mitte – Erkenntnis, 2 s",
    "v_develop": "Foto entwickelt sich (weiß → Farbe) – Erinnerung/Einstieg, 1–2 s",
    "v_zoompulse": "Bild pulsiert im Takt – Energie, 1–3 s",
    "v_shake": "Kamera wackelt – Schreck/Stress, 0,5–1 s",
    "v_rgbsplit": "RGB-Verschiebung – Überforderung/Glitch, 0,5–1 s",
    "v_flash": "weißer Blitz – harter Übergang/Erkenntnis, 0,3–0,6 s",
    "v_film": "alter Film (Korn, Kratzer, Rahmen) – Rückblick, 2–4 s",
    "v_vhs": "VHS-Look mit Datum (title = Datum optional) – Erinnerung, 2–4 s",
    "v_blurin": "Bild wird von unscharf zu scharf – Einstieg, 1 s",
    "v_heartframe": "farbiger Herz-Rahmen – Liebe/Selbstfürsorge, 2–3 s",
}

VFX_DRAWERS = {"v_confetti": draw_confetti, "v_lightleak": draw_lightleak, "v_flare": draw_flare,
               "v_dust": draw_dust, "v_laser": draw_laser, "v_radial": draw_radial, "v_develop": draw_develop,
               "v_zoompulse": draw_zoompulse, "v_shake": draw_shake, "v_rgbsplit": draw_rgbsplit,
               "v_flash": draw_flash, "v_film": draw_film, "v_vhs": draw_vhs, "v_blurin": draw_blurin,
               "v_heartframe": draw_heartframe}
