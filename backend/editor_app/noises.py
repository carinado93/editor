"""Laute zwischen den Wörtern finden ("meah", "mh", Schmatzer, Räuspern), die die Spracherkennung nicht als Wort
aufgeschrieben hat. Erkannt am Ton: In einer Lücke zwischen zwei Wörtern ist etwas fast so laut wie Sprache.
Atmen ist viel leiser und bleibt unberührt.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .transcribe import SR, read_wav

FRAME = 0.02


VERSION = 2


def find(wav: Path, words: list[dict], rel_db: float = 14.0, min_len: float = 0.10, margin: float = 0.12,
         face_samples: list[dict] | None = None) -> list[dict]:
    """Gibt [{after: Wortindex, start, end, why}] zurück: Laute zwischen Wort `after` und dem nächsten Wort.

    Ein Laut zählt, wenn die Lautstärke nach dem Wort erst absinkt (Senke ≥ 10 dB) und dann wieder ansteigt.
    Ein Wortende klingt nur aus, ohne erneuten Anstieg, und wird deshalb nie abgeschnitten.
    Zusätzlich: Zunge raus (Gesichtserkennung) in einer Sprechpause, falls das Modell den Wert liefert.
    """
    if not words or not wav.exists():
        return []
    audio = read_wav(wav)
    fr = int(FRAME * SR)
    frames = audio[: len(audio) // fr * fr].reshape(-1, fr)
    db = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)

    def idx(t: float) -> int:
        return max(0, min(len(db), int(t / FRAME)))

    speech = np.concatenate([db[idx(w["s"]):idx(w["e"])] for w in words if w["e"] > w["s"]] or [np.array([-30.0])])
    speech = speech[speech > -50]
    if not len(speech):
        return []
    level = float(np.median(speech)) - rel_db
    quiet = float(np.median(speech)) - 30.0  # echte Stille (deutlich leiser als Atmen am Mikro)

    def separated(t0: float, t1: float, peak: float) -> bool:
        """Zwischen t0 und t1 gibt es Stille oder eine deutliche Senke (≥ 10 dB unter dem Laut)."""
        seg = db[idx(t0):idx(t1)]
        if not len(seg):
            return False
        low = float(seg.min())
        return low < quiet or (low <= peak - 10 and low < level)

    out = []
    for k in range(len(words) - 1):
        a, b = words[k]["e"] + margin, words[k + 1]["s"] - margin
        if b - a < min_len:
            continue
        seg = db[idx(a):idx(b)] > level
        run_start = None
        found = []
        for j, loud in enumerate(list(seg) + [False]):
            if loud and run_start is None:
                run_start = j
            elif not loud and run_start is not None:
                n_s, n_e = a + run_start * FRAME, a + j * FRAME
                peak = float(db[idx(n_s):idx(n_e)].max()) if idx(n_e) > idx(n_s) else level
                # Nur wenn davor und danach Stille oder eine Senke ist (sonst ist es das Ausklingen eines Worts)
                if (j - run_start) * FRAME >= min_len and separated(words[k]["e"], n_s, peak) \
                        and separated(n_e, words[k + 1]["s"], peak):
                    found.append((n_s, n_e))
                run_start = None
        why = "laut"
        # Zunge raus / Grimasse in der Pause (aus der Gesichtserkennung)
        for fs in face_samples or []:
            if fs.get("face") and a <= fs["t"] <= b and fs.get("tongue", 0) > 0.35:
                found.append((max(a, fs["t"] - 0.15), min(b, fs["t"] + 0.25)))
                why = "grimasse"
        if found:
            found.sort()
            out.append({"after": k, "start": round(found[0][0], 3), "end": round(max(e for _, e in found), 3),
                        "why": why})
    return out
