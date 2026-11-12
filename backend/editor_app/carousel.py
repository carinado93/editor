"""Instagram-Karussell-Generator im Stil von Carinas Karussells (docs/KARUSSELL_STIL.md, Skill "carina-carousel").

Claude schreibt die Folien (Cover, 3–8 Punkte, Schluss-Folie) + Caption + genau 5 Hashtags,
die App zeichnet sie als 1080×1350-PNGs: Creme mit feiner Papier-Struktur, dünner Goldrahmen,
Cormorant Garamond, Lila-Kursiv für Zahlen und *Akzente*, kleines Salbei-Logo, "SWIPE →".
Gespeichert in daten/karussell/<id>/ (nur auf Carinas PC).
"""
from __future__ import annotations

import io
import json
import math
import random
import re
import time
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import meta
from .config import ROOT
from .errors import UserError

W, H = 1080, 1350
FONTS = ROOT / "assets" / "fonts"
DIR = ROOT / "daten" / "karussell"

CREME = (244, 236, 218)
GOLD = (201, 165, 104)
BRAUN = (63, 58, 44)
BRAUN_TEXT = (74, 68, 52)
LILA = (152, 115, 179)
SALBEI = (139, 154, 107)
MARGIN = 120

# Farbvarianten (wie ihre Foto-Story-Karussells): Hintergrund, Text, Akzent, Rahmen
THEMES = {
    "creme": {"bg": CREME, "text": BRAUN, "body": BRAUN_TEXT, "accent": LILA, "frame": GOLD, "logo": SALBEI},
    "flieder": {"bg": (225, 216, 236), "text": BRAUN, "body": BRAUN_TEXT, "accent": (106, 76, 156), "frame": (170, 150, 205),
                "logo": (106, 76, 156)},
    "lila": {"bg": (106, 76, 156), "text": (244, 238, 228), "body": (236, 230, 240), "accent": (233, 196, 120),
             "frame": (233, 196, 120), "logo": (233, 217, 166)},
    "oliv": {"bg": (107, 111, 58), "text": (244, 238, 228), "body": (236, 232, 218), "accent": (233, 217, 166),
             "frame": (233, 217, 166), "logo": (233, 217, 166)},
}


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    files = {"head": "CormorantGaramond-Bold.ttf", "semi": "CormorantGaramond-SemiBold.ttf",
             "italic": "CormorantGaramond-SemiBoldItalic.ttf", "bold_i": "CormorantGaramond-BoldItalic.ttf",
             "jost": "Jost.ttf"}
    return ImageFont.truetype(str(FONTS / files[name]), max(10, int(size)))


# ---------------------------------------------------------------- Texte von Claude

