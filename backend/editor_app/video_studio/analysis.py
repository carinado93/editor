"""Clip-Analyse für den Drone Cutter: Szenen finden und jeden Moment bewerten.

Pro Clip werden ~4 Bilder/s in kleiner Auflösung gelesen (ffmpeg → numpy). Daraus:
  * Szenenwechsel (Farb-Histogramm-Sprung, wie PySceneDetect "content")
  * Schärfe (Laplace-Varianz), Helligkeit/Belichtung, Farbigkeit
  * Kamerabewegung per optischem Fluss: Richtung + Tempo, Wackeln = Abweichung vom geglätteten Verlauf
  * Helden-Momente: ruhig, scharf, farbig – dort passen Zeitlupe und der Hook am Anfang
Ergebnis: Liste von Kandidaten-Momenten (Start, Länge, Punkte, Eigenschaften), die der Planer verwendet.
"""
from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from .. import media

SAMPLE_FPS = 4.0
SAMPLE_W = 320


@dataclass
class Sample:
    t: float
    sharp: float      # 0..1
    bright: float     # 0..1 (mittlere Helligkeit)
    clip: float       # Anteil fast schwarzer/weißer Pixel
    color: float      # 0..1 Farbigkeit
    motion: float     # Pixel/s bei SAMPLE_W
    jitter: float     # Wackeln (Pixel/s)
    dx: float = 0.0
    dy: float = 0.0
    zoom: float = 0.0  # >0 = nach vorn (hinein), <0 = zurück


