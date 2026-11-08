"""Thumbnail-Vorschläge: Bilder, in denen Carina gut aussieht.

Bewertung aus der Gesichtserkennung (blick.json): Augen offen, Blick in die Kamera, Lächeln, Gesicht groß genug,
plus Bildschärfe (wird am Original-Bild gemessen). Nur aus Stellen, die im fertigen Video bleiben.
Die Vorschläge liegen nicht zu nah beieinander (mind. 5 s Abstand), damit es echte Auswahl gibt.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from . import gaze, media
from .errors import UserError


def score_samples(data: dict, keep: list[list[float]]) -> list[tuple[float, float]]:
    base = gaze.baseline(data.get("samples", []))
    out = []
    for s in data.get("samples", []):
        if not s.get("face") or not any(a + 0.2 <= s["t"] <= b - 0.2 for a, b in keep):
            continue
        eyes_open = 1.0 - min(1.0, s["blink"] * 1.6)
        look = 1.0
        if base:
            look -= min(1.0, abs(s["pitch"] - base["pitch"]) / 20 + abs(s["yaw"] - base["yaw"]) / 25
                        + max(0.0, s["side"] - base["side"]) + max(0.0, s["down"] - base["down"]))
        smile = s.get("smile", 0)
        size = (s["box"][2] - s["box"][0]) * (s["box"][3] - s["box"][1])
        talk = s.get("jaw", 0)  # weit offener Mund beim Sprechen sieht selten gut aus
        sc = 2.0 * eyes_open + 2.0 * max(0.0, look) + 1.5 * smile + min(1.0, size * 4) - 1.2 * max(0.0, talk - 0.25)
        out.append((s["t"], sc))
    return out


def pick(scored: list[tuple[float, float]], n: int = 6, min_gap: float = 5.0) -> list[float]:
    chosen: list[float] = []
    for t, _ in sorted(scored, key=lambda x: -x[1]):
        if all(abs(t - c) >= min_gap for c in chosen):
            chosen.append(t)
        if len(chosen) >= n * 2:
            break
    return chosen


def sharpness(img_path: Path) -> float:
    import cv2

    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0
    return float(cv2.Laplacian(img, cv2.CV_64F).var())


def make(src: Path, gaze_data: dict, keep: list[list[float]], out_dir: Path, n: int = 6) -> list[dict]:
    if not gaze_data:
        raise UserError("Die Blick-Erkennung ist noch nicht fertig. Bitte kurz warten und nochmal versuchen.")
    candidates = pick(score_samples(gaze_data, keep), n)
    if not candidates:
        raise UserError("Keine passenden Bilder gefunden (kein Gesicht erkannt).")
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("thumb_*.jpg"):
        old.unlink()
    shots = []
    scored = dict(score_samples(gaze_data, keep))
    for t in candidates:
        f = out_dir / f"thumb_{t:08.2f}.jpg".replace(".", "_", 1)
        r = media.run([media.ffmpeg(), "-hide_banner", "-y", "-ss", f"{t:.2f}", "-i", str(src), "-frames:v", "1",
                       "-q:v", "2", str(f)])
        if r.returncode != 0 or not f.exists():
            continue
        shots.append({"file": f.name, "t": round(t, 2), "score": scored.get(t, 0), "sharp": sharpness(f)})
    if not shots:
        raise UserError("Die Bilder konnten nicht aus dem Video geholt werden.")
    sharp_med = float(np.median([s["sharp"] for s in shots])) or 1.0
    for s in shots:  # unscharfe Bilder (Bewegung) nach hinten
        s["total"] = round(s["score"] + min(1.0, s["sharp"] / sharp_med) * 1.5, 3)
    shots.sort(key=lambda s: -s["total"])
    for s in shots[n:]:
        (out_dir / s["file"]).unlink(missing_ok=True)
    return shots[:n]