SCHEMA = {
    "type": "object",
    "properties": {
        "cover_title": {"type": "string"}, "teaser": {"type": "string"},
        "slides": {"type": "array", "items": {"type": "object", "properties": {
            "title": {"type": "string"}, "lines": {"type": "array", "items": {"type": "string"}}},
            "required": ["title", "lines"], "additionalProperties": False}},
        "caption": {"type": "string"}, "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["cover_title", "teaser", "slides", "caption", "hashtags"],
    "additionalProperties": False,
}


def build_prompt(topic: str, points: int, language: str, source_text: str = "") -> str:
    lang = "Deutsch" if language == "de" else "Englisch"
    account = "@carinadorca.coach" if language == "de" else "@carina.dorca"
    src = f"\nGrundlage ist dieses Video von Carina (nimm ihre Gedanken und Beispiele, neue knackige Worte):\n{source_text[:9000]}\n" \
        if source_text.strip() else ""
    return f"""Du schreibst ein Instagram-Karussell für Carina Dorca (Stress- & Burnout-Coachin, {account}).
Sie lebt seit Jahren mit Angst und hatte dreimal Burnout. Ihre Karussells wirken ruhig, sicher, professionell –
der Text ist der Star. Sprache: {lang}.

Thema / Winkel: {topic.strip()}
{src}
Aufbau:
- cover_title: großer Hook für die erste Folie, max. 9 Wörter, konkret und teilbar (Formate, die sie mag:
  "Things I wish I'd known about …", "Things I'd tell you if it wouldn't make you mad (burnout edition)").
- teaser: kurzer Satz in Klammern-Stil OHNE die Klammern, z. B. "Swipe — number 3 changes everything."
- slides: genau {points} Punkte. title = kurze Überschrift (max. 6 Wörter, OHNE Nummer – die setzt die App).
  lines = 3–5 kurze Sätze, EIN Satz pro Zeile, max. ca. 9 Wörter pro Zeile, keine Aufzählungszeichen.
  Erst das Gefühl benennen, dann erklären ("That's why …"), mit alltagsnahem Beispiel.
  Die LETZTE Zeile jeder Folie ist eine Wendung/ein Kontrast, z. B. "Feeling scared doesn't mean you're in danger."
  Markiere in jeder Folie genau EIN Schlüsselwort oder eine kurze Phrase mit *Sternchen* (wird lila-kursiv).
- caption: in Carinas Stimme. Zeile 1 = Hook, der das Gefühl benennt (+ 🤍). Dann 2–3 kurze Absätze
  (ihr persönlicher Winkel "For years I …", was wirklich half, was dieses Karussell gibt), eine Frage zum
  Kommentieren, "📌 Save this for …", "💌 Share it with someone who …", "Follow {account} for more about anxiety,
  stress & burnout.", letzte Zeile "Educational and my own experience, not a diagnosis or therapy."
  Nur wenige sanfte Emojis (🤍 📌 💌). KEINE Hashtags in der Caption.
- hashtags: GENAU 5 (Mischung aus breit, Nische, ihre Positionierung), bevorzugt aus:
  {", ".join(meta.hashtag_bank(language)[:25])}

{meta.GUARDRAILS}

{meta.lang_rule(language)}
Antworte NUR mit JSON nach dem Schema."""


def clean(raw: dict, language: str) -> dict:
    slides = []
    for s in raw.get("slides", []) if isinstance(raw, dict) else []:
        if not isinstance(s, dict):
            continue
        title = re.sub(r"^\s*\d+[.)]\s*", "", str(s.get("title", "")).strip())
        lines = [str(x).strip() for x in s.get("lines", []) if str(x).strip()][:6]
        if title or lines:
            slides.append({"title": title, "lines": lines})
    if not slides:
        raise UserError("Claude did not return any slides. Please try again.")
    return {
        "cover_title": str(raw.get("cover_title", "")).strip(),
        "teaser": str(raw.get("teaser", "")).strip().strip("()"),
        "slides": slides,
        "caption": str(raw.get("caption", "")).strip(),
        "hashtags": meta.fix_hashtags(list(raw.get("hashtags", [])), language, []),
    }


def draft(engine: str, topic: str, points: int, language: str, source_text: str = "") -> dict:
    if not topic.strip() and not source_text.strip():
        raise UserError("Please write a topic, e.g. \"Things I wish I'd known about burnout\".")
    points = max(3, min(8, int(points or 5)))
    prompt = build_prompt(topic or "the main message of the video", points, language, source_text)
    if engine == "claude":
        from . import claude
        raw = claude.ask_json(prompt, SCHEMA, effort="medium")
    else:
        from . import llm
        raw = llm.ask_json(prompt, "Du antwortest ausschließlich mit gültigem JSON.", timeout=900)
    data = clean(raw, language)
    cid = time.strftime("%Y%m%d-%H%M%S")
    car = {"id": cid, "topic": topic.strip(), "language": language, "theme": "creme", "created": time.time(),
           **data, "files": []}
    return save(car)


# ---------------------------------------------------------------- Speicher

def _dir(cid: str) -> Path:
    if not re.fullmatch(r"[\w-]+", cid):
        raise UserError("Unknown carousel.")
    return DIR / cid


def save(car: dict) -> dict:
    d = _dir(car["id"])
    d.mkdir(parents=True, exist_ok=True)
    (d / "karussell.json").write_text(json.dumps(car, ensure_ascii=False, indent=1), encoding="utf-8")
    return car


def load(cid: str) -> dict:
    f = _dir(cid) / "karussell.json"
    if not f.exists():
        raise UserError("This carousel does not exist any more.")
    return json.loads(f.read_text(encoding="utf-8"))


def list_all() -> list[dict]:
    out = []
    for f in sorted(DIR.glob("*/karussell.json"), reverse=True):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
            out.append({"id": c["id"], "topic": c.get("topic", ""), "cover_title": c.get("cover_title", ""),
                        "created": c.get("created", 0), "files": c.get("files", [])})
        except (OSError, ValueError, KeyError):
            continue
    return out


def update(cid: str, fields: dict) -> dict:
    car = load(cid)
    for k in ("cover_title", "teaser", "caption", "theme", "topic"):
        if k in fields and fields[k] is not None:
            car[k] = str(fields[k])
    if fields.get("slides") is not None:
        car["slides"] = [{"title": str(s.get("title", "")).strip(),
                          "lines": [str(x).strip() for x in s.get("lines", []) if str(x).strip()]}
                         for s in fields["slides"]]
    if fields.get("hashtags") is not None:
        car["hashtags"] = meta.fix_hashtags(list(fields["hashtags"]), car.get("language", "en"), [])
    if car.get("theme") not in THEMES:
        car["theme"] = "creme"
    return save(car)


def delete(cid: str) -> None:
    import shutil
    shutil.rmtree(_dir(cid), ignore_errors=True)


# ---------------------------------------------------------------- Zeichnen

def _background(th: dict) -> Image.Image:
    """Fläche mit sehr feiner Papier-Struktur + dünner Rahmen."""
    rng = np.random.default_rng(7)
    base = np.zeros((H, W, 3), np.float32) + np.array(th["bg"], np.float32)
    noise = rng.normal(0, 3.2, (H // 2, W // 2)).astype(np.float32)
    noise = np.kron(noise, np.ones((2, 2), np.float32))
    base += noise[..., None]
    im = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rectangle((44, 44, W - 45, H - 45), outline=(*th["frame"], 140), width=2)
    im = im.convert("RGBA")
    im.alpha_composite(layer)
    return im


def _logo(img: Image.Image, x: float, y: float, size: float, color) -> None:
    """Carinas Logo als feine Linienzeichnung: kleiner Kreis über zwei Blättern."""
    S = 3
    box = int(size * 1.6)
    layer = Image.new("RGBA", (box * S, box * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    c = (*color, 255)
    w = max(2, int(size * 0.06)) * S
    cx = box * S / 2
    r = size * 0.22 * S
    d.ellipse((cx - r, size * 0.12 * S, cx + r, size * 0.12 * S + 2 * r), outline=c, width=w)
    base_y = size * 1.45 * S
    for side in (-1, 1):  # zwei Blätter, die sich vom Stiel nach oben öffnen
        pts_a, pts_b = [], []
        ang = math.radians(-90 + side * 38)
        ln = size * 0.85 * S
        for i in range(21):
            t = i / 20
            px, py = t * ln, math.sin(math.pi * t) * ln * 0.26
            ca, sa = math.cos(ang), math.sin(ang)
            pts_a.append((cx + px * ca - py * sa, base_y + px * sa + py * ca))
            pts_b.append((cx + px * ca + py * sa, base_y + px * sa - py * ca))
        d.line(pts_a + pts_b[::-1] + [pts_a[0]], fill=c, width=w, joint="curve")
    layer = layer.resize((box, box), Image.LANCZOS)
    img.alpha_composite(layer, (int(x), int(y)))


def _rich(d: ImageDraw.ImageDraw, x: float, y: float, text: str, f, f_acc, color, acc) -> float:
    """Eine Zeile mit *Akzent* (lila-kursiv). Gibt die Breite zurück."""
    cx = x
    for k, part in enumerate(text.split("*")):
        if not part:
            continue
        ff = f_acc if k % 2 else f
        d.text((cx, y), part, font=ff, fill=acc if k % 2 else color, anchor="ls")
        cx += ff.getlength(part)
    return cx - x


def _width(text: str, f, f_acc) -> float:
    return sum((f_acc if k % 2 else f).getlength(p) for k, p in enumerate(text.split("*")))


def _wrap(text: str, f, f_acc, max_w: float) -> list[str]:
    """Umbrechen, ohne *Akzente* zu zerreißen; kein einzelnes Wort allein in der letzten Zeile (Schusterjunge)."""
    words, lines, cur, open_acc = text.split(), [], "", False
    for wd in words:
        trial = f"{cur} {wd}".strip()
        probe = trial + ("*" if (trial.count("*") % 2) else "")
        if cur and _width(probe, f, f_acc) > max_w:
            if cur.count("*") % 2:  # Akzent über den Umbruch: in beiden Zeilen schließen/öffnen
                lines.append(cur + "*")
                cur = "*" + wd
            else:
                lines.append(cur)
                cur = wd
        else:
            cur = trial
    if cur:
        lines.append(cur)
    if len(lines) > 1 and len(lines[-1].replace("*", "").split()) == 1 and len(lines[-2].split()) > 2:
        prev = lines[-2].split()
        lines[-2], lines[-1] = " ".join(prev[:-1]), prev[-1] + " " + lines[-1]
    _ = open_acc
    return lines


def _footer(img: Image.Image, th: dict, swipe: bool, website: bool, logo_small: bool) -> None:
    d = ImageDraw.Draw(img)
    fj = font("jost", 24)
    if logo_small:
        _logo(img, 78, H - 150, 46, th["logo"])
    if website:
        d.text((MARGIN if not logo_small else 160, H - 92), "www.carinadorca.com", font=fj, fill=th["body"], anchor="ls")
    if swipe:  # Pfeil selbst zeichnen (Jost hat kein "→")
        fs = font("jost", 25)
        ax1 = W - MARGIN + 30
        ax0 = ax1 - 34
        ay = H - 100
        d.line((ax0, ay, ax1, ay), fill=th["accent"], width=2)
        d.line((ax1 - 9, ay - 7, ax1, ay, ax1 - 9, ay + 7), fill=th["accent"], width=2, joint="curve")
        d.text((ax0 - 14, H - 92), "S W I P E", font=fs, fill=th["accent"], anchor="rs")


def render_cover(car: dict, th: dict) -> Image.Image:
    img = _background(th)
    _logo(img, 92, 88, 70, th["logo"])
    d = ImageDraw.Draw(img)
    title = car.get("cover_title") or "Your hook"
    size = 104
    while True:
        f, fa = font("head", size), font("bold_i", size)
        lines = _wrap(title, f, fa, W - 2 * MARGIN)
        if (len(lines) <= 6 and size * 0.98 * len(lines) < 640) or size <= 60:
            break
        size -= 6
    y = 420
    for ln in lines:
        _rich(d, MARGIN, y + size * 0.8, ln, f, fa, th["text"], th["accent"])
        y += size * 0.98
    if car.get("teaser"):
        ft = font("italic", 48)
        y += 40
        for ln in _wrap(f"({car['teaser']})", ft, ft, W - 2 * MARGIN):
            d.text((MARGIN, y + 40), ln, font=ft, fill=th["accent"], anchor="ls")
            y += 58
    _footer(img, th, swipe=True, website=True, logo_small=False)
    return img


def render_point(n: int, slide: dict, th: dict, last_point: bool = False) -> Image.Image:
    img = _background(th)
    d = ImageDraw.Draw(img)
    hs, bs = 76, 46
    for _ in range(12):  # Schrift verkleinern, bis alles ins Bild passt
        fh, fhi = font("head", hs), font("bold_i", hs)
        fb, fbi = font("semi", bs), font("italic", bs)
        num = f"{n}. "
        tl = _wrap(slide.get("title", ""), fh, fhi, W - 2 * MARGIN - fhi.getlength(num))
        body = [ln2 for ln in slide.get("lines", []) for ln2 in _wrap(ln, fb, fbi, W - 2 * MARGIN)]
        need = len(tl) * hs * 1.05 + 70 + len(body) * bs * 1.32 + 30 * len(slide.get("lines", []))
        if need < H - 400:
            break
        hs, bs = hs - 4, bs - 2
    y = 230
    for k, ln in enumerate(tl):
        x = MARGIN
        if k == 0:
            d.text((x, y + hs * 0.8), num, font=fhi, fill=th["accent"], anchor="ls")
        x += fhi.getlength(num)
        _rich(d, x, y + hs * 0.8, ln, fh, fhi, th["text"], th["accent"])
        y += hs * 1.05
    y += 60
    for ln in slide.get("lines", []):
        for ln2 in _wrap(ln, fb, fbi, W - 2 * MARGIN):
            _rich(d, MARGIN, y + bs * 0.8, ln2, fb, fbi, th["body"], th["accent"])
            y += bs * 1.32
        y += 22  # etwas Luft zwischen den Sätzen
    _footer(img, th, swipe=True, website=False, logo_small=True)
    return img


def render_end(car: dict, th: dict) -> Image.Image:
    img = _background(th)
    _logo(img, 92, 88, 70, th["logo"])
    d = ImageDraw.Draw(img)
    de = car.get("language") == "de"
    fh, fb, fi = font("head", 92), font("semi", 46), font("italic", 52)
    y = 360
    d.text((MARGIN, y), "Hi, ich bin Carina." if de else "Hi, I'm Carina.", font=fh, fill=th["text"], anchor="ls")
    y += 90
    topic = (car.get("topic", "") + " " + car.get("cover_title", "")).lower()
    if "anx" in topic or "angst" in topic:
        bio = ("Stress- & Burnout-Coachin, die weiß, wie es ist, jahrelang mit Angst zu leben." if de else
               "Stress & burnout coach, who knows what it means to live with anxiety for years.")
    else:
        bio = ("Stress- & Burnout-Coachin, die weiß, was Burnout bedeutet. Ich hatte es dreimal." if de else
               "Stress & burnout coach, who knows what it means to go through burnout. I had it three times.")
    for ln in _wrap(bio, fb, fb, W - 2 * MARGIN):
        d.text((MARGIN, y), ln, font=fb, fill=th["body"], anchor="ls")
        y += 60
    y += 70
    lines = ([("Wenn dir dieses Karussell geholfen hat …", fb, th["body"]),
              ("Tippe auf den Link in meiner Bio", fi, th["accent"]),
              ("oder folge mir für mehr über Angst & Burnout.", fb, th["body"])] if de else
             [("If this carousel helped you…", fb, th["body"]),
              ("Tap the link in my bio", fi, th["accent"]),
              ("or follow for more about anxiety & burnout.", fb, th["body"])])
    for text, f, col in lines:
        for ln in _wrap(text, f, f, W - 2 * MARGIN):
            d.text((MARGIN, y), ln, font=f, fill=col, anchor="ls")
            y += 64
        y += 6
    _footer(img, th, swipe=False, website=True, logo_small=False)
    return img


def render(cid: str) -> dict:
    car = load(cid)
    th = THEMES.get(car.get("theme", "creme"), THEMES["creme"])
    d = _dir(cid)
    for old in d.glob("slide_*.png"):
        old.unlink()
    stamp = int(time.time())
    imgs = [render_cover(car, th)]
    n = len(car["slides"])
    imgs += [render_point(k + 1, s, th, k == n - 1) for k, s in enumerate(car["slides"])]
    imgs.append(render_end(car, th))
    files = []
    for k, im in enumerate(imgs, 1):
        name = f"slide_{k:02d}_{stamp}.png"
        im.convert("RGB").save(d / name, "PNG", optimize=True)
        files.append(name)
    (d / "caption.txt").write_text(car.get("caption", "") + "\n\n" + " ".join(car.get("hashtags", [])),
                                   encoding="utf-8")
    car["files"] = files
    return save(car)


def file_path(cid: str, name: str) -> Path:
    f = _dir(cid) / name
    if "/" in name or "\\" in name or not f.is_file():
        raise UserError("File not found.")
    return f


def zip_bytes(cid: str) -> bytes:
    car = load(cid)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for k, name in enumerate(car.get("files", []), 1):
            z.write(_dir(cid) / name, f"{k:02d}.png")
        z.writestr("caption.txt", car.get("caption", "") + "\n\n" + " ".join(car.get("hashtags", [])))
    return buf.getvalue()


_ = random  # (für spätere Varianten)
