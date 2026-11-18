"""Schnittplan für den Drone Cutter: welche Momente, in welcher Reihenfolge, wie lang.

Regeln (Stil "Explore the World 4K"):
  * Reel 9:16: Aufnahmen 1,5–3 s, die BESTE Aufnahme zuerst (Hook, trägt den Ort-Titel, darf bis 3,2 s).
  * YouTube 16:9: Aufnahmen 4–10 s mit "Atem-Rhythmus" (lang – kürzer – lang …).
  * Schnitte liegen auf Musik-Schlägen (wenn Musik da ist), Gesamtlänge stimmt aufs Bild genau.
  * Gleiche Bilder nie zweimal; aufeinanderfolgende Aufnahmen möglichst aus verschiedenen Szenen.
  * Ende: ruhige, schöne Aufnahme (Ausklang).
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass

MODES = {
    "reel": {"min": 1.5, "max": 3.0, "pattern": [2.4, 1.8, 2.2, 1.6, 2.6, 2.0], "first_max": 3.2},
    "youtube": {"min": 4.0, "max": 10.0, "pattern": [7.0, 5.0, 8.5, 4.5, 6.5, 9.0], "first_max": 10.0},
}


@dataclass
class Shot:
    clip: str
    src_in: float      # Start im Quell-Clip (s)
    src_dur: float     # verwendete Länge im Quell-Clip (s)
    t0: float          # Start auf der Zeitleiste (s)
    dur: float         # Länge auf der Zeitleiste (s)
    speed: float = 1.0
    score: float = 0.0
    hero: bool = False
    transit: bool = False
    direction: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _snap(t: float, fps: float) -> float:
    return round(round(t * fps) / fps, 6)


def cut_times(duration: float, mode: str, beats: list[float] | None, fps: float, seed: int = 0,
              first_min: float = 0.0) -> list[float]:
    """Schnittzeitpunkte 0 = t_0 < t_1 < … < t_n = duration (bildgenau, wenn möglich auf Schlägen)."""
    cfg = MODES[mode]
    rnd = random.Random(seed)
    pat = cfg["pattern"][:]
    rnd.shuffle(pat)
    lo, hi = cfg["min"], cfg["max"]
    bts = sorted(b for b in (beats or []) if 0 < b < duration - lo * 0.75)
    cuts = [0.0]
    k = 0
    while True:
        t = cuts[-1]
        first = len(cuts) == 1
        want = pat[k % len(pat)] * (1 + rnd.uniform(-0.08, 0.08))
        a, b = (max(lo, first_min) if first else lo), (cfg["first_max"] if first else hi)
        want = min(b, max(a, want))
        if duration - t <= b + 1e-6 and duration - t >= a * 0.9 - 1e-6:
            break                                  # Rest passt als letzte Aufnahme
        cand = [x for x in bts if a - 1e-6 <= x - t <= b + 1e-6 and duration - x >= lo * 0.9 - 1e-6]
        if not cand:   # kein Schlag im Wunschbereich: nächster Schlag knapp außerhalb (bis ±25 %)
            cand = [x for x in bts if a * 0.85 - 1e-6 <= x - t <= b * 1.25 + 1e-6 and duration - x >= lo * 0.9 - 1e-6]
        # erste Aufnahme trägt den Titel: lieber etwas länger als kürzer
        nxt = min(cand, key=lambda x: abs(x - t - want) + (1.0 if first and x - t < a - 1e-6 else 0)) if cand else t + want
        if duration - nxt < lo:                    # sonst bliebe ein zu kurzes Ende
            nxt = duration - lo
        cuts.append(_snap(nxt, fps))
        k += 1
        if len(cuts) > 2000:
            break
    cuts.append(_snap(duration, fps))
    return cuts


def _free(used: dict, clip: str, a: float, b: float) -> bool:
    return all(b <= x or y <= a for x, y in used.get(clip, []))


def _window(m: dict, L: float, used: dict) -> float | None:
    """Freier Ausschnitt der Länge L in Moment m (möglichst mittig). None, wenn keiner frei ist."""
    if m["dur"] + 1e-6 < L:
        return None
    mid = m["start"] + (m["dur"] - L) / 2
    # alle Startpunkte im 0,25-s-Raster, die Mitte zuerst (bester Teil), dann nach außen
    n = int((m["dur"] - L) / 0.25)
    starts = sorted({round(mid, 3), m["start"], round(m["start"] + m["dur"] - L, 3),
                     *(round(m["start"] + k * 0.25, 3) for k in range(n + 1))}, key=lambda s: abs(s - mid))
    for s in starts:
        if _free(used, m["clip"], s, s + L):
            return s
    return None


def plan(moments: list[dict], duration: float, mode: str = "reel", beats: list[float] | None = None,
         fps: float = 30.0, seed: int = 0, title_len: float = 0.0) -> list[Shot]:
    """moments: aus analysis (alle Clips), nach Punkten sortiert. Gibt die Aufnahmen in Reihenfolge zurück."""
    if not moments:
        raise ValueError("No usable moments found – the clips may be too dark, too shaky or too short.")
    first_min = min(title_len, MODES[mode]["first_max"]) if mode == "reel" and title_len else 0.0
    cuts = cut_times(duration, mode, beats, fps, seed, first_min)
    slots = [b - a for a, b in zip(cuts[:-1], cuts[1:])]
    rnd = random.Random(seed)
    best = max(m["score"] for m in moments)
    # wackelige/dunkle/unscharfe Momente nur, wenn sonst nichts mehr frei ist (stehen am Ende der Liste)
    good = [m for m in moments if m["score"] >= 0.55 * best]
    weak = [m for m in moments if m["score"] < 0.55 * best]
    jitter = lambda m: m["score"] + rnd.uniform(0, 0.03 if seed else 0)  # noqa: E731 – Varianten
    pool = sorted(good, key=jitter, reverse=True) + sorted(weak, key=jitter, reverse=True)
    used: dict[str, list[tuple[float, float]]] = {}
    shots: list[Shot] = []

    def take(m: dict, L: float, speed: float = 1.0) -> Shot | None:
        src_L = L * speed
        s = _window(m, src_L, used)
        if s is None:
            return None
        used.setdefault(m["clip"], []).append((s, s + src_L))
        return Shot(m["clip"], round(s, 3), round(src_L, 3), 0.0, L, speed, m["score"], m.get("hero", False),
                    m.get("transit", False), m.get("direction", ""))

    order = list(range(len(slots)))
    # Hook zuerst, dann das Ende (ruhiger Ausklang), dann die Mitte
    if len(order) > 2:
        order = [0, len(slots) - 1, *range(1, len(slots) - 1)]
    placed: dict[int, Shot] = {}
    for i in order:
        L = slots[i]
        prev = placed.get(i - 1)
        cands = pool
        if i == 0:   # Hook: Helden-Moment bevorzugen
            cands = sorted(pool, key=lambda m: (m in good, m.get("hero", False), m["score"]), reverse=True)
        elif i == len(slots) - 1 and len(slots) > 1:   # Ende: ruhig (keine schnelle Fahrt)
            cands = sorted(pool, key=lambda m: (m in good, not m.get("transit", False), m["score"]), reverse=True)
        sh = None
        for pass_ in range(3):
            for m in cands:
                if pass_ == 0 and prev and m.get("scene") == _scene_of(prev, pool) and m["clip"] == prev.clip:
                    continue   # nicht zweimal hintereinander dieselbe Szene
                sh = take(m, L)
                if sh:
                    break
            if sh:
                break
            if pass_ == 1:   # nichts frei: etwas schneller abspielen (bis 1,5×), damit es passt
                for m in cands:
                    sh = take(m, L, speed=min(1.5, max(1.0, m["dur"] / L)))
                    if sh and sh.speed <= 1.5:
                        break
                    sh = None
                if sh:
                    break
        if sh is None:   # zu wenig Material: in Zeitlupe strecken (wirkt bei Drohnenbildern ruhig und filmisch)
            for sp in (0.8, 0.65, 0.5):
                for m in cands:
                    sh = take(m, L, speed=sp)
                    if sh:
                        break
                if sh:
                    break
        if sh is None:   # Notfall: Wiederholung erlauben (sehr kurzer Einzel-Clip)
            m = cands[len(placed) % len(cands)]
            speed = max(0.5, min(1.0, m["dur"] / L))
            sh = Shot(m["clip"], m["start"], round(min(m["dur"], L * speed), 3), 0.0, L, round(speed, 3), m["score"],
                      m.get("hero", False), m.get("transit", False), m.get("direction", ""))
        placed[i] = sh
    t = 0.0
    for i in range(len(slots)):
        sh = placed[i]
        sh.t0 = round(cuts[i], 6)
        sh.dur = round(cuts[i + 1] - cuts[i], 6)
        shots.append(sh)
        t += sh.dur
    return shots


def _scene_of(shot: Shot, pool: list[dict]) -> int | None:
    for m in pool:
        if m["clip"] == shot.clip and m["start"] <= shot.src_in + 1e-3 and shot.src_in + shot.src_dur <= m["start"] + m["dur"] + 1e-3:
            return m.get("scene")
    return None
