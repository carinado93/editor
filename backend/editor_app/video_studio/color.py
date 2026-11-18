"""Farbe: alle Farb-Einstellungen einer Aufnahme werden zu EINER 3D-LUT (.cube, 33³) gebacken.

Dieselbe LUT benutzt die Vorschau im Browser (WebGL, 3D-Textur) und der Export (ffmpeg lut3d bzw. haldclut),
darum sieht die Vorschau genau so aus wie das fertige Video.

Reihenfolge (wie in CapCut/Lightroom): Belichtung → Weißabgleich (Temperatur/Tönung) → Kontrast →
Lichter/Tiefen/Weiß/Schwarz → Helligkeit → Sättigung/Dynamik (Hauttöne geschützt) → Verblassen → Look-LUT.
Alles weich (keine abgeschnittenen Lichter): Lichter werden sanft abgerollt statt geclippt.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

N = 33

# Eigene Looks (Parameter, keine fremden Dateien). "natural_plus" = dezent, wie Explore-the-World-Videos.
PRESETS: dict[str, dict] = {
    "none": {},
    # Standard (Carinas Wunsch 18.11.: "intensivere Farben"): satt, aber Lichter weich und Haut geschützt
    "vivid_travel": {"contrast": 16, "highlights": -22, "shadows": 10, "vibrance": 34, "sat": 12, "temp": 4,
                     "sat_by": {"orange": 12, "yellow": 8, "cyan": 10, "blue": 8, "green": 6}, "darks": -4},
    "natural_plus": {"contrast": 10, "highlights": -18, "shadows": 8, "sat": 6, "vibrance": 14, "temp": 3},
    "tropical_pop": {"contrast": 12, "highlights": -20, "shadows": 6, "vibrance": 26, "sat": 6, "temp": 4,
                     "hue_shift": {"cyan": -4}, "sat_by": {"cyan": 18, "blue": 10, "green": 8}},
    "golden_hour": {"temp": 14, "tint": 3, "contrast": 8, "highlights": -15, "vibrance": 12, "fade": 4},
    "teal_orange": {"contrast": 14, "highlights": -16, "split": {"shadows": [0.42, 0.16], "highlights": [0.08, 0.14]},
                    "vibrance": 10},
    "epic_mountains": {"contrast": 18, "highlights": -22, "shadows": 4, "temp": -6, "vibrance": 10, "darks": -6},
    "deep_blue_ocean": {"temp": -8, "contrast": 12, "sat_by": {"blue": 20, "cyan": 14}, "highlights": -14},
    "emerald_jungle": {"sat_by": {"green": 22, "yellow": 8}, "hue_shift": {"yellow": 6}, "contrast": 10, "shadows": 6},
    "moody_dusk": {"exposure": -0.15, "contrast": 16, "sat": -12, "temp": -4, "fade": 8, "darks": -8},
    "bw_drama": {"sat": -100, "contrast": 28, "highlights": -10, "darks": -10},
    "vintage_film": {"fade": 14, "sat": -14, "temp": 6, "contrast": -6, "split": {"shadows": [0.5, 0.08]}},
}

# Farbtöne in Grad für "pro Farbe"-Regler
HUES = {"red": 0, "orange": 30, "yellow": 55, "green": 120, "cyan": 185, "blue": 225, "purple": 275, "magenta": 320}


def _luma(c: np.ndarray) -> np.ndarray:
    return c[..., 0] * 0.2126 + c[..., 1] * 0.7152 + c[..., 2] * 0.0722


def _rgb_to_hsv(c: np.ndarray):
    mx, mn = c.max(-1), c.min(-1)
    d = mx - mn
    h = np.zeros_like(mx)
    m = d > 1e-6
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    i = m & (mx == r)
    h[i] = ((g - b)[i] / d[i]) % 6
    i = m & (mx == g)
    h[i] = (b - r)[i] / d[i] + 2
    i = m & (mx == b)
    h[i] = (r - g)[i] / d[i] + 4
    s = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0)
    return h * 60.0, s, mx


def _hue_weight(h: np.ndarray, center: float, width: float = 40.0) -> np.ndarray:
    d = np.abs((h - center + 180) % 360 - 180)
    return np.clip(1 - d / width, 0, 1) ** 1.5


def skin_mask(c: np.ndarray) -> np.ndarray:
    """Hauttöne (orange-rötlich, mittlere Sättigung) – dort Sättigung/Farbton kaum verändern."""
    h, s, v = _rgb_to_hsv(c)
    return _hue_weight(h, 22, 28) * np.clip((s - 0.12) / 0.15, 0, 1) * np.clip((0.65 - s) / 0.2, 0, 1) \
        * np.clip((v - 0.2) / 0.2, 0, 1)


def _soft_clip(x: np.ndarray) -> np.ndarray:
    """Werte über 0,9 weich gegen 1 abrollen (keine harten, ausgefressenen Lichter)."""
    k = 0.9
    over = x > k
    y = x.copy()
    y[over] = k + (1 - k) * np.tanh((x[over] - k) / (1 - k))
    return np.clip(y, 0, 1)


def grade(c: np.ndarray, p: dict) -> np.ndarray:
    """c: (...,3) RGB 0..1 (Rec.709, Display) → gegradet. p: Regler -100..100 (exposure in Blenden)."""
    c = np.clip(c.astype(np.float64), 0, 1)
    g = lambda k: float(p.get(k, 0) or 0)  # noqa: E731
    t, ti = g("temp") / 100, g("tint") / 100
    if g("exposure") or t or ti:
        # Belichtung (Blenden) und Weißabgleich im linearen Licht
        lin = c ** 2.2 * (2.0 ** g("exposure"))
        lin = lin * np.array([1 + 0.18 * t + 0.04 * ti, 1 - 0.08 * ti, 1 - 0.18 * t + 0.04 * ti])
        c = _soft_clip(lin) ** (1 / 2.2)
    # Kontrast (S-Kurve um 0,5, Luma-erhaltend)
    k = g("contrast") / 100
    if k:
        L = _luma(c)[..., None]
        L2 = np.clip(0.5 + (L - 0.5) * (1 + k) - k * 0.0, 0, 1)
        if k > 0:  # weiche S-Kurve statt linear
            L2 = L + (np.clip(L2, 0, 1) - L) * (1 - np.abs(2 * L - 1) ** 3 * 0.6)
        c = np.clip(c + (L2 - L), 0, 1)
    # Lichter / Tiefen / Weiß ("lights") / Schwarz ("darks") – luma-gewichtet
    L = _luma(c)[..., None]
    hi = np.clip((L - 0.45) / 0.55, 0, 1) ** 1.5
    sh = np.clip((0.55 - L) / 0.55, 0, 1) ** 1.5 * np.clip(L / 0.1, 0, 1)   # reines Schwarz bleibt schwarz
    wt = np.clip((L - 0.75) / 0.25, 0, 1)
    dk = np.clip((0.25 - L) / 0.25, 0, 1)
    delta = (g("highlights") * 0.25 * hi + g("shadows") * 0.25 * sh + g("lights") * 0.15 * wt
             + g("darks") * 0.15 * dk + g("brightness") * 0.2) / 100
    c = np.clip(c + delta, 0, 1)
    # Sättigung, Dynamik (schont schon satte Farben), pro Farbe, Hautschutz
    L = _luma(c)[..., None]
    h, s, _ = _rgb_to_hsv(c)
    amt = np.full(h.shape, g("sat") / 100)
    amt = amt + g("vibrance") / 100 * (1 - s) ** 2
    for name, val in (p.get("sat_by") or {}).items():
        amt = amt + float(val) / 100 * _hue_weight(h, HUES.get(name, 0))
    if p.get("protect_skin", True):
        amt = amt * (1 - 0.8 * skin_mask(c))
    c = np.clip(L + (c - L) * (1 + amt[..., None]), 0, 1)
    # Farbton-Verschiebung pro Farbe (kleine Werte, Grad)
    shifts = p.get("hue_shift") or {}
    if shifts:
        h, s, v = _rgb_to_hsv(c)
        dh = np.zeros_like(h)
        for name, deg in shifts.items():
            dh += float(deg) * _hue_weight(h, HUES.get(name, 0))
        c = _hsv_to_rgb((h + dh) % 360, s, v)
    # Split-Toning: (Farbton 0..1, Stärke) für Tiefen/Lichter
    split = p.get("split") or {}
    if split:
        L = _luma(c)[..., None]
        for zone, (hue, strength) in split.items():
            tint = _hsv_to_rgb(np.array(hue * 360.0), np.array(1.0), np.array(1.0)) - 0.5
            w = (np.clip((0.5 - L) * 2, 0, 1) if zone == "shadows" else np.clip((L - 0.5) * 2, 0, 1))
            c = np.clip(c + tint * w * strength * 0.25, 0, 1)
    # Verblassen (angehobenes Schwarz)
    f = g("fade") / 100
    if f:
        c = c * (1 - 0.25 * f) + 0.25 * f * 0.35
    return np.clip(c, 0, 1)


def _hsv_to_rgb(h, s, v):
    h = np.asarray(h, dtype=np.float64) / 60.0
    s, v = np.asarray(s, dtype=np.float64), np.asarray(v, dtype=np.float64)
    i = np.floor(h).astype(int) % 6
    f = h - np.floor(h)
    p_, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r = np.choose(i, [v, q, p_, p_, t, v])
    g = np.choose(i, [t, v, v, q, p_, p_])
    b = np.choose(i, [p_, p_, t, v, v, q])
    return np.stack([r, g, b], -1)


def params_for(look: str = "natural_plus", strength: float = 1.0, overrides: dict | None = None,
               protect_skin: bool = True) -> dict:
    """Look + Stärke (0..1) + eigene Regler → ein Parametersatz."""
    base = PRESETS.get(look, {})
    p: dict = {}
    for k, v in base.items():
        if isinstance(v, (int, float)):
            p[k] = v * strength
        elif isinstance(v, dict) and k == "split":
            p[k] = {z: [hv[0], hv[1] * strength] for z, hv in v.items()}
        elif isinstance(v, dict):
            p[k] = {n: x * strength for n, x in v.items()}
    for k, v in (overrides or {}).items():
        if isinstance(v, (int, float)) and isinstance(p.get(k), (int, float)):
            p[k] = p[k] + v
        else:
            p[k] = v
    p["protect_skin"] = protect_skin
    return p


def bake(p: dict, n: int = N) -> np.ndarray:
    """LUT-Würfel (n,n,n,3), Index [b][g][r] wie im .cube-Format (Rot läuft am schnellsten)."""
    x = np.linspace(0, 1, n)
    b, g, r = np.meshgrid(x, x, x, indexing="ij")
    return grade(np.stack([r, g, b], -1), p)


def write_cube(lut: np.ndarray, path: Path, title: str = "Carina Video Studio") -> Path:
    n = lut.shape[0]
    lines = [f'TITLE "{title}"', f"LUT_3D_SIZE {n}", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"]
    flat = lut.reshape(-1, 3)
    lines += [f"{a:.6f} {b:.6f} {c:.6f}" for a, b, c in flat]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def read_cube(path: Path) -> np.ndarray:
    n, vals = 0, []
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        if ln.upper().startswith("LUT_3D_SIZE"):
            n = int(ln.split()[1])
        elif ln[0].isdigit() or ln[0] in "-.":
            parts = ln.split()
            if len(parts) == 3:
                vals.append([float(v) for v in parts])
    if not n or len(vals) != n ** 3:
        raise ValueError("This is not a 3D .cube LUT.")
    return np.array(vals).reshape(n, n, n, 3)


def apply_lut(img: np.ndarray, lut: np.ndarray) -> np.ndarray:
    """Trilineare Interpolation (wie GPU/ffmpeg) – für Tests und Vorschaubilder. img uint8 RGB."""
    n = lut.shape[0]
    x = img.astype(np.float64) / 255 * (n - 1)
    i0 = np.clip(np.floor(x).astype(int), 0, n - 2)
    f = x - i0
    r0, g0, b0 = i0[..., 0], i0[..., 1], i0[..., 2]
    fr, fg, fb = f[..., 0:1], f[..., 1:2], f[..., 2:3]
    out = 0
    for db in (0, 1):
        for dg in (0, 1):
            for dr in (0, 1):
                w = (fr if dr else 1 - fr) * (fg if dg else 1 - fg) * (fb if db else 1 - fb)
                out = out + w * lut[b0 + db, g0 + dg, r0 + dr]
    return np.clip(np.round(out * 255), 0, 255).astype(np.uint8)


def hald_image(lut: np.ndarray, level: int = 8):
    """Hald-CLUT-Bild (level 8 → 512×512) für ffmpegs haldclut, falls lut3d fehlt."""
    from PIL import Image
    size = level * level
    x = np.linspace(0, 1, size)
    b, g, r = np.meshgrid(x, x, x, indexing="ij")
    rgb = np.stack([r, g, b], -1).reshape(-1, 3)
    out = apply_lut((rgb * 255).round().astype(np.uint8)[None], lut)[0]
    side = level ** 3
    return Image.fromarray(out.reshape(side, side, 3))


def lut_file(p: dict, cache_dir: Path) -> Path:
    """.cube für einen Parametersatz (zwischengespeichert nach Inhalt)."""
    key = hashlib.sha1(json.dumps(p, sort_keys=True).encode()).hexdigest()[:12]
    cache_dir.mkdir(parents=True, exist_ok=True)
    f = cache_dir / f"grade_{key}.cube"
    if not f.exists():
        write_cube(bake(p), f)
    return f


def ffmpeg_filter(cube: Path, work: Path) -> tuple[str, list[str]]:
    """ffmpeg-Filter für die LUT. Gibt (Filtertext, zusätzliche Eingaben) zurück.
    lut3d wenn vorhanden (Carinas ffmpeg-Build), sonst haldclut mit einem Hald-Bild (zweiter Eingang)."""
    from .. import media
    if media.has_filter("lut3d"):
        esc = str(cube).replace("\\", "/").replace(":", "\\\\:").replace("'", "\\'")
        return f"lut3d=file='{esc}':interp=tetrahedral", []
    hald = work / (cube.stem + "_hald.png")
    if not hald.exists():
        hald_image(read_cube(cube)).save(hald)
    return "HALD", [str(hald)]
