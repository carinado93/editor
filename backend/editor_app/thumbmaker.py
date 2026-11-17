"""YouTube-Thumbnail-Maker: KI-Hintergrund + Carina freigestellt + Titel aus 2 Wörtern, 3 Versionen zum Testen.

Look (angelehnt an George-Alexander-Thumbnails, aber in Carinas Farben – nie seine Bilder):
  1280×720 PNG < 2 MB · realistische Szene, oben dunkler · Carina groß, freigestellt, weicher Schatten,
  ihr Foto wird nie farblich verändert · oben 2 Wörter: Wort 1 Poppins Black weiß, kleiner lila "Play"-Tag,
  Wort 2 Cormorant Garamond Bold Italic weiß (oft größer) mit lila Pinsel-Unterstrich.
Layouts: top (Wort links/rechts, sie in der Mitte), two (oben Wort 1, unten groß Wort 2 über der Brust),
side (sie auf einer Seite, Wörter gestapelt auf der anderen), auto. "Text behind me": Reihenfolge
Hintergrund → Text → Carina → Doodles; jedes Wort bleibt zu ≥ 70 % sichtbar, erster Buchstabe immer.
Der Text liegt nie auf ihrem Gesicht (und vor ihr nie auf ihr selbst, außer Wort 2 im Layout "two").
"""
from __future__ import annotations

import io
import math
import random
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import ROOT

W, H = 1280, 720
FONTS = ROOT / "assets" / "fonts"
LILAC_TAG = (183, 156, 224)      # #B79CE0
LILAC = (201, 179, 236)          # Marke (fx_studio.LILAC)
PLUM = (74, 52, 110)
WHITE = (255, 255, 255)
MAX_BYTES = 2_000_000


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    files = {"black": "Poppins-Black.ttf", "script": "CormorantGaramond-BoldItalic.ttf", "hand": "Caveat.ttf"}
    return ImageFont.truetype(str(FONTS / files[name]), max(8, int(size)))


# ================================================================ Freistellen

def cutout(photo: Image.Image, segmenter=None) -> tuple[Image.Image, list[float] | None]:
    """Carina aus einem Foto freistellen → (RGBA zugeschnitten auf sie, Gesichtsbox 0..1 relativ zum Ausschnitt).
    Personen-Maske (fx.Segmenter) + Finger/Haar-Korrektur (GrabCut, Wand-/Pflanzen-Pixel raus, größte Fläche)."""
    import cv2

    from . import fx, gaze

    img = photo.convert("RGB")
    seg = segmenter or fx.Segmenter()
    try:
        m = np.asarray(seg.mask(img)).astype(np.float32) / 255
    finally:
        if segmenter is None:
            seg.close()
    m = refine_mask(np.asarray(img), m)
    face = gaze.photo_face(img)
    return crop_cutout(img, m, face)


