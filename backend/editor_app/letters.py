"""Letter Carousel Studio: Briefe/Gedichte als 3 Instagram-Karussells (The Long Exhale / Lieber Schatten, liebes Ich).

Das Zeichnen ist eine 1:1-Übertragung von Carinas Referenz-Code (sty.py, sty3.py, dog2.py, soft.py, heartbase.py):
gleiche Maße, Farben, Schriftgrößen, Drehungen, Papier-Körnung und Weichzeichnung. Bitte Zahlen hier nur ändern,
wenn Carina es ausdrücklich möchte – die Slides sollen aussehen wie die bereits geposteten.

Stile:
  storyteller  Papier (Creme/Salbei), Cormorant Italic + Allison-Zeilen, ein Aquarell-Motiv (multipliziert)
  painted      Vollbild-Gemälde (soften + dunkler Verlauf oben), cremefarbene Allison-Schrift mit Schatten
"""
from __future__ import annotations

import io
import json
import re
import shutil
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from .config import ROOT
from .errors import UserError

W, H = 1080, 1350
FONTS = ROOT / "assets" / "fonts"
ASSETS = ROOT / "assets" / "letters"
DIR = ROOT / "daten" / "briefe"

AL = str(FONTS / "Allison-Regular.ttf")
CGI = str(FONTS / "CormorantGaramond-MediumItalic.ttf")
CG = str(FONTS / "CormorantGaramond-Medium.ttf")
JO = str(FONTS / "JosefinSans-Light.ttf")

INK = (84, 92, 72)
SOFT = (128, 134, 116)
PUR = (88, 72, 104)
GRN = (96, 106, 84)
SAGE = (226, 231, 214)
CREAM = (248, 243, 232)
PAINT_CREAM = (246, 238, 220)

ACCOUNTS = {
    "en": {"handle": "thelongexhale.book", "blog_id": 7940042, "book": "THE LONG EXHALE",
           "label": "A LETTER TO MY ANXIETY", "soon": "en_coming_soon.jpg", "soon_name": "coming-soon",
           "hashtags": "#TheLongExhale #poetry #anxiety #depression #selfcompassion",
           "parts": [("PART 1", "HOLDING MY BREATH", "Part 1 - Holding my breath"),
                     ("PART 2", "LETTING GO", "Part 2 - Letting go"),
                     ("PART 3", "AFTER THE NOISE", "Part 3 - After the noise")]},
    "de": {"handle": "lieberschatten.buch", "blog_id": 7940724, "book": "LIEBER SCHATTEN, LIEBES ICH",
           "label": "BRIEF AN MEINE ANGST", "soon": "de_demnaechst.jpg", "soon_name": "demnaechst",
           "hashtags": "#LieberSchattenLiebesIch #gedichte #angst #depression #selbstmitgefühl",
           "parts": [("TEIL 1", "DEN ATEM ANHALTEN", "Teil 1 - Den Atem anhalten"),
                     ("TEIL 2", "LOSLASSEN", "Teil 2 - Loslassen"),
                     ("TEIL 3", "NACH DEM LÄRM", "Teil 3 - Nach dem Laerm")]},
}
FORBIDDEN = re.compile(r"stress\s*(&|and|und)\s*burnout[\s-]*coach", re.I)

ILLU_PROMPT = ("Delicate watercolor illustration of {motif}, soft muted sage, grey and warm cream tones, loose brush "
               "strokes, gentle and poetic, isolated on a plain white background, no text, no frame")
PAINT_PROMPT = ("Expressive oil painting painted edge to edge, {scene}, soft muted sage, olive and warm lamp-light "
                "tones, quiet melancholic storybook mood, no white background, no text, no frame")


# ================================================================ A1 · sty.py

def paper(color=CREAM) -> Image.Image:
    bg = np.zeros((H, W, 3), float)
    bg[:] = color
    rng = np.random.default_rng(7)
    n = rng.normal(0, 1, (H, W))
    n = np.array(Image.fromarray((n * 25 + 128).clip(0, 255).astype("uint8")).filter(
        ImageFilter.GaussianBlur(1.2))).astype(float) - 128
    bg += (n / 25 * 2.4)[:, :, None]
    return Image.fromarray(bg.clip(0, 255).astype("uint8"))


def ctext(d, t, fp, sz, y, fill, sp=0):
    f = ImageFont.truetype(fp, sz)
    if sp:
        w = sum(d.textlength(c, font=f) for c in t) + sp * (len(t) - 1)
        x = (W - w) / 2
        for c in t:
            d.text((x, y), c, font=f, fill=fill)
            x += d.textlength(c, font=f) + sp
    else:
        w = d.textlength(t, font=f)
        d.text(((W - w) / 2, y), t, font=f, fill=fill)


def leaf(d, cx, cy, s=22, fill=(150, 166, 138), vein=CREAM):
    d.polygon([(cx, cy + s), (cx - s * 0.55, cy), (cx, cy - s), (cx + s * 0.55, cy)], fill=fill)
    d.line((cx, cy + s, cx, cy - s * 0.6), fill=vein, width=2)


