"""Nachhören: Die Spracherkennung lässt Wiederholungen und "äh"s gern weg, wenn sie den ganzen Satz kennt
("Mein Lehrgang war, mein Lehrgang war, äh …" wird zu einem einzigen, 5 Sekunden langen "Lehrgang").
Diese Stellen werden einzeln und ohne Vorwissen nochmal angehört. Was dabei zusätzlich zu hören ist, wird ins
Transkript eingefügt, damit die Schnitt-Erkennung es findet.

Verdächtig sind:
- Wörter, die viel länger dauern, als sie lang sind,
- Lücken zwischen Wörtern, in denen etwas fast so laut wie Sprache ist,
- die Wörter direkt an einem Schnitt (dort hört man sonst Reste).
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Callable

import numpy as np

from . import cuts
from .transcribe import FILLER_HOTWORDS, FILLER_PROMPT, SR

VERSION = 1
FRAME = 0.02


def expected(word: str) -> float:
    """Ungefähre Sprechdauer eines Worts in Sekunden."""
    return 0.065 * len(re.sub(r"\W", "", word)) + 0.12


def stretched(w: dict, factor: float = 2.2, minimum: float = 0.6) -> bool:
    d = w["e"] - w["s"]
    return d > max(minimum, factor * expected(w["w"])) or (factor >= 2.2 and d > 1.0 and d > 1.6 * expected(w["w"]))


def _db(audio: np.ndarray) -> np.ndarray:
    fr = int(FRAME * SR)
    frames = audio[: len(audio) // fr * fr].reshape(-1, fr)
    return 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)


def candidates(words: list[dict], db: np.ndarray, extra: set[int] | None = None) -> list[tuple[int, int]]:
    """Fenster (erstes, letztes Wort inklusive), die nochmal angehört werden sollen."""
    n = len(words)
    if n < 2:
        return []

    def idx(t: float) -> int:
        return max(0, min(len(db), int(t / FRAME)))

    speech = np.concatenate([db[idx(w["s"]):idx(w["e"])] for w in words if w["e"] > w["s"]] or [np.zeros(1)])
    level = float(np.median(speech)) - 12.0
    wins: list[tuple[int, int]] = []
    for i, w in enumerate(words):
        if stretched(w) or (extra and i in extra and stretched(w, 1.4, 0.35)):
            wins.append((max(0, i - 1), min(n - 1, i + 1)))
    for k in range(n - 1):
        a, b = words[k]["e"] + 0.1, words[k + 1]["s"] - 0.1
        if b - a >= 0.4 and (db[idx(a):idx(b)] > level).sum() * FRAME >= 0.25:
            wins.append((k, k + 1))
    return sorted(set(wins))


def _groups(wins: list[tuple[int, int]], words: list[dict]) -> list[list[tuple[int, int]]]:
    """Überlappende Fenster zu Gruppen zusammenfassen (erst gemeinsam versuchen, sonst einzeln)."""
    groups: list[list[tuple[int, int]]] = []
    for a, b in sorted(wins):
        g = groups[-1] if groups else None
        if g and a <= max(x[1] for x in g) and words[b]["e"] - words[g[0][0]]["s"] < 12:
            g.append((a, b))
        else:
            groups.append([(a, b)])
    return groups


def _same(a: str, b: str) -> bool:
    a, b = cuts.norm(a), cuts.norm(b)
    if not a or not b:
        return False
    if a == b:
        return True
    if min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)):
        return True
    return len(a) >= 4 and SequenceMatcher(None, a, b).ratio() >= 0.75


def splice(orig: list[dict], new: list[dict]) -> list[dict] | None:
    """Fügt die neu gehörten Wörter in das Fenster `orig` ein.

    Jedes alte Wort wird dem gleich lautenden neuen Wort mit der nächstgelegenen Startzeit zugeordnet
    (Reihenfolge bleibt). Die Wörter innen müssen alle wiedergefunden werden, sonst bleibt alles wie es war.
    Eingefügt wird nur, was zeitlich zwischen dem ersten und letzten alten Wort liegt (an den Fensterrändern
    hört die Erkennung oft nur halbe Wörter). Gibt die neue Wortliste fürs Fenster zurück oder None.
    """
    if not new:
        return None
    match: list[int | None] = []
    pos = 0
    for k, w in enumerate(orig):
        best = None
        for j in range(pos, len(new)):
            if _same(w["w"], new[j]["w"]):
                if best is None or abs(new[j]["s"] - w["s"]) < abs(new[best]["s"] - w["s"]):
                    best = j
        if best is None and 0 < k < len(orig) - 1:
            return None  # ein inneres Wort fehlt: der neue Durchgang hat etwas anderes gehört
        match.append(best)
        if best is not None:
            pos = best + 1
    lo = orig[0]["e"] - 0.05
    hi = orig[-1]["s"] + 0.05
    used = {j for j in match if j is not None}
    extras = [dict(new[j], p=min(new[j].get("p", 0.5), 0.6), neu=True) for j in range(len(new))
              if j not in used and new[j]["s"] >= lo and new[j]["e"] <= hi and new[j]["w"].strip()]
    out = []
    changed = bool(extras)
    for k, w in enumerate(orig):
        w = dict(w)
        j = match[k]
        if j is not None and 0 < k < len(orig) - 1 or (j is not None and stretched(w)):
            nw = new[j]
            # Neue Zeiten nur übernehmen, wenn sie im alten Bereich liegen und das Wort kürzer machen
            if w["s"] - 0.1 <= nw["s"] and nw["e"] <= w["e"] + 0.1 and nw["e"] - nw["s"] < w["e"] - w["s"] - 0.05:
                w["s"], w["e"] = round(max(w["s"], nw["s"]), 3), round(min(w["e"], nw["e"]), 3)
                changed = True
        out.append(w)
    if not changed:
        return None
    out.extend(extras)
    out.sort(key=lambda x: x["s"])
    return out


def _listen(model, audio: np.ndarray, t0: float, t1: float, lang: str) -> list[dict]:
    seg = audio[int(max(0.0, t0) * SR):int(t1 * SR)]
    if len(seg) < SR * 0.2:
        return []
    res, _ = model.transcribe(seg, language=lang, word_timestamps=True, beam_size=5, vad_filter=False,
                              condition_on_previous_text=False, initial_prompt=FILLER_PROMPT.get(lang),
                              hotwords=FILLER_HOTWORDS.get(lang))
    out = []
    for s in res:
        for w in s.words or []:
            if w.word.strip():
                out.append({"w": w.word.strip(), "s": round(t0 + w.start, 3), "e": round(t0 + w.end, 3),
                            "p": round(w.probability, 3)})
    return out


def _boundaries(transcript: dict) -> set[int]:
    """Wörter direkt vor und nach einem Schnitt (nach der normalen Erkennung)."""
    cl = cuts.build(transcript, cuts.default_settings(transcript.get("language", "de")))
    flags = cuts.evaluate(transcript, cl)["flags"]
    out = set()
    for i in range(len(flags)):
        if flags[i]:
            continue
        if (i > 0 and flags[i - 1]) or (i + 1 < len(flags) and flags[i + 1]):
            out.add(i)
    return out


def _apply_windows(transcript: dict, audio: np.ndarray, model, wins: list[tuple[int, int]],
                   report: Callable[[float], None]) -> int:
    lang = transcript.get("language", "de")
    loc = [(si, wi) for si, seg in enumerate(transcript["segments"]) for wi in range(len(seg["words"]))]
    words = cuts.flat_words(transcript)
    replace: dict[int, tuple[int, list[dict]]] = {}
    groups = _groups(wins, words)
    for n, g in enumerate(groups):
        report(n / max(1, len(groups)))
        a, b = g[0][0], max(x[1] for x in g)
        new = _listen(model, audio, words[a]["s"] - 0.15, words[b]["e"] + 0.15, lang)
        res = splice(words[a:b + 1], new)
        if res is not None:
            replace[a] = (b, res)
            continue
        if len(g) == 1:
            continue
        # Gemeinsam ging es nicht (ein Wort wurde anders gehört): die Fenster einzeln versuchen
        last = -1
        for a2, b2 in g:
            if a2 <= last:
                continue
            new = _listen(model, audio, words[a2]["s"] - 0.15, words[b2]["e"] + 0.15, lang)
            res = splice(words[a2:b2 + 1], new)
            if res is not None:
                replace[a2] = (b2, res)
                last = b2
    if not replace:
        return 0
    # Neu zusammensetzen: eingefügte Wörter kommen in den Satz-Abschnitt des Worts davor
    segs = [dict(s, words=[]) for s in transcript["segments"]]
    i = 0
    while i < len(words):
        if i in replace:
            b, res = replace[i]
            si = loc[i][0]
            segs[si]["words"].extend(res)
            i = b + 1
        else:
            segs[loc[i][0]]["words"].append(words[i])
            i += 1
    transcript["segments"] = segs
    return len(replace)


def apply(transcript: dict, audio: np.ndarray, model, progress: Callable[[float, str], None] | None = None) -> int:
    """Hört verdächtige Stellen nach und ergänzt das Transkript. Gibt die Zahl der geänderten Stellen zurück."""
    report = progress or (lambda f, m: None)
    db = _db(audio)
    msg = "Listening again to unclear spots (hidden retakes, äh) …"
    wins = candidates(cuts.flat_words(transcript), db)
    changed = _apply_windows(transcript, audio, model, wins, lambda f: report(0.5 * f, msg))
    # Zweiter Durchgang: Wörter direkt an Schnitten
    words = cuts.flat_words(transcript)
    edge = _boundaries(transcript)
    n = len(words)
    wins2 = [(max(0, i - 1), min(n - 1, i + 1)) for i in sorted(edge)
             if stretched(words[i], 1.4, 0.35) and not stretched(words[i])]
    changed += _apply_windows(transcript, audio, model, wins2, lambda f: report(0.5 + 0.5 * f, msg))
    transcript["relisten"] = VERSION
    return changed