def refine_mask(rgb: np.ndarray, m: np.ndarray) -> np.ndarray:
    """Finger/Haare retten (aus dem Cutout-Skill): GrabCut mit der Maske als Startpunkt, Wand-Pixel (hell, wenig
    Farbe) und Pflanzen-Pixel (grün) in neu dazugekommenen Stellen wieder raus, nur die größte Fläche behalten."""
    import cv2

    h, w = m.shape
    sc = 960 / max(w, h) if max(w, h) > 960 else 1.0
    small = cv2.resize(rgb, (int(w * sc), int(h * sc))) if sc != 1 else rgb.copy()
    ms = cv2.resize(m, (small.shape[1], small.shape[0]))
    gc = np.full(ms.shape, cv2.GC_BGD, np.uint8)
    near = cv2.dilate((ms > 0.3).astype(np.uint8), np.ones((25, 25), np.uint8))
    gc[near > 0] = cv2.GC_PR_BGD
    gc[ms > 0.3] = cv2.GC_PR_FGD
    gc[cv2.erode((ms > 0.8).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0] = cv2.GC_FGD
    try:
        bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        cv2.grabCut(cv2.cvtColor(small, cv2.COLOR_RGB2BGR), gc, None, bgd, fgd, 3, cv2.GC_INIT_WITH_MASK)
        g = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.float32)
    except cv2.error:
        g = (ms > 0.5).astype(np.float32)
    hsv = cv2.cvtColor(small, cv2.COLOR_RGB2HSV)
    added = (g > 0.5) & (ms < 0.5)
    wall = (hsv[..., 1] < 70) & (hsv[..., 2] > 150)
    plant = small[..., 1].astype(int) >= small[..., 0].astype(int) - 5
    g[added & (wall | plant)] = 0
    both = np.maximum(ms, g * 0.95)
    # nur die größte zusammenhängende Fläche (keine Möbel-/Pflanzen-Inseln)
    n, lab, stats, _ = cv2.connectedComponentsWithStats((both > 0.5).astype(np.uint8), 8)
    if n > 2:
        keep = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        region = cv2.dilate((lab == keep).astype(np.uint8), np.ones((15, 15), np.uint8))
        both = both * region
    both = cv2.GaussianBlur(both, (0, 0), 1.2)
    return np.clip(cv2.resize(both, (w, h)), 0, 1)


def crop_cutout(img: Image.Image, m: np.ndarray, face: list[float] | None) -> tuple[Image.Image, list[float] | None]:
    a = (np.clip(m, 0, 1) * 255).astype(np.uint8)
    rgba = img.convert("RGBA")
    rgba.putalpha(Image.fromarray(a))
    bbox = Image.fromarray(a).point(lambda v: 255 if v > 40 else 0).getbbox()
    if not bbox:
        raise ValueError("No person found in this photo.")
    cut = rgba.crop(bbox)
    cut.info["bbox"] = bbox   # wo sie im Foto steht (für "Hintergrund unscharf" ohne sie)
    fbox = None
    if face:
        x0, y0, x1, y1 = bbox
        cw, ch = x1 - x0, y1 - y0
        fbox = [(face[0] * img.width - x0) / cw, (face[1] * img.height - y0) / ch,
                (face[2] * img.width - x0) / cw, (face[3] * img.height - y0) / ch]
    return cut, fbox


# ================================================================ Bausteine

def darken_top(bg: Image.Image, strength: float = 0.5) -> Image.Image:
    """Oben dunkler, damit der weiße Text gut lesbar ist (nur der Hintergrund, nie Carina)."""
    a = np.asarray(bg.convert("RGB")).astype(np.float32)
    ramp = np.ones(H, np.float32)
    n = int(H * 0.5)
    ramp[:n] = (1 - strength) + strength * (np.linspace(0, 1, n) ** 1.3)
    return Image.fromarray(np.clip(a * ramp[:, None, None], 0, 255).astype(np.uint8))


def soft_shadow(person: Image.Image, blur: int = 16, offset=(10, 12), alpha: float = 0.5) -> Image.Image:
    a = person.getchannel("A").point(lambda v: int(v * alpha))
    sh = Image.new("RGBA", person.size, PLUM + (0,))
    sh.putalpha(a)
    pad = blur * 3
    big = Image.new("RGBA", (person.width + 2 * pad, person.height + 2 * pad), (0, 0, 0, 0))
    big.alpha_composite(sh, (pad + offset[0], pad + offset[1]))
    return big.filter(ImageFilter.GaussianBlur(blur)), pad


def play_tag(h: int) -> Image.Image:
    """Kleiner lila "Play"-Tag (abgerundet, weißes Dreieck) zwischen den Wörtern."""
    w = int(h * 1.55)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=int(h * 0.32), fill=LILAC_TAG + (255,))
    cx, cy, s = w / 2 + h * 0.06, h / 2, h * 0.24
    d.polygon([(cx - s * 0.8, cy - s), (cx - s * 0.8, cy + s), (cx + s, cy)], fill=WHITE + (255,))
    return im


