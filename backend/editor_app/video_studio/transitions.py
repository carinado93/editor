"""Übergänge zwischen Aufnahmen (Schritt 4: 10 Grund-Übergänge + Automatik).

Jeder Übergang = ffmpeg xfade-Art + Standarddauer + Familie. Im Export: xfade-Kette. Der Schnittpunkt bleibt
auf dem Takt: der Übergang liegt mittig um den Schnitt (halbe Dauer davor, halbe danach).

Automatik (Explore-the-World-Stil):
  * Reel: meist harte Schnitte auf dem Takt; etwa jeder dritte Schnitt bekommt einen Übergang:
    gleiche Bewegungsrichtung beider Aufnahmen → Wisch in diese Richtung (Match-Cut),
    nächste Aufnahme ist ein Helden-Moment → Zoom, sonst kurze Überblendung.
  * YouTube: ruhige Überblendungen, vor der letzten Aufnahme Abblende über Schwarz.
"""
from __future__ import annotations

import random

TRANSITIONS: dict[str, dict] = {
    "cut": {"xfade": None, "dur": 0.0, "family": "simple", "label": "Hard cut"},
    "dissolve": {"xfade": "fade", "dur": 0.6, "family": "simple", "label": "Dissolve"},
    "fade_black": {"xfade": "fadeblack", "dur": 0.8, "family": "simple", "label": "Dip to black"},
    "flash": {"xfade": "fadewhite", "dur": 0.4, "family": "light", "label": "Flash"},
    "swipe_left": {"xfade": "smoothleft", "dur": 0.4, "family": "slide", "label": "Swipe left"},
    "swipe_right": {"xfade": "smoothright", "dur": 0.4, "family": "slide", "label": "Swipe right"},
    "swipe_up": {"xfade": "smoothup", "dur": 0.4, "family": "slide", "label": "Swipe up"},
    "swipe_down": {"xfade": "smoothdown", "dur": 0.4, "family": "slide", "label": "Swipe down"},
    "zoom_in": {"xfade": "zoomin", "dur": 0.5, "family": "camera", "label": "Zoom in"},
    "blur": {"xfade": "hblur", "dur": 0.5, "family": "blur", "label": "Blur"},
    "circle": {"xfade": "circleopen", "dur": 0.6, "family": "mask", "label": "Circle reveal"},
    # Schritt 8: erweiterte Bibliothek
    "circle_close": {"xfade": "circleclose", "dur": 0.6, "family": "mask", "label": "Circle close"},
    "wipe_left": {"xfade": "wipeleft", "dur": 0.5, "family": "simple", "label": "Wipe left"},
    "wipe_right": {"xfade": "wiperight", "dur": 0.5, "family": "simple", "label": "Wipe right"},
    "slide_left": {"xfade": "slideleft", "dur": 0.5, "family": "slide", "label": "Slide left"},
    "slide_up": {"xfade": "slideup", "dur": 0.5, "family": "slide", "label": "Slide up"},
    "open_horizontal": {"xfade": "horzopen", "dur": 0.6, "family": "mask", "label": "Open (horizontal)"},
    "open_vertical": {"xfade": "vertopen", "dur": 0.6, "family": "mask", "label": "Open (vertical)"},
    "diagonal": {"xfade": "diagtl", "dur": 0.6, "family": "mask", "label": "Diagonal"},
    "radial": {"xfade": "radial", "dur": 0.6, "family": "mask", "label": "Radial (clock)"},
    "pixelize": {"xfade": "pixelize", "dur": 0.6, "family": "glitch", "label": "Pixelize"},
    "fade_grays": {"xfade": "fadegrays", "dur": 0.8, "family": "light", "label": "Fade through grey"},
    "squeeze": {"xfade": "squeezeh", "dur": 0.5, "family": "distortion", "label": "Squeeze"},
    "distance": {"xfade": "distance", "dur": 0.6, "family": "distortion", "label": "Distance (melt)"},
}
# Bewegungsrichtung der Kamera → Wisch in dieselbe Richtung (Inhalt wandert mit)
MATCH = {"left": "swipe_right", "right": "swipe_left", "up": "swipe_down", "down": "swipe_up", "in": "zoom_in"}


def auto(shots: list[dict], mode: str, seed: int = 0, dur_scale: float = 1.0) -> list[dict]:
    """Übergang nach jeder Aufnahme außer der letzten: [{"id", "dur"}]."""
    rnd = random.Random(seed + 7)
    out = []
    n = len(shots)
    for k in range(n - 1):
        a, b = shots[k], shots[k + 1]
        if mode == "youtube":
            tid = "fade_black" if k == n - 2 and n > 3 else "dissolve"
            d = 1.8 if tid == "dissolve" else 1.5   # lange, weiche Überblendung wie in der Referenz
        else:
            every = 3 if n > 5 else 2
            if (k + rnd.randint(0, 1)) % every != every - 1:
                tid = "cut"
            elif a.get("direction") and a.get("direction") == b.get("direction") and a["direction"] in MATCH:
                tid = MATCH[a["direction"]]
            elif b.get("hero"):
                tid = "zoom_in"
            else:
                tid = "dissolve"
            d = TRANSITIONS[tid]["dur"]
        d = min(d * dur_scale, 0.45 * min(a["dur"], b["dur"]))   # nie mehr als knapp die Hälfte einer Aufnahme
        out.append({"id": tid, "dur": round(d if tid != "cut" else 0.0, 3)})
    return out


def fixed(shots: list[dict], tid: str, dur: float | None = None) -> list[dict]:
    t = TRANSITIONS.get(tid, TRANSITIONS["cut"])
    out = []
    for a, b in zip(shots[:-1], shots[1:]):
        d = 0.0 if tid == "cut" else min(dur or t["dur"], 0.45 * min(a["dur"], b["dur"]))
        out.append({"id": tid if tid in TRANSITIONS else "cut", "dur": round(d, 3)})
    return out


def choose(shots: list[dict], mode: str, setting: str = "auto", dur: float | None = None, seed: int = 0) -> list[dict]:
    if setting == "auto":
        return auto(shots, mode, seed, (dur / 0.6) if dur else 1.0)
    return fixed(shots, setting, dur)