# ================================================================ A2 · sty3.py

def script(img, t, size, y, rot, col, cy):
    S = 2
    L = Image.new("L", (W * S, H * S), 0)
    ld = ImageDraw.Draw(L)
    f = ImageFont.truetype(AL, size * S)
    w = ld.textlength(t, font=f)
    ld.text(((W * S - w) / 2, y * S), t, font=f, fill=255, stroke_width=2, stroke_fill=255)
    L = L.rotate(rot, resample=Image.BICUBIC, center=(W * S / 2, cy * S)).resize((W, H), Image.LANCZOS)
    a = np.array(L).astype(float) / 255
    o = np.array(img).astype(float) * (1 - a[:, :, None]) + np.array(col, float) * a[:, :, None]
    return Image.fromarray(o.astype("uint8"))


# ================================================================ A3 · dog2.py slide()

def footer_l(d, book, bg=CREAM):
    leaf(d, W // 2, 1262, vein=bg)
    ctext(d, f"CARINA DORCA  ·  {book}", JO, 22 if len(book) > 16 else 24, 1295, SOFT, sp=4 if len(book) > 16 else 5)


def _art_image(path: Path) -> Image.Image:
    a = Image.open(path).convert("RGB")
    arr = np.array(a)
    b = int(min(a.size) * 0.02)  # 2 % Rand weiß machen (Rahmenlinien weg)
    arr[:b, :] = 255
    arr[-b:, :] = 255
    arr[:, :b] = 255
    arr[:, -b:] = 255
    m = (arr.astype(int).sum(2) < 735)
    ys, xs = np.where(m)
    if not len(xs):
        raise UserError("The illustration is empty (only white).")
    return Image.fromarray(arr).crop((max(0, xs.min() - 12), max(0, ys.min() - 12),
                                      min(a.width, xs.max() + 12), min(a.height, ys.max() + 12)))


def slide(blocks, book, bg=CREAM, art=None, cap=None):
    """blocks: ['t', [zeilen], größe, farbe] | ['s', text, größe, farbe] | ['g', px]. art: (pfad, breite, cy)."""
    blocks = [list(b) for b in blocks]
    img = paper(bg)
    y0, y1 = 140, 1215
    if cap:
        y0 = 170
    if art:
        path, w, cy = art
        a = _art_image(Path(path))
        h = int(a.height * w / a.width)
        if h > 520:
            w = int(w * 520 / h)
            h = 520
        a = a.resize((w, h), Image.LANCZOS)
        top = min(cy - h // 2, 1210 - h)
        L = Image.new("RGB", (W, H), (255, 255, 255))
        L.paste(a, ((W - w) // 2, top))
        img = ImageChops.multiply(img, L)
        y1 = top - 25
    d = ImageDraw.Draw(img)
    hs = []
    for b in blocks:
        if b[0] == "t":
            hs.append(len(b[1]) * int(b[2] * 1.27))
        elif b[0] == "s":
            sz = b[2]
            f = ImageFont.truetype(AL, sz)
            while d.textlength(b[1], font=f) > 900:
                sz -= 6
                f = ImageFont.truetype(AL, sz)
            b[2] = sz
            hs.append(int(sz * 0.95))
        else:
            hs.append(b[1])
    y = y0 + max(0, int((y1 - y0 - sum(hs)) * (0.5 if art else 0.42)))
    for b, h in zip(blocks, hs):
        if b[0] == "t":
            d = ImageDraw.Draw(img)
            lh = int(b[2] * 1.27)
            sz = b[2]
            f = ImageFont.truetype(CGI, sz)
            while max(d.textlength(ln, font=f) for ln in b[1]) > 960:
                sz -= 2
                f = ImageFont.truetype(CGI, sz)
            for i, ln in enumerate(b[1]):
                ctext(d, ln, CGI, sz, y + i * lh, b[3] if len(b) > 3 else INK)
        elif b[0] == "s":
            img = script(img, b[1], b[2], int(y - b[2] * 0.12), 2, b[3], int(y + h / 2))
        y += h
    d = ImageDraw.Draw(img)
    if cap:
        ctext(d, cap[0], JO, 24, 52, SOFT, sp=6)
        ctext(d, cap[1], JO, 21, 90, SOFT, sp=5)
    footer_l(d, book, bg)
    return img


# ================================================================ A4 · soft.py

def soften(im, level=1):
    im = im.convert("RGB")
    if not level:
        return im
    m, b, col, con, cr = {1: (5, 1.6, 0.62, 0.78, 0.20), 2: (9, 2.6, 0.52, 0.70, 0.28),
                          3: (11, 3.4, 0.45, 0.64, 0.34)}[int(level)]
    small = im.resize((im.width // 2, im.height // 2), Image.LANCZOS)
    small = small.filter(ImageFilter.MedianFilter(m)).filter(ImageFilter.ModeFilter(5))
    im = small.resize(im.size, Image.LANCZOS).filter(ImageFilter.GaussianBlur(b))
    im = ImageEnhance.Color(im).enhance(col)
    im = ImageEnhance.Contrast(im).enhance(con)
    a = np.array(im).astype(float)
    a = a * (1 - cr) + np.array([240, 235, 219.]) * cr
    rng = np.random.default_rng(3)
    n = rng.normal(0, 1, a.shape[:2])
    n = np.array(Image.fromarray((n * 40 + 128).clip(0, 255).astype("uint8")).filter(
        ImageFilter.GaussianBlur(1.2))).astype(float) - 128
    bl = rng.normal(0, 1, (a.shape[0] // 40 + 1, a.shape[1] // 40 + 1))
    bl = np.array(Image.fromarray(((bl * 30) + 128).clip(0, 255).astype("uint8")).resize(
        (a.shape[1], a.shape[0]), Image.BICUBIC)).astype(float) - 128
    a += (n / 40 * 3.5)[:, :, None] + (bl / 30 * 4)[:, :, None]
    return Image.fromarray(a.clip(0, 255).astype("uint8"))


# ================================================================ A5 · heartbase.py

S2 = 2


def bgimg(path, level=1, zoom=1.0, fx=0.5, fy=0.5, top=0.42, amt=0.9):
    im = soften(Image.open(path).convert("RGB"), level)
    sc = max(W / im.width, H / im.height) * zoom
    im = im.resize((int(im.width * sc) + 1, int(im.height * sc) + 1), Image.LANCZOS)
    x = int((im.width - W) * fx)
    y = int((im.height - H) * fy)
    im = im.crop((x, y, x + W, y + H))
    a = np.array(im).astype(float) * amt
    g = np.ones(H)
    n = int(H * 0.55)
    g[:n] = top + (1 - top) * (np.linspace(0, 1, n) ** 1.2)
    a = a * g[:, None, None]
    return Image.fromarray(np.clip(a, 0, 255).astype("uint8"))


def comp(im, L, col=PAINT_CREAM, shadow=True):
    L = L.resize((W, H), Image.LANCZOS)
    a = np.array(L).astype(float) / 255
    o = np.array(im).astype(float)
    if shadow:
        sh = np.array(L.filter(ImageFilter.GaussianBlur(7))).astype(float) / 255
        o = o * (1 - sh[:, :, None] * 0.5)
    o = o * (1 - a[:, :, None]) + np.array(col, float) * a[:, :, None]
    return Image.fromarray(o.astype("uint8"))


def lines_layer(lines, y0, size, rot, maxw=1000, lh=0.92, big=None):
    """big: Zeilen-Nummern, die hervorgehoben werden (*Zeile*) – 15 % größer."""
    big = big or set()
    f = ImageFont.truetype(AL, size * S2)
    fb = ImageFont.truetype(AL, int(size * 1.15) * S2)
    d0 = ImageDraw.Draw(Image.new("L", (10, 10)))
    mw = max(d0.textlength(ln, font=fb if k in big else f) for k, ln in enumerate(lines)) / S2
    if mw > maxw:
        size = int(size * maxw / mw)
        f = ImageFont.truetype(AL, size * S2)
        fb = ImageFont.truetype(AL, int(size * 1.15) * S2)
    L = Image.new("L", (W * S2, H * S2), 0)
    d = ImageDraw.Draw(L)
    y = y0 * S2
    for k, ln in enumerate(lines):
        ff = fb if k in big else f
        w = d.textlength(ln, font=ff)
        d.text(((W * S2 - w) / 2, y), ln, font=ff, fill=255, stroke_width=2, stroke_fill=255)
        y += int((size * 1.15 if k in big else size) * lh) * S2
    return L.rotate(rot, resample=Image.BICUBIC, center=(W * S2 / 2, (y0 + 200) * S2))


def caps(txt, y, sz, sp):
    L = Image.new("L", (W * S2, H * S2), 0)
    d = ImageDraw.Draw(L)
    f = ImageFont.truetype(JO, sz * S2)
    w = sum(d.textlength(c, font=f) for c in txt) + sp * S2 * (len(txt) - 1)
    x = (W * S2 - w) / 2
    for c in txt:
        d.text((x, y * S2), c, font=f, fill=255)
        x += d.textlength(c, font=f) + sp * S2
    return L


def pscript(txt, y, sz, rot=0):
    L = Image.new("L", (W * S2, H * S2), 0)
    d = ImageDraw.Draw(L)
    f = ImageFont.truetype(AL, sz * S2)
    w = d.textlength(txt, font=f)
    d.text(((W * S2 - w) / 2, y * S2), txt, font=f, fill=255, stroke_width=2, stroke_fill=255)
    if rot:
        L = L.rotate(rot, resample=Image.BICUBIC, center=(W * S2 / 2, (y + 100) * S2))
    return L


def poem(path, lines, y0=30, size=130, rot=2.5, maxw=1000, big=None, **kw):
    im = bgimg(path, **kw)
    L = lines_layer(lines, y0, size, rot, maxw, big=big)
    im = comp(im, L)
    return comp(im, L, shadow=False)


def cover(path, top_caps, title_lines, tsize=185, ty=95, rot=2, book="LIEBER SCHATTEN, LIEBES ICH", sub=None,
          part=None, **kw):
    im = bgimg(path, **kw)
    a = np.array(im).astype(float)
    g = np.ones(H)
    n = int(H * 0.28)
    g[-n:] = 1 - 0.5 * np.linspace(0, 1, n) ** 1.3
    im = Image.fromarray(np.clip(a * g[:, None, None], 0, 255).astype("uint8"))
    a = np.array(im).astype(float)
    band = np.array([64, 66, 46.])
    h = int(H * 0.36)
    m = np.zeros(H)
    m[:h] = 0.9 * (1 - np.linspace(0, 1, h) ** 2.2)
    a = a * (1 - m[:, None, None]) + band * m[:, None, None]
    im = Image.fromarray(a.astype("uint8"))
    im = comp(im, caps(top_caps, 52, 26, 6))
    if part:  # Teil-Zeile unter dem Label (wie im geposteten "Dear heart"-Cover)
        im = comp(im, caps(part, 88, 20, 5))
    L = lines_layer(title_lines, ty, tsize, rot, maxw=1000, lh=0.98)
    im = comp(im, L)
    im = comp(im, L, shadow=False)
    im = comp(im, pscript("Carina Dorca", 1120, 105))
    im = comp(im, caps(book, 1265, 28, 8))
    if sub:
        im = comp(im, lines_layer(sub, ty + len(title_lines) * int(tsize * 0.98) + 10, 95, rot, maxw=980, lh=0.95))
    return im


# ================================================================ Text → Folien

def _is_script(line: str) -> bool:
    s = line.strip()
    return len(s) > 2 and s.startswith("*") and s.endswith("*")


def _plain(line: str) -> str:
    return line.strip().strip("*").strip()


def split_text(text: str) -> tuple[list[list[str]], bool]:
    """Leerzeile = neue Folie. Ohne Leerzeilen: selbst teilen (2–5 kurze Zeilen, nie mitten im Satz).
    Gibt (folien, automatisch_geteilt) zurück. Carinas Wörter werden nie verändert."""
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return [], False
    if re.search(r"\n\s*\n", text):
        return [[ln.rstrip() for ln in block.split("\n") if ln.strip()] for block in re.split(r"\n\s*\n", text)
                if block.strip()], False
    lines = [ln.rstrip() for ln in text.split("\n") if ln.strip()]
    slides, cur = [], []
    for ln in lines:
        cur.append(ln)
        ends = bool(re.search(r"[.!?…:;,–—]\"?$|\*$", ln.strip()))
        sentence_end = bool(re.search(r"[.!?…]\"?\*?$", ln.strip()))
        if len(cur) >= 5 or (len(cur) >= 2 and sentence_end) or (len(cur) >= 4 and ends):
            slides.append(cur)
            cur = []
    if cur:
        if slides and len(cur) == 1 and len(slides[-1]) < 5:
            slides[-1].append(cur[0])
        else:
            slides.append(cur)
    return slides, True


def default_slide(lines: list[str], index: int, total: int) -> dict:
    # wie in den geposteten Karussells: Cover + 2. Folie Creme, dann abwechselnd (3. Salbei …)
    return {"lines": lines, "bg": "sage" if index >= 2 and index % 2 == 0 else "cream",
            "image": None, "motif": "", "zoom": 1.0, "fx": 0.5, "fy": 0.5,
            # Motiv auf dem Cover, etwa jede 3. Folie und auf der letzten Text-Folie
            "wants_art": index == 0 or index % 3 == 0 or index == total - 1}


def storyteller_blocks(lines: list[str], is_cover: bool) -> list:
    blocks: list = []
    text: list[str] = []
    after_script = False

    def flush():
        nonlocal text
        if text:
            if blocks:
                blocks.append(["g", 30])
            blocks.append(["t", text, 58 if after_script else 64, SOFT if after_script else INK])
            text = []

    for k, ln in enumerate(lines):
        if _is_script(ln) or (is_cover and k == 0):  # die Anrede auf dem Cover ist immer Schrift (grün)
            flush()
            if blocks:
                blocks.append(["g", 10 if is_cover else 30])
            address = is_cover and k == 0
            blocks.append(["s", _plain(ln), 170 if address else 180, GRN if address else PUR])
            after_script = not address
        else:
            text.append(ln.strip())
    flush()
    return blocks


def _image_path(lid: str, name: str | None) -> Path | None:
    if not name:
        return None
    p = _dir(lid) / "bilder" / name
    return p if p.exists() else None


def render_slide(letter: dict, lang: str, part_idx: int, slide_idx: int) -> Image.Image:
    acc = ACCOUNTS[lang]
    part = letter["parts"][lang][part_idx]
    sl = part["slides"][slide_idx]
    lines = sl["lines"]
    if FORBIDDEN.search(" ".join(lines)):
        raise UserError('The words "stress & burnout coach" must never appear on these slides.')
    is_cover = slide_idx == 0
    p_label, p_name, _ = acc["parts"][part_idx]
    part_line = f"{p_label}  ·  {p_name}"
    img_path = _image_path(letter["id"], sl.get("image"))
    if part.get("style") == "painted":
        if img_path is None:
            raise UserError(f"Part {part_idx + 1}, slide {slide_idx + 1}: please add a painting (upload or generate).")
        kw = {"level": int(part.get("acrylic", 1)), "zoom": float(sl.get("zoom", 1.0)),
              "fx": float(sl.get("fx", 0.5)), "fy": float(sl.get("fy", 0.5))}
        if is_cover:
            title = [_plain(lines[0])] if lines else [letter.get("title", "")]
            sub = [_plain(x) for x in lines[1:]] or None
            return cover(img_path, acc["label"], title, tsize=200, book=acc["book"], sub=sub, part=part_line, **kw)
        big = {k for k, ln in enumerate(lines) if _is_script(ln)}
        return poem(img_path, [_plain(x) for x in lines], y0=30, size=130, big=big, **kw)
    bg = SAGE if sl.get("bg") == "sage" else CREAM
    art = (str(img_path), 560 if is_cover else 480, 930 if is_cover else 980) if img_path else None
    return slide(storyteller_blocks(lines, is_cover), acc["book"], bg=bg, art=art,
                 cap=(acc["label"], part_line) if is_cover else None)


def soon_image(lang: str) -> Image.Image:
    return Image.open(ASSETS / ACCOUNTS[lang]["soon"]).convert("RGB").resize((W, H), Image.LANCZOS)


# ================================================================ Speicher

def _dir(lid: str) -> Path:
    if not re.fullmatch(r"[\w-]+", lid or ""):
        raise UserError("Unknown letter.")
    return DIR / lid


def tomorrow_times() -> list[str]:
    d = (date.today() + timedelta(days=1)).isoformat()
    return [f"{d}T18:00:00", f"{d}T19:00:00", f"{d}T20:00:00"]


def new_letter(title: str, number: str, langs: list[str]) -> dict:
    langs = [x for x in langs if x in ACCOUNTS] or ["en"]
    lid = time.strftime("%Y%m%d-%H%M%S")
    times = tomorrow_times()
    letter = {"id": lid, "title": title.strip(), "number": number.strip() or "01", "langs": langs,
              "created": time.time(), "parts": {}}
    for lang in langs:
        letter["parts"][lang] = [{"text": "", "style": "storyteller", "acrylic": 1, "time": times[k],
                                  "caption": f"\n\n{ACCOUNTS[lang]['hashtags']}", "slides": [], "auto_split": False,
                                  "files": [], "scheduled": None}
                                 for k in range(3)]
    return save(letter)


def save(letter: dict) -> dict:
    d = _dir(letter["id"])
    (d / "bilder").mkdir(parents=True, exist_ok=True)
    (d / "brief.json").write_text(json.dumps(letter, ensure_ascii=False, indent=1), encoding="utf-8")
    return letter


def load(lid: str) -> dict:
    f = _dir(lid) / "brief.json"
    if not f.exists():
        raise UserError("This letter does not exist any more.")
    return json.loads(f.read_text(encoding="utf-8"))


def list_all() -> list[dict]:
    out = []
    for f in sorted(DIR.glob("*/brief.json"), reverse=True):
        try:
            b = json.loads(f.read_text(encoding="utf-8"))
            out.append({"id": b["id"], "title": b.get("title", ""), "number": b.get("number", ""),
                        "langs": b.get("langs", [])})
        except (OSError, ValueError, KeyError):
            continue
    return out


def delete(lid: str) -> None:
    shutil.rmtree(_dir(lid), ignore_errors=True)


def hashtag_count(caption: str) -> int:
    return len(re.findall(r"(?<!\w)#\w+", caption))


def set_text(letter: dict, lang: str, idx: int, text: str) -> dict:
    """Text eines Teils setzen → Folien neu aufteilen (Bilder/Einstellungen gleich gebliebener Folien bleiben)."""
    part = letter["parts"][lang][idx]
    part["text"] = text
    groups, auto = split_text(text)
    old = part.get("slides", [])
    part["slides"] = []
    for k, lines in enumerate(groups):
        s = default_slide(lines, k, len(groups))
        if k < len(old):
            for key in ("bg", "image", "motif", "zoom", "fx", "fy"):
                if key in old[k]:
                    s[key] = old[k][key]
        part["slides"].append(s)
    part["auto_split"] = auto
    return letter


def render_part(letter: dict, lang: str, idx: int) -> list[str]:
    """Alle Folien eines Teils als PNG (Archiv) + JPG (Metricool). Letzte Folie: Coming soon / Demnächst."""
    part = letter["parts"][lang][idx]
    if not part["slides"]:
        raise UserError(f"Part {idx + 1} ({lang.upper()}) has no text yet.")
    out = _dir(letter["id"]) / "out" / lang / f"teil{idx + 1}"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    stamp = int(time.time())
    files = []
    imgs = [render_slide(letter, lang, idx, k) for k in range(len(part["slides"]))] + [soon_image(lang)]
    for k, im in enumerate(imgs, 1):
        name = f"{k:02d}_{stamp}"
        im.convert("RGB").save(out / f"{name}.png", "PNG", optimize=True)
        im.convert("RGB").save(out / f"{name}.jpg", "JPEG", quality=92)
        files.append(name)
    part["files"] = files
    return files


def preview_png(letter: dict, lang: str, idx: int, slide_idx: int, scale: float = 0.5) -> bytes:
    im = render_slide(letter, lang, idx, slide_idx)
    if scale != 1:
        im = im.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def out_file(lid: str, lang: str, idx: int, name: str) -> Path:
    if lang not in ACCOUNTS or not re.fullmatch(r"\d{2}_\d+\.(png|jpg)", name):
        raise UserError("File not found.")
    f = _dir(lid) / "out" / lang / f"teil{idx + 1}" / name
    if not f.is_file():
        raise UserError("File not found.")
    return f


def zip_bytes(letter: dict) -> bytes:
    """{NN} - {Titel}/Part 1 - Holding my breath/01.png … 10-coming-soon.png (DE: Teil …/…-demnaechst.png)."""
    buf = io.BytesIO()
    root = f"{letter.get('number', '01')} - {letter.get('title', 'Letter')}".strip()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for lang in letter["langs"]:
            acc = ACCOUNTS[lang]
            base = root if len(letter["langs"]) == 1 else f"{root}/{lang.upper()}"
            for idx, part in enumerate(letter["parts"][lang]):
                files = part.get("files") or []
                if not files:
                    continue
                for k, name in enumerate(files, 1):
                    last = k == len(files)
                    arc = f"{base}/{acc['parts'][idx][2]}/{k:02d}{'-' + acc['soon_name'] if last else ''}.png"
                    z.write(_dir(letter["id"]) / "out" / lang / f"teil{idx + 1}" / f"{name}.png", arc)
                z.writestr(f"{base}/{acc['parts'][idx][2]}/caption.txt", part.get("caption", ""))
    return buf.getvalue()


# ================================================================ Claude: Motive + Captions vorschlagen

SUGGEST_SCHEMA = {
    "type": "object",
    "properties": {"parts": {"type": "array", "items": {"type": "object", "properties": {
        "caption": {"type": "string"},
        "motifs": {"type": "array", "items": {"type": "string"}}},
        "required": ["caption", "motifs"], "additionalProperties": False}}},
    "required": ["parts"], "additionalProperties": False,
}


def suggest(letter: dict, lang: str, engine: str = "claude") -> dict:
    """Pro Teil: eine ruhige Caption (1–2 Sätze) und pro Folie ein Bild-Motiv. Carinas Text bleibt unverändert."""
    parts = letter["parts"][lang]
    listing = []
    for k, p in enumerate(parts):
        listing.append(f"TEIL {k + 1} (Stil: {'Gemälde, ganze Szene' if p['style'] == 'painted' else 'Aquarell-Motiv auf Weiß'}):")
        for j, s in enumerate(p["slides"]):
            listing.append(f"  Folie {j + 1}: " + " / ".join(_plain(x) for x in s["lines"]))
    sprache = "Deutsch" if lang == "de" else "Englisch"
    prompt = f"""Carina veröffentlicht einen Brief/ein Gedicht ("{letter.get('title', '')}") als 3 Instagram-Karussells
für ihr Buch {ACCOUNTS[lang]['book']}. Hier ist ihr Text, schon in Folien geteilt:

{chr(10).join(listing)}

Aufgaben:
1. caption pro Teil: ruhig, 1–2 kurze Sätze auf {sprache}, KEINE Hashtags, keine Emojis-Flut, nicht verkäuferisch.
   Die Worte "stress & burnout coach" dürfen nie vorkommen.
2. motifs pro Teil: für JEDE Folie genau ein kurzes Bild-Motiv auf Englisch (für einen Bild-Generator), passend zur
   Zeile. Aquarell-Stil: ein einzelnes Motiv (z. B. "a smoky half-transparent black dog sitting beside a chair").
   Gemälde-Stil: eine ganze Szene (z. B. "a quiet bedroom at night, a woman on the bed, a warm lamp").
   Bei Angst/Depression/"black dog": schattenhafte, rauchige, halbtransparente Figuren – nie wörtlich oder gruselig.
Ändere Carinas Text nie. Antworte NUR mit JSON nach dem Schema."""
    if engine == "claude":
        from . import claude
        raw = claude.ask_json(prompt, SUGGEST_SCHEMA, effort="low")
    else:
        from . import llm
        raw = llm.ask_json(prompt, "Du antwortest ausschließlich mit gültigem JSON.", timeout=600)
    got = raw.get("parts", []) if isinstance(raw, dict) else []
    tags = ACCOUNTS[lang]["hashtags"]
    for k, p in enumerate(parts):
        if k >= len(got):
            break
        cap = FORBIDDEN.sub("", str(got[k].get("caption", "")).strip())
        cap = re.sub(r"(?<!\w)#\w+", "", cap).strip()
        if cap:
            p["caption"] = f"{cap}\n\n{tags}"
        for j, s in enumerate(p["slides"]):
            motifs = got[k].get("motifs", [])
            if j < len(motifs) and not s.get("motif"):
                s["motif"] = str(motifs[j]).strip()
    return letter


def image_prompt(part: dict, slide: dict) -> str:
    m = slide.get("motif") or "a quiet, gentle scene"
    return (PAINT_PROMPT if part.get("style") == "painted" else ILLU_PROMPT).format(motif=m, scene=m)


# ================================================================ Übergabe an Claude (Metricool + Canva)

CLAUDE_MD = """# Letter carousel "{title}" ({number}) – instructions for Claude

Carina's Video-Editor app prepared this folder. Use Carina's **Metricool** and **Canva** connections.
Never change her words, captions or slide order. The words "stress & burnout coach" must never appear.

## A · "schedule" → job.json
For every entry in `posts` of `job.json`, call Metricool **createScheduledPost** with exactly
`blogId`, `date` and `info` (pass `info` as JSON, unchanged; media are public URLs in the right order,
the last one is the Coming soon / Demnächst slide). Do not add music, do not edit the text.
Then write `scheduled.json` in this folder: a list of objects
`{{"lang": "en", "part": 1, "ok": true, "plannerUrl": "…"}}` (or `"ok": false, "error": "…"`) and commit it to
branch `{branch}` of `{repo}`. If a post fails, schedule the others anyway.

## B · "pictures" → pictures.json
For every entry, create ONE image with Canva AI using `prompt` exactly (style notes are inside the prompt).
Storyteller = single watercolor motif on a plain white background; Painted Scene = full-bleed painting, portrait 4:5.
Soft and poetic; for anxiety / depression / "black dog" use shadowy, smoky, half-transparent figures, never scary.
Download each result as PNG or JPG and save it as `art/<file>` in this folder (file names are given), then commit
everything in one commit to branch `{branch}` of `{repo}`. Carina presses "Get pictures" in the app afterwards.
"""


def folder(letter: dict) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", letter.get("title", "letter").lower()).strip("-") or "letter"
    return f"media/letters/{letter.get('number', '01')}-{slug}"


def berlin_offset(dt: str) -> str:
    """UTC-Abstand für Europe/Berlin (Sommerzeit: letzter Sonntag im März bis letzter Sonntag im Oktober, 1 Uhr UTC)."""
    from datetime import datetime

    d = datetime.fromisoformat(dt[:19])

    def last_sunday(year, month):
        x = date(year, month, 31)
        return x - timedelta(days=(x.weekday() + 1) % 7)
    start = datetime.combine(last_sunday(d.year, 3), datetime.min.time()).replace(hour=2)
    end = datetime.combine(last_sunday(d.year, 10), datetime.min.time()).replace(hour=3)
    return "+02:00" if start <= d < end else "+01:00"


def _claude_md(letter: dict) -> bytes:
    from . import publish

    repo, branch = publish.repo_branch()
    return CLAUDE_MD.format(title=letter.get("title", ""), number=letter.get("number", ""),
                            repo=repo, branch=branch).encode("utf-8")


def send_for_scheduling(letter: dict) -> str:
    """Nach "Approve": alle noch nicht geplanten Teile rendern, JPGs + job.json + CLAUDE.md in EINEM Commit
    nach carinado93/app (carousel-media). Gibt den Satz zurück, den Carina Claude schickt."""
    from . import publish

    try:  # erst nachsehen, was Claude schon geplant hat – nie etwas doppelt planen
        sync(letter)
    except UserError:
        pass
    todo = [(lg, i) for lg in letter["langs"] for i in range(3)
            if letter["parts"][lg][i]["slides"] and not (letter["parts"][lg][i].get("scheduled") or {}).get("ok")]
    if not todo:
        raise UserError("Everything is already scheduled ✓")
    for lg, i in todo:
        part = letter["parts"][lg][i]
        n = hashtag_count(part.get("caption", ""))
        if n != 5:
            raise UserError(f"{lg.upper()} part {i + 1}: the caption has {n} hashtags – it needs exactly 5.")
        if not re.sub(r"(?<!\w)#\w+", "", part.get("caption", "")).strip():
            raise UserError(f"{lg.upper()} part {i + 1}: please write 1–2 sentences before the hashtags.")
        if FORBIDDEN.search(part.get("caption", "")):
            raise UserError('The words "stress & burnout coach" must never appear.')
        if not part.get("files"):
            render_part(letter, lg, i)
    repo, branch = publish.repo_branch()
    base = folder(letter)
    uploads, plan = [], []
    for lg, i in todo:
        files = letter["parts"][lg][i]["files"]
        out = _dir(letter["id"]) / "out" / lg / f"teil{i + 1}"
        paths = [f"{base}/{lg}{i + 1}_{k:02d}.jpg" for k in range(1, len(files) + 1)]
        uploads += [((out / f"{n}.jpg").read_bytes(), p) for n, p in zip(files, paths)]
        plan.append((lg, i, paths))
    # erst die Bilder, damit job.json die festen Commit-Links enthält
    commit, _ = publish.upload(uploads, f"Letter carousel media: {letter.get('title', '')}")
    raw = f"https://raw.githubusercontent.com/{repo}/{commit}/"
    posts = []
    for lg, i, paths in plan:
        part = letter["parts"][lg][i]
        when = part["time"][:19]
        posts.append({
            "lang": lg, "part": i + 1, "account": ACCOUNTS[lg]["handle"],
            "blogId": str(ACCOUNTS[lg]["blog_id"]), "date": when + berlin_offset(when),
            "info": {
                "autoPublish": True, "draft": False, "descendants": [], "firstCommentText": "",
                "hasNotReadNotes": False, "media": [raw + p for p in paths], "mediaAltText": [],
                "providers": [{"network": "instagram"}],
                "publicationDate": {"dateTime": when, "timezone": "Europe/Berlin"},
                "shortener": False, "smartLinkData": {"ids": []}, "text": part["caption"].strip(),
                "instagramData": {"type": "POST", "collaborators": [], "carouselTags": {}, "showReelOnFeed": True,
                                  "isAiGenerated": False},
            }})
    job = {"letter": letter.get("title", ""), "number": letter.get("number", ""), "created": time.time(), "posts": posts}
    publish.upload([(json.dumps(job, ensure_ascii=False, indent=1).encode(), f"{base}/job.json"),
                    (_claude_md(letter), f"{base}/CLAUDE.md")],
                   f"Letter carousel job: {letter.get('title', '')}")
    for lg, i, _ in plan:
        letter["parts"][lg][i]["scheduled"] = {"ok": False, "waiting": True, "at": time.time()}
    letter["sent"] = {"folder": base, "at": time.time()}
    return (f"Please schedule my letter carousels: read {base}/CLAUDE.md in {repo} (branch {branch}) "
            f"and do part A (job.json).")


def request_pictures(letter: dict, only_missing: bool = True) -> str:
    """Bild-Wünsche (Motiv → fertiger Prompt) als pictures.json hochladen. Gibt den Satz für Claude zurück."""
    from . import publish

    items = []
    for lg in letter["langs"]:
        for i, part in enumerate(letter["parts"][lg]):
            painted = part.get("style") == "painted"
            for k, sl in enumerate(part["slides"]):
                if only_missing and sl.get("image"):
                    continue
                if not painted and not sl.get("wants_art"):
                    continue
                items.append({"lang": lg, "part": i + 1, "slide": k + 1, "style": part.get("style"),
                              "motif": sl.get("motif", ""), "prompt": image_prompt(part, sl),
                              "file": f"{lg}{i + 1}_{k + 1:02d}.png"})
    if not items:
        raise UserError("All slides that need a picture already have one.")
    repo, branch = publish.repo_branch()
    base = folder(letter)
    publish.upload([(json.dumps({"letter": letter.get("title", ""), "items": items}, ensure_ascii=False,
                                indent=1).encode(), f"{base}/pictures.json"),
                    (_claude_md(letter), f"{base}/CLAUDE.md")],
                   f"Letter carousel picture request: {letter.get('title', '')}")
    letter["pictures_requested"] = {"at": time.time(), "count": len(items)}
    return (f"Please make the pictures for my letter carousel with Canva AI: read {base}/CLAUDE.md in {repo} "
            f"(branch {branch}) and do part B (pictures.json, {len(items)} pictures).")


def sync(letter: dict) -> dict:
    """Von GitHub holen, was Claude erledigt hat: Bilder aus art/ an die Folien hängen, Planungs-Ergebnis übernehmen."""
    from . import publish

    base = folder(letter)
    got = 0
    for f in publish.list_dir(f"{base}/art"):
        m = re.fullmatch(r"(en|de)([123])_(\d{2})\.(png|jpe?g|webp)", f.get("name", ""), re.I)
        if not m or m.group(1) not in letter["parts"]:
            continue
        lg, i, k = m.group(1), int(m.group(2)) - 1, int(m.group(3)) - 1
        slides = letter["parts"][lg][i]["slides"]
        if not 0 <= k < len(slides):
            continue
        name = f"canva_{lg}{i + 1}_{k + 1:02d}_{(f.get('sha') or '')[:8]}.png"
        if slides[k].get("image") == name:
            continue
        data = publish.read_file(f"{base}/art/{f['name']}")
        if not data:
            continue
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img.save(_dir(letter["id"]) / "bilder" / name, "PNG")
        slides[k]["image"] = name
        letter["parts"][lg][i]["files"] = []
        got += 1
    done = 0
    raw = publish.read_file(f"{base}/scheduled.json")
    if raw:
        try:
            for r in json.loads(raw.decode("utf-8")):
                lg, i = r.get("lang"), int(r.get("part", 0)) - 1
                if lg in letter["parts"] and 0 <= i < 3:
                    letter["parts"][lg][i]["scheduled"] = {
                        "ok": bool(r.get("ok")), "planner": r.get("plannerUrl") or r.get("planner"),
                        "error": r.get("error"), "at": time.time()}
                    done += bool(r.get("ok"))
        except (ValueError, TypeError, AttributeError):
            pass
    return {"pictures": got, "scheduled": done}
