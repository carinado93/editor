"""Laute zwischen den Wörtern finden ("meah", "mh", Schmatzer, Räuspern), die die Spracherkennung nicht als Wort
aufgeschrieben hat. Erkannt am Ton: In einer Lücke zwischen zwei Wörtern ist etwas fast so laut wie Sprache.
Atmen ist viel leiser und bleibt unberührt.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .transcribe import SR, read_wav

FRAME = 0.02


def find(wav: Path, words: list[dict], rel_db: float = 14.0, min_len: float = 0.15, margin: float = 0.12) -> list[dict]:
    """Gibt [{after: Wortindex, start, end}] zurück: Laute zwischen Wort `after` und dem nächsten Wort."""
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

    def has_quiet(t0: float, t1: float, need: float = 0.08) -> bool:
        q = db[idx(t0):idx(t1)] < quiet
        run = best = 0
        for v in q:
            run = run + 1 if v else 0
            best = max(best, run)
        return best * FRAME >= need

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
                # Nur wenn vorher und nachher kurz Stille ist (sonst ist es das Ausklingen eines Worts)
                if (j - run_start) * FRAME >= min_len and has_quiet(words[k]["e"], n_s) \
                        and has_quiet(n_e, words[k + 1]["s"]):
                    found.append((n_s, n_e))
                run_start = None
        if found:
            out.append({"after": k, "start": round(found[0][0], 3), "end": round(found[-1][1], 3)})
    return out