def brush_stroke(width: int, thick: int, seed: int = 3) -> Image.Image:
    """Lila Pinsel-Unterstrich: leicht gewellt, an den Enden dünner."""
    rnd = random.Random(seed)
    S = 3
    im = Image.new("RGBA", (width * S, thick * 3 * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    top, bot = [], []
    steps = 40
    phase = rnd.uniform(0, 3)
    for i in range(steps + 1):
        x = i / steps * width * S
        taper = min(1.0, i / 5, (steps - i) / 5) * 0.8 + 0.2
        yc = (thick * 1.5 + math.sin(i / steps * math.pi * 1.6 + phase) * thick * 0.35) * S
        hh = thick * taper * S * rnd.uniform(0.9, 1.05) / 2
        top.append((x, yc - hh))
        bot.append((x, yc + hh))
    d.polygon(top + bot[::-1], fill=LILAC_TAG + (235,))
    return im.resize((width, thick * 3), Image.LANCZOS)


def text_sprite(txt: str, f: ImageFont.FreeTypeFont, shadow: bool = True) -> Image.Image:
    """Weißer Text mit weichem dunklen Schatten (bleibt auf hellen Stellen lesbar)."""
    box = f.getbbox(txt)
    tw, th = box[2] - box[0], box[3] - box[1]
    pad = int(f.size * 0.25)
    im = Image.new("RGBA", (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((pad - box[0] + 3, pad - box[1] + 5), txt, font=f, fill=(30, 18, 50, 150))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(max(3, f.size // 18))))
    ImageDraw.Draw(im).text((pad - box[0], pad - box[1]), txt, font=f, fill=WHITE + (255,))
    return im


def glyph_mask(txt: str, f: ImageFont.FreeTypeFont, pos: tuple[int, int]) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """Nur die Buchstaben (ohne Schatten) als Maske im ganzen Bild – für die Sichtbarkeits-Prüfung."""
    m = Image.new("L", (W, H), 0)
    box = f.getbbox(txt)
    pad = int(f.size * 0.25)
    ImageDraw.Draw(m).text((pos[0] + pad - box[0], pos[1] + pad - box[1]), txt, font=f, fill=255)
    arr = np.asarray(m) > 128
    first = Image.new("L", (W, H), 0)
    ImageDraw.Draw(first).text((pos[0] + pad - box[0], pos[1] + pad - box[1]), txt[:1], font=f, fill=255)
    fb = first.getbbox() or (0, 0, 0, 0)
    return arr, fb


# ================================================================ Aufbau

@dataclass
class Spec:
    title1: str = "burned"
    title2: str = "out."
    layout: str = "auto"          # auto | top | two | side
    behind: bool = False          # Text hinter Carina
    doodles: bool = False
    doodle_text: str = "me"
    person: dict = field(default_factory=dict)   # {"dx", "dy" (Anteil), "s" (Faktor)} – Carinas Feinschiebung
    text: dict = field(default_factory=dict)     # {"dx", "dy", "s"} – Titel verschieben/skalieren
    shade: float = 0.5            # wie stark oben abgedunkelt wird (Farb-Hintergründe haben schon Pflaume oben)


@dataclass
class Result:
    image: Image.Image
    layout: str
    face_box: tuple[int, int, int, int] | None
    word_boxes: list[tuple[int, int, int, int]]
    visible: list[float]
    warnings: list[str]
    person_box: tuple[int, int, int, int]


def _place_person(cut: Image.Image, layout: str, face: list[float] | None, scale: float, spec: Spec,
                  lower: float = 0.0):
    """Größe und Ort von Carina: groß im Bild, unten angeschnitten; Seite je nach Layout."""
    target_h = H * 0.98 * scale
    s = target_h / cut.height
    if cut.width * s > W * 0.62:
        s = W * 0.62 / cut.width
    pw, ph = int(cut.width * s), int(cut.height * s)
    cx = {"side": 0.73}.get(layout, 0.5) * W
    fcx = ((face[0] + face[2]) / 2) if face else 0.5   # das Gesicht steht an der Zielstelle, nicht der Ausschnitt
    x = int(cx - fcx * pw)
    x = max(-int(pw * 0.25), min(W - int(pw * 0.75), x))
    y = int(H - ph + ph * 0.06 + lower * H)   # Unterkante leicht angeschnitten; "lower" = tiefer setzen
    p = spec.person or {}
    x += int(float(p.get("dx", 0)) * W)
    y += int(float(p.get("dy", 0)) * H)
    if float(p.get("s", 1)) != 1:
        f = max(0.4, min(1.6, float(p.get("s", 1))))
        nw, nh = int(pw * f), int(ph * f)
        x, y = x + (pw - nw) // 2, y + (ph - nh)
        pw, ph = nw, nh
    fb = None
    if face:
        fb = (int(x + face[0] * pw), int(y + face[1] * ph), int(x + face[2] * pw), int(y + face[3] * ph))
    return (x, y, pw, ph), fb


def _overlaps(a, b, margin=0) -> bool:
    return not (a[2] + margin <= b[0] or b[2] + margin <= a[0] or a[3] + margin <= b[1] or b[3] + margin <= a[1])


def _word_layout(layout: str, t1: str, t2: str, base: int, fb, pbox, spec: Spec):
    """Liefert [(text, font, x, y)] + Tag-Position für ein Layout. base = Grundgröße Wort 1."""
    f1, f2 = font("black", base), font("script", int(base * (1.7 if layout == "two" else 1.32)))
    s1, s2 = text_sprite(t1, f1), text_sprite(t2, f2)
    tag = play_tag(int(base * 0.55))
    gap = int(base * 0.18)
    tx = spec.text or {}
    ox, oy = int(float(tx.get("dx", 0)) * W), int(float(tx.get("dy", 0)) * H)
    px, py, pw, ph = pbox
    head_top = fb[1] if fb else py + int(ph * 0.05)
    words = []
    if layout == "two":
        y1 = max(18, head_top - s1.height - 4)
        x1 = (W - (s1.width + gap + tag.width)) // 2
        words.append((t1, f1, x1 + ox, y1 + oy, s1))
        tagpos = (x1 + s1.width + gap + ox, y1 + (s1.height - tag.height) // 2 + oy)
        y2 = int(H * 0.60)
        words.append((t2, f2, (W - s2.width) // 2 + ox, y2 + oy, s2))
    elif layout == "side":
        left_side = px > W / 2
        area_x0, area_x1 = (40, max(240, px - 20)) if left_side else (px + pw + 20, W - 40)
        cx = (area_x0 + area_x1) // 2
        total = s1.height + s2.height - int(base * 0.15)
        y1 = max(30, int(H * 0.42) - total // 2)
        row1 = s1.width + gap + tag.width
        words.append((t1, f1, cx - row1 // 2 + ox, y1 + oy, s1))
        tagpos = (cx - row1 // 2 + s1.width + gap + ox, y1 + (s1.height - tag.height) // 2 + oy)
        words.append((t2, f2, cx - s2.width // 2 + ox, y1 + s1.height - int(base * 0.15) + oy, s2))
    else:  # top: eine Zeile oben – Wort 1 links, Tag, Wort 2 rechts (Kopf in der Mitte)
        line_w = s1.width + gap + tag.width + gap + s2.width
        y = max(16, min(head_top - max(s1.height, s2.height) + int(base * 0.25), int(H * 0.30)))
        if spec.behind and fb:
            # Text hinter dem Kopf: Unterkante auf Stirnhöhe – Haare überdecken die Buchstaben, Augen bleiben frei
            forehead = fb[1] + int((fb[3] - fb[1]) * 0.22)
            y = max(16, forehead - max(s1.height, s2.height) + int(base * 0.12))
        elif spec.behind:
            y = max(16, head_top - int(max(s1.height, s2.height) * 0.45))
        x0 = (W - line_w) // 2
        if fb and not spec.behind:
            # Gesicht frei halten: Wörter links und rechts vom Kopf, falls die Zeile darüber nicht passt
            if y + max(s1.height, s2.height) > fb[1] - 6:
                x_l = fb[0] - 2 * gap - tag.width - s1.width
                x_r = fb[2] + 2 * gap
                words.append((t1, f1, x_l + ox, y + oy, s1))
                tagpos = (x_l + s1.width + gap + ox, y + (s1.height - tag.height) // 2 + oy)
                words.append((t2, f2, x_r + ox, y + (s1.height - s2.height) // 2 + oy, s2))
                return words, tag, tagpos
        words.append((t1, f1, x0 + ox, y + oy, s1))
        tagpos = (x0 + s1.width + gap + ox, y + (s1.height - tag.height) // 2 + oy)
        words.append((t2, f2, x0 + s1.width + gap + tag.width + gap + ox,
                      y + (s1.height - s2.height) // 2 + oy, s2))
    return words, tag, tagpos


def _visible(words, alpha_full: np.ndarray) -> tuple[list[float], list[float]]:
    """Wie viel von jedem Wort sichtbar bleibt (Text hinter Carina) und wie viel vom ersten Buchstaben."""
    vis, first = [], []
    person = alpha_full > 128
    for txt, f, x, y, _ in words:
        gm, fb = glyph_mask(txt, f, (x, y))
        tot = gm.sum()
        vis.append(float((gm & ~person).sum() / tot) if tot else 1.0)
        fx0, fy0, fx1, fy1 = fb
        fm = gm[fy0:fy1, fx0:fx1]
        first.append(float((fm & ~person[fy0:fy1, fx0:fx1]).sum() / max(1, fm.sum())) if fm.size else 1.0)
    return vis, first


def compose(bg: Image.Image, cut: Image.Image, face: list[float] | None, spec: Spec) -> Result:
    """Ein Thumbnail bauen. Probiert Größen/Positionen, bis Text weder Gesicht verdeckt noch (bei 'behind')
    zu stark von Carina verdeckt wird; sonst Hinweis in warnings."""
    layout = spec.layout
    if layout not in ("top", "two", "side"):
        fcx = (face[0] + face[2]) / 2 if face else 0.5
        layout = "side" if abs(fcx - 0.5) > 0.18 else "top"
    t1, t2 = (spec.title1 or "").strip(), (spec.title2 or "").strip()
    user_moved = bool(spec.person or spec.text)
    # erst tiefer setzen, dann verkleinern (Carinas Vorgabe), dazu kleinere Schrift probieren
    tries = [(sc, low, base) for sc in (1.0, 0.92, 0.85, 0.78, 0.7) for low in (0.0, 0.08, 0.16)
             for base in (118, 104, 92, 80)]
    if user_moved:
        tries = [(1.0, 0.0, int(104 * max(0.4, min(2.0, float((spec.text or {}).get("s", 1))))))]
    best = None
    for sc, low, base in tries:
        pbox, fb = _place_person(cut, layout, face, sc, spec, low)
        words, tag, tagpos = _word_layout(layout, t1, t2, base, fb, pbox, spec)
        boxes = [(x, y, x + s.width, y + s.height) for _, _, x, y, s in words]
        alpha = np.zeros((H, W), np.uint8)
        pa = cut.resize((pbox[2], pbox[3]), Image.LANCZOS).getchannel("A")
        alpha_img = Image.new("L", (W, H), 0)
        alpha_img.paste(pa, (pbox[0], pbox[1]))
        alpha = np.asarray(alpha_img)
        warn = []
        inside = all(b[0] >= 10 and b[2] <= W - 10 and b[1] >= 6 and b[3] <= H - 6 for b in boxes)
        face_hit = bool(fb) and any(_overlaps(b, fb, 4) for b in boxes[:1 if layout == "two" else 2]) \
            and not spec.behind
        vis, first = _visible(words, alpha)
        if spec.behind:
            ok_vis = all(v >= 0.70 for v in vis) and all(f >= 0.8 for f in first)
            # nie über die Augen/Mund schreiben, auch nicht dahinter: Gesichtsmitte bleibt frei
            if fb:
                core = (fb[0] + (fb[2] - fb[0]) // 5, fb[1] + int((fb[3] - fb[1]) * 0.3), fb[2] - (fb[2] - fb[0]) // 5, fb[3])
                ok_vis = ok_vis and not any(_overlaps(b, core) for b in boxes)
        else:
            # vor Carina: höchstens 15 % der Buchstaben auf ihr (Wort 2 im Layout "two" darf über die Brust)
            ok_vis = all(v >= 0.85 for k, v in enumerate(vis) if not (layout == "two" and k == 1))
        good = inside and not face_hit and ok_vis
        cand = (good, sc, base, pbox, fb, words, tag, tagpos, boxes, alpha, vis)
        if good:
            best = cand
            break
        if best is None:
            best = cand
    good, sc, base, pbox, fb, words, tag, tagpos, boxes, alpha, vis = best
    warnings = []
    if not good:
        if spec.behind and any(v < 0.7 for v in vis):
            warnings.append("Part of a word is hidden behind you – move the text or yourself a little.")
        elif not all(b[0] >= 10 and b[2] <= W - 10 for b in boxes):
            warnings.append("The title is too long for this layout – use shorter words or another layout.")
        else:
            warnings.append("The text gets close to your face – try another layout or move yourself.")

    # ---------- zeichnen: Hintergrund → (Text) → Schatten + Carina → (Text) → Doodles
    canvas = darken_top(bg.convert("RGB").resize((W, H)), spec.shade).convert("RGBA")
    person = cut.resize((pbox[2], pbox[3]), Image.LANCZOS)
    sh, pad = soft_shadow(person)
    text_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for txt, f, x, y, sprite in words:
        text_layer.paste(sprite, (x, y), sprite)
        if f.path.endswith("BoldItalic.ttf"):
            uw = int(sprite.width * 0.82)
            stroke = brush_stroke(uw, max(8, int(f.size * 0.13)))
            sx, sy = x + (sprite.width - uw) // 2, y + sprite.height - int(f.size * 0.42)
            under = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            under.paste(stroke, (sx, sy), stroke)
            # Unterstrich liegt unter den Buchstaben
            tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            tmp.alpha_composite(under)
            tmp.alpha_composite(text_layer)
            text_layer = tmp
    if spec.behind:
        canvas.alpha_composite(text_layer)
    canvas.paste(sh, (pbox[0] - pad, pbox[1] - pad), sh)
    canvas.paste(person, (pbox[0], pbox[1]), person)
    if not spec.behind:
        canvas.alpha_composite(text_layer)
    if tag:  # der kleine Play-Tag liegt immer vorne und an einer freien Stelle (nie auf Kopf/Haaren)
        tx_, ty_ = tagpos
        def on_person(x, y):
            reg = alpha[max(0, y):max(0, y) + tag.height, max(0, x):max(0, x) + tag.width]
            return reg.size and reg.mean() > 25
        if on_person(tx_, ty_) and words:
            w1 = words[0]
            cand = [(w1[2] - tag.width - int(w1[1].size * 0.18), ty_)]          # vor Wort 1
            if len(words) > 1:
                w2 = words[1]
                cand.append((w2[2] + w2[4].width + int(w1[1].size * 0.1), ty_))  # nach Wort 2
            for cx_, cy_ in cand:
                if 8 <= cx_ <= W - tag.width - 8 and not on_person(cx_, cy_):
                    tx_, ty_ = cx_, cy_
                    break
        canvas.paste(tag, (tx_, ty_), tag)
    if spec.doodles:
        canvas.alpha_composite(doodles(pbox, fb, boxes, spec.doodle_text))
    return Result(canvas.convert("RGB"), layout, fb, boxes, vis, warnings, (pbox[0], pbox[1], pbox[0] + pbox[2], pbox[1] + pbox[3]))


def doodles(pbox, fb, boxes, label: str = "me") -> Image.Image:
    """Lila Handzeichnungen auf der freien Seite: gewellte Linie mit Kreisen (wie ein Graph), Pfeil zu Carina,
    kleine Notiz in Caveat. Alles unterhalb des Titels, nie über Text oder Gesicht."""
    S = 2
    lay = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    col = LILAC_TAG + (255,)
    px, py, pw, ph = pbox
    space_r, space_l = W - (px + pw), px
    right = space_r >= space_l
    x0, x1 = ((px + pw + 30, W - 40) if right else (40, px - 30))
    if x1 - x0 < 160:
        return lay.resize((W, H), Image.LANCZOS)
    text_bottom = max([b[3] for b in boxes] or [0])
    gy = max(text_bottom + 150, int(H * 0.70))
    gy = min(gy, H - 40)
    gx0, gx1 = x0 + 10, min(x1, x0 + 250)
    pts = []
    for i in range(7):
        x = gx0 + (gx1 - gx0) * i / 6
        y = gy - i * 14 + math.sin(i * 1.7) * 14
        pts.append((x, y))
    d.line([(x * S, y * S) for x, y in pts], fill=col, width=5 * S, joint="curve")
    for x, y in pts[1::2]:
        d.ellipse(((x - 9) * S, (y - 9) * S, (x + 9) * S, (y + 9) * S), outline=col, width=4 * S)
    # Pfeil vom Ende des Graphen zu Carina (Schulterhöhe), leicht gebogen
    # Pfeil beginnt am Ende des Graphen, das Carina am nächsten ist, und endet kurz vor ihr
    near = pts[0] if right else pts[-1]
    ax0, ay0 = near[0], near[1] - 40
    tx = (px + pw * 0.12) if right else (px + pw * 0.08)
    if not right:
        tx = px - 12
    else:
        tx = px + pw + 12
    ty = max(text_bottom + 40, (fb[3] + 60) if fb else py + ph * 0.4)
    ctrl = ((ax0 + tx) / 2, min(ay0, ty) - 50)
    curve = [((1 - k) ** 2 * ax0 + 2 * (1 - k) * k * ctrl[0] + k * k * tx,
              (1 - k) ** 2 * ay0 + 2 * (1 - k) * k * ctrl[1] + k * k * ty) for k in (i / 24 for i in range(25))]
    d.line([(x * S, y * S) for x, y in curve], fill=col, width=4 * S, joint="curve")
    (xa, ya), (xb, yb) = curve[-3], curve[-1]
    ang = math.atan2(yb - ya, xb - xa)
    for s_ in (-1, 1):
        d.line([(xb * S, yb * S), ((xb - 22 * math.cos(ang + s_ * 0.5)) * S, (yb - 22 * math.sin(ang + s_ * 0.5)) * S)],
               fill=col, width=4 * S)
    if label.strip():
        f = font("hand", 44 * S)
        lx = (gx0 + gx1) / 2
        d.text((lx * S, (gy + 46) * S), label.strip(), font=f, fill=col, anchor="mm")
    return lay.resize((W, H), Image.LANCZOS)


def to_png(img: Image.Image) -> bytes:
    """PNG unter 2 MB (sonst weniger Farben – bei Fotos kaum sichtbar)."""
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    if buf.tell() <= MAX_BYTES:
        return buf.getvalue()
    for colors in (256, 192, 128):
        buf = io.BytesIO()
        img.quantize(colors=colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG).save(
            buf, "PNG", optimize=True)
        if buf.tell() <= MAX_BYTES:
            return buf.getvalue()
    return buf.getvalue()