@dataclass
class Moment:
    clip: str
    start: float
    dur: float
    score: float
    hero: bool = False
    transit: bool = False      # schnelle, gleichmäßige Fahrt → darf beschleunigt werden
    direction: str = ""        # left/right/up/down/in/out (für Match-Cuts später)
    scene: int = 0
    info: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def read_samples(path: Path, info: dict, fps: float = SAMPLE_FPS, width: int = SAMPLE_W) -> tuple[np.ndarray, np.ndarray]:
    """Kleine Graubild-/Farbbild-Folge des Clips: (times, frames[N,h,w,3] uint8)."""
    w = width
    h = int(round(width * info["height"] / max(1, info["width"]) / 2)) * 2
    cmd = [media.ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(path),
           "-map", f"0:{info['video_index']}", "-vf", f"{media.sdr_filter(info)}fps={fps},scale={w}:{h}:flags=area",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    r = subprocess.run(cmd, capture_output=True, creationflags=getattr(media, "_NO_WINDOW", 0))
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError("Could not read the clip: " + r.stderr.decode("utf-8", "replace")[-300:])
    frames = np.frombuffer(r.stdout, np.uint8)
    n = frames.size // (w * h * 3)
    frames = frames[: n * w * h * 3].reshape(n, h, w, 3)
    times = (np.arange(n) + 0.5) / fps
    return times, frames


def _hist(f: np.ndarray) -> np.ndarray:
    import cv2
    hsv = cv2.cvtColor(f, cv2.COLOR_RGB2HSV)
    hst = cv2.calcHist([hsv], [0, 1, 2], None, [16, 8, 8], [0, 180, 0, 256, 0, 256]).ravel()
    return hst / max(1.0, hst.sum())


def scene_cuts(frames: np.ndarray, threshold: float = 0.45) -> list[int]:
    """Indizes, an denen eine neue Szene beginnt (Histogramm-Abstand, Bhattacharyya-ähnlich)."""
    cuts = []
    prev = None
    for k, f in enumerate(frames):
        hst = _hist(f)
        if prev is not None:
            d = 1.0 - float(np.sum(np.sqrt(hst * prev)))
            if d > threshold:
                cuts.append(k)
        prev = hst
    return cuts


def motion_cuts(samples: list["Sample"], responses: list[float]) -> list[int]:
    """Harte Schnitte im Clip, die das Farb-Histogramm nicht sieht: Bild passt nicht zum vorigen
    (Phasenkorrelation deutlich schwächer als bei den Nachbarn) UND die Bewegung springt weit über die Nachbarn."""
    out = []
    mot = np.array([s.motion for s in samples])
    for i in range(1, len(samples)):
        nb = np.median(np.r_[mot[max(0, i - 3):i], mot[i + 1:i + 4]]) if len(mot) > 2 else 0
        r = np.array(responses)
        nb_r = float(np.median(np.r_[r[max(0, i - 3):i], r[i + 1:i + 4]]))
        if responses[i] < min(0.62, 0.7 * nb_r) and mot[i] > 3 * nb + 30:
            out.append(i)
    return out


def measure(times: np.ndarray, frames: np.ndarray, responses_out: list | None = None) -> list[Sample]:
    import cv2
    out: list[Sample] = []
    grays = [cv2.cvtColor(f, cv2.COLOR_RGB2GRAY) for f in frames]
    flows = [np.zeros(4)]
    responses = [1.0]
    win = None
    for a, b in zip(grays[:-1], grays[1:]):
        h, w = a.shape
        if win is None:
            win = cv2.createHanningWindow((w, h), cv2.CV_32F)
        # Kamerabewegung: Verschiebung des ganzen Bildes (Phasenkorrelation) – funktioniert auch bei viel
        # glattem Himmel, wo der optische Fluss "0" misst
        (sx, sy), resp = cv2.phaseCorrelate(a.astype(np.float32), b.astype(np.float32), win)
        responses.append(float(resp))
        dx, dy = -float(sx), -float(sy)
        # Zoom: optischer Fluss nur dort, wo das Bild Struktur hat
        fl = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        gm = cv2.magnitude(cv2.Sobel(a, cv2.CV_32F, 1, 0), cv2.Sobel(a, cv2.CV_32F, 0, 1))
        tex = gm > np.percentile(gm, 60)
        yy, xx = np.mgrid[0:h, 0:w]
        rx, ry = xx - w / 2, yy - h / 2
        rn = np.sqrt(rx ** 2 + ry ** 2) + 1e-3
        radial = ((fl[..., 0] - np.median(fl[..., 0][tex])) * rx + (fl[..., 1] - np.median(fl[..., 1][tex])) * ry) / rn
        zoom = float(np.median(radial[tex])) if tex.any() else 0.0
        flows.append(np.array([dx, dy, zoom, float(np.hypot(dx, dy) + abs(zoom))]))
    flows[0] = flows[1] if len(flows) > 1 else flows[0]
    if responses_out is not None:
        responses_out[:] = responses
    F = np.array(flows)
    # Wackeln: Abweichung der Bewegung vom geglätteten Verlauf (ruhige Drohnenfahrt = gleichmäßig)
    k = 5
    pad = np.pad(F[:, :2], ((k // 2, k // 2), (0, 0)), mode="edge")
    smooth = np.stack([np.convolve(pad[:, j], np.ones(k) / k, mode="valid") for j in range(2)], 1)
    jit = np.hypot(*(F[:, :2] - smooth).T)
    for i, (t, f, g) in enumerate(zip(times, frames, grays)):
        lap = cv2.Laplacian(g, cv2.CV_32F).var()
        sharp = float(1 - np.exp(-lap / 180.0))
        bright = float(g.mean() / 255)
        clip = float(((g < 12) | (g > 248)).mean())
        r, gg, b = (f[..., c].astype(np.float32) for c in range(3))
        rg, yb = r - gg, 0.5 * (r + gg) - b
        colorful = float((np.hypot(rg.std(), yb.std()) + 0.3 * np.hypot(rg.mean(), yb.mean())) / 110.0)
        out.append(Sample(float(t), sharp, bright, clip, min(1.0, colorful), float(F[i, 3] * SAMPLE_FPS),
                          float(jit[i] * SAMPLE_FPS), float(F[i, 0] * SAMPLE_FPS), float(F[i, 1] * SAMPLE_FPS),
                          float(F[i, 2] * SAMPLE_FPS)))
    return out


def quality(s: Sample) -> float:
    """Ein Moment ist gut, wenn er scharf, ruhig, gut belichtet und farbig ist."""
    expo = 1.0 - min(1.0, abs(s.bright - 0.48) / 0.4)     # zu dunkel/zu hell abwerten
    shake = float(np.exp(-s.jitter / 6.0))                 # wackelig → stark abwerten
    q = 0.32 * s.sharp + 0.28 * shake + 0.22 * expo + 0.18 * s.color
    if s.bright < 0.12 or s.clip > 0.35:
        q *= 0.35
    return float(q)


def _direction(dx: float, dy: float, zoom: float) -> str:
    if abs(zoom) > max(abs(dx), abs(dy)) * 0.6 and abs(zoom) > 1.5:
        return "in" if zoom > 0 else "out"
    if max(abs(dx), abs(dy)) < 1.5:
        return ""
    if abs(dx) >= abs(dy):
        return "left" if dx > 0 else "right"   # Bildinhalt wandert nach rechts → Kamera schwenkt nach links
    return "up" if dy > 0 else "down"


def moments(clip_id: str, samples: list[Sample], cuts: list[int], min_len: float = 2.0, max_len: float = 6.0,
            step: float = 0.5) -> list[Moment]:
    """Kandidaten-Momente (2–6 s) innerhalb jeder Szene, nach Punkten sortiert, ohne Überlappung."""
    if not samples:
        return []
    med_sharp = float(np.median([s.sharp for s in samples])) or 1e-3
    # Unschärfe relativ zum Clip bewerten (jede Kamera/Szene hat ein anderes "scharf")
    q = np.array([quality(s) * min(1.0, (s.sharp / med_sharp) / 0.6) ** 1.5 for s in samples])
    t = np.array([s.t for s in samples])
    bounds = [0, *cuts, len(samples)]
    cands: list[Moment] = []
    for si, (a, b) in enumerate(zip(bounds[:-1], bounds[1:])):
        if b - a < 2:
            continue
        t0, t1 = t[a] - 0.5 / SAMPLE_FPS, t[b - 1] + 0.5 / SAMPLE_FPS
        # 0,25 s Abstand zu Szenengrenzen (keine halben Bilder vom Wechsel)
        t0, t1 = t0 + (0.25 if a else 0.05), t1 - (0.25 if b < len(samples) else 0.05)
        # Start und Landung der Drohne (Boden nah, Kamera kippt) weglassen. Ein Landeanflug dauert oft 10 s
        # und mehr: lange Clips (>60 s) ohne die ersten 5 s und letzten 12 s, mittlere ohne 2 s / 6 s
        clip_end = t[-1] + 0.5 / SAMPLE_FPS
        if clip_end > 60:
            t0, t1 = max(t0, 5.0), min(t1, clip_end - 12.0)
        elif clip_end > 25:
            t0, t1 = max(t0, 2.0), min(t1, clip_end - 6.0)
        L = min(max_len, t1 - t0)
        if L < min(min_len, 1.2):
            continue
        st = t0
        while st + min(min_len, L) <= t1 + 1e-6:
            dur = min(L, t1 - st)
            m = (t >= st) & (t <= st + dur)
            if m.sum() >= 2:
                qs = q[m]
                ss = [samples[i] for i in np.where(m)[0]]
                mean_q = float(qs.mean() - 0.5 * qs.std())   # gleichmäßig gut > kurz sehr gut
                mot = float(np.mean([s.motion for s in ss]))
                jit = float(np.mean([s.jitter for s in ss]))
                dx = float(np.mean([s.dx for s in ss]))
                dy = float(np.mean([s.dy for s in ss]))
                zm = float(np.mean([s.zoom for s in ss]))
                smooth = jit < 3.0 or jit < 0.12 * mot   # schnelle Fahrt: relatives Wackeln zählt
                hero = smooth and mean_q > 0.62 and float(np.mean([s.color for s in ss])) > 0.35 and mot < 25
                transit = smooth and mot > 18
                cands.append(Moment(clip_id, round(float(st), 3), round(float(dur), 3), round(mean_q, 4), hero, transit,
                                    _direction(dx, dy, zm), si,
                                    {"motion": round(mot, 2), "jitter": round(jit, 2),
                                     "bright": round(float(np.mean([s.bright for s in ss])), 3)}))
            st += step
    cands.sort(key=lambda m: m.score, reverse=True)
    chosen: list[Moment] = []
    for c in cands:   # keine Überlappung (gleiche Bilder nie zweimal)
        if all(c.start + c.dur <= o.start or o.start + o.dur <= c.start for o in chosen if o.clip == c.clip):
            chosen.append(c)
    return chosen


def analyse(clip_id: str, path: Path, info: dict | None = None) -> dict:
    """Ganze Analyse eines Clips → JSON-fähiges Ergebnis (wird pro Clip zwischengespeichert)."""
    info = info or media.probe(path)
    times, frames = read_samples(path, info)
    cuts = scene_cuts(frames)
    resp: list[float] = []
    samples = measure(times, frames, resp)
    cuts = sorted(set(cuts) | set(motion_cuts(samples, resp)))
    ms = moments(clip_id, samples, cuts)
    return {"clip": clip_id, "duration": info["duration"], "fps": info["fps"], "width": info["width"],
            "height": info["height"], "scenes": [round(float(times[c]), 2) for c in cuts],
            "samples": [asdict(s) for s in samples], "moments": [m.to_dict() for m in ms],
            # längere Momente (4–10 s) für YouTube-Aufnahmen
            "moments_long": [m.to_dict() for m in moments(clip_id, samples, cuts, 4.0, 10.0, 1.0)]}


def refresh_moments(res: dict) -> dict:
    """Momente aus gespeicherten Messwerten neu berechnen (ohne das Video erneut zu lesen),
    damit verbesserte Regeln auch für schon analysierte Clips gelten."""
    samples = [Sample(**x) for x in res.get("samples", [])]
    if not samples:
        return res
    ts = [s.t for s in samples]
    cuts = [min(range(len(ts)), key=lambda i: abs(ts[i] - c)) for c in res.get("scenes", [])]
    res["moments"] = [m.to_dict() for m in moments(res["clip"], samples, cuts)]
    res["moments_long"] = [m.to_dict() for m in moments(res["clip"], samples, cuts, 4.0, 10.0, 1.0)]
    return res


def best_xpos(img, target_aspect: float) -> float:
    """Automatischer Bildausschnitt für Hochkant (Auto-Reframe): wo im breiten Bild ist am meisten los?
    Auffälligkeit = Kanten (Struktur) + Farbsättigung, leicht zur Mitte gewichtet. Gibt die Lage 0..1 zurück."""
    import cv2
    a = np.asarray(img.convert("RGB").resize((320, max(2, int(320 * img.height / img.width)))))
    h, w = a.shape[:2]
    win = int(round(h * target_aspect))
    if win >= w - 2:
        return 0.5
    gray = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY).astype(np.float32)
    edges = cv2.magnitude(cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1))
    sat = cv2.cvtColor(a, cv2.COLOR_RGB2HSV)[..., 1].astype(np.float32)
    sal = edges / (edges.mean() + 1e-3) * 0.6 + sat / (sat.mean() + 1e-3) * 0.4
    col = sal.sum(axis=0)
    csum = np.concatenate([[0], np.cumsum(col)])
    best, bx = -1.0, (w - win) // 2
    for x in range(0, w - win + 1, 2):
        c = (x + win / 2) / w
        v = (csum[x + win] - csum[x]) * (1 - 0.35 * abs(c - 0.5) * 2)
        if v > best:
            best, bx = v, x
    return round(bx / max(1, w - win), 3)
