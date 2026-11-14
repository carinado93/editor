"""Schnitt-Erkennung für den YouTube-Rohschnitt (nicht-destruktiv: es entsteht nur eine Schnittliste).

Erkennt:
- Retakes: Carina setzt neu an und sagt dieselben Wörter nochmal ("I decided to make a, I decided to make a giveaway").
  Der erste Versuch bis zum Neuanfang wird geschnitten, die letzte Version bleibt.
  Regel: höchstens MAX_GAP Sekunden *Sprechen* zwischen dem ersten Versuch und dem Neuanfang
  (stille Denkpausen zählen nicht mit).
- Signalwörter ("again", "nochmal", "von vorne" …): der angefangene Satz davor und das Signalwort fliegen raus.
- doppelte Wörter ("then then") und abgebrochene Wörter ("Resi- Resilienz").
- Füllwörter (äh, ähm, uh, um …), pro Wort ein- und ausschaltbar.
- Pausen: zu lange Stille wird auf eine natürliche Länge gekürzt (locker / normal / straff).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher

DEFAULT_SIGNAL_WORDS = ["again", "nochmal", "noch mal", "noch einmal", "von vorne", "stopp", "stop", "cut"]

# Füllwörter: (Wort, standardmäßig an?)
DEFAULT_FILLERS = {
    "de": {"äh": True, "ähm": True, "öh": True, "öhm": True, "hm": True, "hmm": True, "mhm": True, "mh": True,
           "mäh": True, "meh": True, "ehm": True, "äm": True, "mmh": True, "eh": False, "ah": False,
           "also": False, "quasi": False, "halt": False, "sozusagen": False, "irgendwie": False},
    "en": {"uh": True, "um": True, "erm": True, "er": True, "hm": True, "hmm": True, "mhm": True, "mh": True,
           "meh": True, "ehm": True, "mmh": True, "uhm": True, "eh": False, "ah": False,
           "like": False, "you know": False, "i mean": False, "basically": False, "actually": False},
}

# Tempo: (längste erlaubte Pause, auf diese Länge wird gekürzt), Sekunden
TEMPO = {
    "locker": (0.75, 0.50),
    "normal": (0.45, 0.30),
    "straff": (0.30, 0.18),
    # "Ich schneide selbst": keine Pause wird automatisch gekürzt, Anfang und Ende bleiben ganz
    "original": (1e9, 1e9),
}

# Wörter, die man absichtlich doppelt sagt ("sehr sehr") → nur Vorschlag
INTENSIFIERS = {"very", "really", "so", "sehr", "ganz", "viel", "much", "many", "ja", "nein", "no", "yes", "bye", "tschüss"}

# Wörter, mit denen man sich selbst korrigiert ("beim dritten, nein, beim zweiten")
CORRECTION_WORDS = {"nein", "nee", "egal", "sorry", "quatsch", "falsch", "no", "wait", "nope"}

ALL_FILLERS = {f for lang in DEFAULT_FILLERS.values() for f, on in lang.items() if on and " " not in f}

REASON_TEXT = {
    "retake": "Retake: you started again, the last version stays",
    "signal": "Signal word: sentence was broken off",
    "doppelt": "Doubled word",
    "fragment": "Broken-off word",
    "fuellwort": "Filler word",
    "blick": "Looking away from the camera",
    "anfang": "Silence at the start",
    "ende": "Silence at the end",
}


@dataclass
class Detection:
    id: str
    type: str          # retake | signal | doppelt | fragment | fuellwort
    start: int         # erster Wort-Index (inklusive)
    end: int           # letzter Wort-Index + 1
    sure: bool         # False = nur Vorschlag (standardmäßig nicht aktiv)
    reason: str
    active: bool


def norm(word: str) -> str:
    w = unicodedata.normalize("NFC", word).lower().strip()
    w = re.sub(r"^[\"'„“‚‘(\[]+|[\"'“”‘’)\].,!?;:…]+$", "", w)
    return w.replace("’", "'")


def ends_clause(word: str) -> bool:
    return bool(re.search(r"[.,!?;:…]$", word.strip()))


def ends_sentence(word: str) -> bool:
    return bool(re.search(r"[.!?…]$", word.strip()))


def flat_words(transcript: dict) -> list[dict]:
    return [w for seg in transcript["segments"] for w in seg["words"]]


def _speech_between(words: list[dict], a: int, b: int, pause: float = 0.3) -> float:
    """Sprechzeit zwischen Wort a (inklusive) und Wort b (exklusive). Stille über `pause` zählt nicht."""
    total = 0.0
    for k in range(a, b):
        total += max(0.0, words[k]["e"] - words[k]["s"])
        if k + 1 < len(words):
            gap = words[k + 1]["s"] - words[k]["e"]
            if 0 < gap <= pause:
                total += gap
    return total


def _starts_clause(words: list[dict], i: int) -> bool:
    if i == 0:
        return True
    prev = words[i - 1]
    return ends_clause(prev["w"]) or words[i]["s"] - prev["e"] >= 0.25


def _overlap(tokens: list[str], i: int, j: int) -> float:
    """Wie sehr der erste Versuch (i..j-1) dem Neuanfang ab j gleicht (0..1).
    Neuanfang: "Mein Lehrgang war stattlich zugelassen" → "Mein Lehrgang war stattlich geprüft" (hoch).
    Absichtliche Aufzählung: "ich wollte nicht mehr nur …" → "ich wollte nicht wieder …" (niedrig)."""
    a = [t for t in tokens[i:j] if t and t not in ALL_FILLERS]
    b = [t for t in tokens[j:j + 2 * len(a) + 2] if t and t not in ALL_FILLERS]
    if not a:
        return 1.0
    same = sum(m.size for m in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    return same / len(a)


def detect_chains(words: list[dict], tokens: list[str], max_gap: float) -> list[tuple[int, int]]:
    """Mehrere Anläufe mit demselben Satzanfang hintereinander ("Mein Lehrgang war … Mein Lehrgang war … Mein
    Lehrgang war …"): alles vom ersten bis zum letzten Anlauf wird geschnitten, nur der letzte bleibt."""
    n = len(tokens)
    starts: dict[tuple[str, ...], list[int]] = {}
    for p in range(n - 2):
        key = tuple(tokens[p:p + 3])
        if all(key) and not any(t in ALL_FILLERS for t in key) and _starts_clause(words, p):
            starts.setdefault(key, []).append(p)
    links: dict[int, int] = {}
    for pos in starts.values():
        for p, q in zip(pos, pos[1:]):
            if _speech_between(words, p, q) <= 2 * max_gap and _overlap(tokens, p, q) >= 0.7:
                links[p] = q
    out = []
    used: set[int] = set()
    for p in sorted(links):
        if p in used:
            continue
        q = p
        while q in links:
            used.add(q)
            q = links[q]
        out.append((p, q))
    return out


def detect_retakes(words: list[dict], tokens: list[str], max_gap: float) -> list[tuple[int, int, int, bool]]:
    """Findet Neuanfänge. Gibt (i, j, k, sicher) zurück: Wörter i..j-1 schneiden, ab j (k Wörter gleich) bleibt."""
    n = len(tokens)
    cands: list[tuple[int, int, int, bool]] = []
    for j in range(1, n):
        best = None
        for i in range(j - 1, -1, -1):
            if tokens[i] != tokens[j] or not tokens[i]:
                continue
            if i > 0 and tokens[i - 1] == tokens[j - 1] and tokens[i - 1]:
                continue  # Teil einer längeren Wiederholung, die schon ein Wort früher beginnt
            k = 0
            while j + k < n and i + k < j and tokens[i + k] == tokens[j + k]:
                k += 1
            if _speech_between(words, i + k, j) > max_gap:
                if words[j]["s"] - words[i]["s"] > 120:
                    break
                continue
            if k == 1:
                if i != j - 1:
                    continue  # einzelnes Wort nur, wenn direkt doppelt (eigene Regel unten)
                continue
            after_filler = j > 0 and tokens[j - 1] in ALL_FILLERS
            if k == 2 and not (_starts_clause(words, i) and _starts_clause(words, j)) and not after_filler:
                continue  # zwei gleiche Wörter mitten im Satz ("in the … in the") sind meist kein Retake
            # Kurze Übereinstimmung, aber der Rest ist ganz anders: eher eine Aufzählung → nur Vorschlag
            sure = k > 2 or _overlap(tokens, i, j) >= 0.7 or any(t in CORRECTION_WORDS for t in tokens[i:j])
            if best is None or k > best[2]:
                best = (i, j, k, sure)
        if best:
            cands.append(best)
    # Längste Übereinstimmungen zuerst; ein Retake darf nicht den behaltenen Teil eines anderen schneiden
    cands.sort(key=lambda c: (-c[2], c[1] - c[0]))
    accepted: list[tuple[int, int, int, bool]] = []
    for c in cands:
        i, j, k, _ = c
        cut, keep = (i, j), (j, j + k)
        clash = False
        for a in accepted:
            a_cut, a_keep = (a[0], a[1]), (a[1], a[1] + a[2])
            # Mehrere Anläufe hintereinander: ein *späterer* Neuanfang darf den vorherigen Gewinner ersetzen
            if cut[0] < a_keep[1] and a_keep[0] < cut[1] and not (j > a[1] and cut[0] >= a[1]):
                clash = True
            # Was dieser Neuanfang behalten will, darf ein anderer Retake nicht schon geschnitten haben
            if keep[0] < a_cut[1] and a_cut[0] < keep[1]:
                clash = True
            if cut[0] >= a_cut[0] and cut[1] <= a_cut[1]:
                clash = True  # liegt schon komplett in einem Schnitt
        if not clash:
            accepted.append(c)
    return sorted(accepted)


def _signal_positions(words: list[dict], tokens: list[str], signal_words: list[str]) -> list[tuple[int, int]]:
    """Signalwort-Stellen (Start, Ende exklusiv). Nur wenn das Wort allein steht (Pause oder Satzzeichen davor/danach),
    damit "stop doing this" oder "lies es nochmal" nicht getroffen werden."""
    out = []
    phrases = sorted({tuple(norm(x).split()) for x in signal_words if norm(x)}, key=len, reverse=True)
    n = len(tokens)
    i = 0
    while i < n:
        hit = None
        for ph in phrases:
            if tuple(tokens[i:i + len(ph)]) == ph:
                hit = len(ph)
                break
        if hit:
            end = i + hit
            before_ok = i == 0 or ends_clause(words[i - 1]["w"]) or words[i]["s"] - words[i - 1]["e"] >= 0.4
            after_ok = end >= n or ends_clause(words[end - 1]["w"]) or words[end]["s"] - words[end - 1]["e"] >= 0.4
            if before_ok and after_ok:
                out.append((i, end))
            i = end
        else:
            i += 1
    return out


def detect(transcript: dict, settings: dict, gaze_events: list[dict] | None = None) -> list[Detection]:
    if settings.get("no_cuts"):
        return []
    words = flat_words(transcript)
    tokens = [norm(w["w"]) for w in words]
    lang = transcript.get("language", "de")
    max_gap = float(settings.get("max_gap", 5.0))
    dets: list[Detection] = []

    def add(type_: str, a: int, b: int, sure: bool, extra: str = ""):
        if b <= a:
            return
        reason = REASON_TEXT[type_] + (f" ({extra})" if extra else "")
        dets.append(Detection(f"{type_}-{a}-{b}", type_, a, b, sure, reason, sure))

    # 1. Signalwörter: vom Anfang des abgebrochenen Satzes bis einschließlich Signalwort
    for a, b in _signal_positions(words, tokens, settings.get("signal_words", DEFAULT_SIGNAL_WORDS)):
        start = a
        while start > 0 and not ends_sentence(words[start - 1]["w"]) and words[start]["s"] - words[start - 1]["e"] < 0.8:
            start -= 1
        add("signal", start, b, True, " ".join(w["w"] for w in words[a:b]))

    # 2. Retakes (Neuanfang mit denselben Wörtern)
    for i, j in detect_chains(words, tokens, max_gap):
        add("retake", i, j, True, f"several attempts, the last one stays: \"{' '.join(w['w'] for w in words[j:j + 4])}…\"")
    for i, j, k, sure in detect_retakes(words, tokens, max_gap):
        add("retake", i, j, sure, f"same start: \"{' '.join(w['w'] for w in words[j:j + min(k, 6)])}…\"")

    # 3. Direkt doppelte Wörter und abgebrochene Wörter
    for i in range(len(tokens) - 1):
        t, nxt = tokens[i], tokens[i + 1]
        if not t:
            continue
        if t == nxt and words[i + 1]["s"] - words[i]["e"] < 1.0:
            add("doppelt", i, i + 1, t not in INTENSIFIERS, words[i]["w"])
        elif (words[i]["w"].rstrip().endswith("-") or (len(t) >= 2 and nxt.startswith(t) and len(nxt) > len(t) + 1)) \
                and words[i]["e"] - words[i]["s"] < 0.6:
            add("fragment", i, i + 1, True, words[i]["w"])

    # 4. Füllwörter
    fillers = settings.get("fillers") or {k: v for k, v in DEFAULT_FILLERS.get(lang, DEFAULT_FILLERS["en"]).items()}
    phrases = sorted(((tuple(f.split()), on) for f, on in fillers.items()), key=lambda x: -len(x[0]))
    i = 0
    while i < len(tokens):
        for ph, on in phrases:
            if tuple(tokens[i:i + len(ph)]) == ph:
                if on:
                    add("fuellwort", i, i + len(ph), True, " ".join(ph))
                i += len(ph) - 1
                break
        i += 1

    # 5. Blick weg (nur Vorschlag: Carina entscheidet)
    for ev in gaze_events or []:
        inside = [k for k, w in enumerate(words) if ev["start"] <= (w["s"] + w["e"]) / 2 <= ev["end"]]
        if inside:
            # Wegschauen ohne richtigen Inhalt (nichts oder nur "und", "hm" …) wird gleich geschnitten
            filler_only = len(inside) <= 2 and all(len(tokens[k]) <= 4 for k in inside)
            add("blick", inside[0], inside[-1] + 1, filler_only, f"{ev['length']:.1f} s, {ev['reason']}")

    # Doppelte Treffer zusammenfassen: gleiche Wörter nur einmal (der erste Grund gewinnt)
    seen: set[str] = set()
    unique = []
    for d in dets:
        if d.id not in seen:
            seen.add(d.id)
            unique.append(d)
    return unique


def word_cut_flags(n: int, detections: list[dict], manual: dict) -> list[str | None]:
    """Für jedes Wort: Grund, warum es geschnitten wird, oder None."""
    flags: list[str | None] = [None] * n
    for d in detections:
        if d["active"]:
            for k in range(d["start"], min(d["end"], n)):
                flags[k] = flags[k] or d["type"]
    for k in manual.get("keep", []):
        if 0 <= k < n:
            flags[k] = None
    for k in manual.get("cut", []):
        if 0 <= k < n:
            flags[k] = "manuell"
    return flags


def timeline(words: list[dict], flags: list[str | None], duration: float, tempo: str = "normal",
             pause_keep: list[int] | None = None, noises: list[dict] | None = None) -> dict:
    """Berechnet, welche Zeitbereiche des Videos bleiben. Gibt {keep:[[s,e],…], pauses:[…], new_duration} zurück.

    Zwischen zwei behaltenen Wörtern bleibt höchstens die Pause des gewählten Tempos.
    """
    max_pause, target = TEMPO.get(tempo, TEMPO["normal"])
    pause_keep = set(pause_keep or [])
    kept = [k for k, f in enumerate(flags) if f is None]
    lead = 0.15  # so viel Luft vor dem ersten und nach dem letzten Wort
    whole = tempo == "original"
    if not kept:
        if whole and not any(flags):  # ganz ohne Sprechen (z. B. nur Bilder/B-Roll): alles bleibt
            return {"keep": [[0.0, round(duration, 3)]], "pauses": [], "new_duration": round(duration, 2)}
        return {"keep": [], "pauses": [], "new_duration": 0.0}
    segs: list[list[float]] = []
    pauses = []
    cur_start = 0.0 if whole and kept[0] == 0 else max(0.0, words[kept[0]]["s"] - lead)
    noise_list = sorted(noises or [], key=lambda n: n["start"])
    for a, b in zip(kept, kept[1:]):
        wa, wb = words[a], words[b]
        gap = wb["s"] - wa["e"]
        removed_between = b != a + 1
        loud = [n for n in noise_list if wa["e"] <= n["start"] and n["end"] <= wb["s"]]
        has_noise = bool(loud) and a not in pause_keep
        if not removed_between and not has_noise and (gap <= max_pause or a in pause_keep):
            continue
        if not removed_between:
            pauses.append({"after": a, "start": round(wa["e"], 3), "end": round(wb["s"], 3),
                           "length": round(gap, 2), "kept": False, "noise": bool(loud)})
        half = min(target / 2, max(gap, 0) / 2)
        if not removed_between and gap > 1.5 and not ends_clause(wa["w"]):
            half = min(half, 0.05)  # lange Denkpause mitten im Satz ("Ich … bin Carina"): fast ganz zu
        after, before = half, half
        if removed_between:
            # Die Luft darf nicht in ein geschnittenes Nachbarwort hineinreichen (sonst bleibt "I m…" hörbar)
            after = min(half, max(0.02, words[a + 1]["s"] - wa["e"] - 0.02))
            before = min(half, max(0.02, wb["s"] - words[b - 1]["e"] - 0.02))
        if has_noise:
            # Laute wie "meah" ganz herausschneiden
            after = min(after, max(0.02, loud[0]["start"] - wa["e"] - 0.03))
            before = min(before, max(0.02, wb["s"] - loud[-1]["end"] - 0.03))
        segs.append([cur_start, wa["e"] + after])
        cur_start = wb["s"] - before
    # Pausen, die behalten werden sollen, trotzdem anzeigen
    for a in sorted(pause_keep):
        if a in kept and a + 1 < len(words) and flags[a + 1] is None:
            gap = words[a + 1]["s"] - words[a]["e"]
            loud = any(n["after"] == a for n in noise_list)
            if gap > max_pause or loud:
                pauses.append({"after": a, "start": round(words[a]["e"], 3), "end": round(words[a + 1]["s"], 3),
                               "length": round(gap, 2), "kept": True, "noise": loud})
    end = duration if whole and kept[-1] == len(words) - 1 else min(duration, words[kept[-1]]["e"] + lead)
    segs.append([cur_start, end])
    segs = [[round(s, 3), round(e, 3)] for s, e in segs if e - s > 0.02]
    pauses.sort(key=lambda p: p["after"])
    return {"keep": segs, "pauses": pauses, "new_duration": round(sum(e - s for s, e in segs), 2)}


def default_settings(language: str) -> dict:
    return {
        "tempo": "normal",
        "max_gap": 5.0,
        "noises": True,
        "signal_words": list(DEFAULT_SIGNAL_WORDS),
        "fillers": dict(DEFAULT_FILLERS.get(language, DEFAULT_FILLERS["en"])),
    }


def build(transcript: dict, settings: dict, manual: dict | None = None, pause_keep: list[int] | None = None,
          gaze_events: list[dict] | None = None) -> dict:
    """Komplette Schnittliste (wird als schnitte.json gespeichert)."""
    dets = [asdict(d) for d in detect(transcript, settings, gaze_events)]
    return {"version": 1, "settings": settings, "detections": dets,
            "manual": manual or {"cut": [], "keep": []}, "pause_keep": pause_keep or []}


def evaluate(transcript: dict, cutlist: dict) -> dict:
    words = flat_words(transcript)
    if cutlist["settings"].get("no_cuts"):  # Reel veredeln: Länge, Tempo und Ablauf bleiben exakt
        dur = round(transcript.get("duration", words[-1]["e"] if words else 0), 3)
        return {"flags": [None] * len(words), "keep": [[0.0, dur]], "pauses": [], "new_duration": dur,
                "old_duration": dur}
    flags = word_cut_flags(len(words), cutlist["detections"], cutlist["manual"])
    time_cuts = [r for r in cutlist.get("time_cuts", []) if r[1] - r[0] > 0.05]
    for k, w in enumerate(words):  # Wörter in selbst gewählten Zeitbereichen sind auch geschnitten
        mid = (w["s"] + w["e"]) / 2
        if flags[k] is None and any(a <= mid <= b for a, b in time_cuts):
            flags[k] = "zeit"
    tl = timeline(words, flags, transcript.get("duration", words[-1]["e"] if words else 0),
                  cutlist["settings"].get("tempo", "normal"), cutlist.get("pause_keep"),
                  cutlist.get("noises") if cutlist["settings"].get("noises", True) else None)
    if time_cuts:  # auch Stellen ohne Sprechen (z. B. Anfang/Ende eines Clips) herausnehmen
        keep = []
        for s0, e0 in tl["keep"]:
            parts = [[s0, e0]]
            for a, b in time_cuts:
                parts = [q for s1, e1 in parts for q in ([[s1, min(e1, a)]] if s1 < a else []) +
                         ([[max(s1, b), e1]] if e1 > b else [])]
            keep += [[round(x, 3), round(y, 3)] for x, y in parts if y - x > 0.04]
        tl["keep"] = keep
        tl["new_duration"] = round(sum(e - s for s, e in keep), 2)
    return {"flags": flags, **tl, "old_duration": round(transcript.get("duration", 0), 2)}
