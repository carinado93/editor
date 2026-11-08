"""Automatische Buzzword-Vorschläge ohne KI (Ersatz, wenn Ollama nicht läuft).

Regeln: Themenwörter aus Carinas Nische, Zahlen und starke Inhaltswörter, ca. eins alle 15 Sekunden,
nie zwei direkt hintereinander.
"""
from __future__ import annotations

import re

from .cuts import norm

THEMEN = {
    # Deutsch
    "stress", "burnout", "erschöpfung", "erschöpft", "nervensystem", "atmen", "atmung", "pause", "pausen",
    "ruhe", "grenzen", "selbstfürsorge", "überforderung", "überfordert", "angst", "druck", "schlaf", "körper",
    "gewohnheiten", "gewohnheit", "routine", "routinen", "prävention", "wohlbefinden", "achtsamkeit", "perfektionismus",
    "notizbuch", "müde", "energie", "balance", "loslassen", "kraft", "gedanken",
    # Englisch
    "burnt", "burned", "exhausted", "exhaustion", "nervous", "breathe", "breathing", "rest", "calm", "boundaries",
    "overwhelm", "overwhelmed", "anxiety", "pressure", "sleep", "body", "habits", "habit", "routines",
    "wellbeing", "mindfulness", "perfectionism", "notebook", "tired", "energy", "giveaway", "free", "win",
}

STOP = {
    "der", "die", "das", "und", "ist", "ich", "du", "es", "ein", "eine", "einen", "zu", "mit", "auf", "für", "nicht",
    "wenn", "dann", "aber", "auch", "so", "wie", "was", "dass", "sich", "mir", "mich", "dir", "dich", "wir", "sie",
    "the", "and", "is", "i", "you", "it", "a", "an", "to", "with", "on", "for", "not", "if", "then", "but", "also",
    "so", "like", "what", "that", "this", "these", "those", "my", "your", "me", "we", "they", "of", "in", "at", "be",
    "will", "can", "just", "about", "because", "there", "here", "have", "has", "been", "are", "was", "were", "do",
    "really", "right", "now", "make", "made", "going", "thing", "things", "something", "someone", "would", "could",
}


def suggest(words: list[dict], flags: list, every: float = 15.0) -> list[dict]:
    kept = [(k, w) for k, (w, f) in enumerate(zip(words, flags)) if not f]
    if not kept:
        return []

    def score(k: int, w: dict) -> float:
        t = norm(w["w"])
        if not t or t in STOP:
            return 0
        s = 0.0
        if t in THEMEN:
            s += 5
        if re.fullmatch(r"\d+([.,]\d+)?%?|\d+(st|nd|rd|th)", t):
            s += 4
        if len(t) >= 7:
            s += 1.5
        if w["w"][:1].isupper() and k > 0 and not re.search(r"[.!?]$", words[k - 1]["w"]):
            s += 1  # Eigenname mitten im Satz
        return s

    out: list[dict] = []
    used: set[str] = set()
    window_start = kept[0][1]["s"]
    best = None
    for k, w in kept:
        if w["s"] - window_start >= every:
            if best and best[0] >= 3:
                out.append({"start": best[1], "end": best[1] + 1})
                used.add(norm(words[best[1]]["w"]))
            window_start, best = w["s"], None
        sc = score(k, w) if norm(w["w"]) not in used else 0
        if sc and (best is None or sc > best[0]):
            best = (sc, k)
    if best and best[0] >= 3:
        out.append({"start": best[1], "end": best[1] + 1})
    return out
