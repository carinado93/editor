"""Tempo-Kurven (Speed Ramps) für Aufnahmen.

Eine Kurve gibt das Tempo über die AUSGABE-Zeit einer Aufnahme an (u = 0..1): 1.0 = normal, 0.4 = Zeitlupe.
Beispiel "hero": normal → weich auf 40 % (Zeitlupe auf dem schönsten Moment) → zurück auf normal.
Fürs Rendern wird die Kurve in kurze Stücke mit festem Tempo zerlegt (ffmpeg setpts je Stück).
"""
from __future__ import annotations

import numpy as np

RAMPS: dict[str, list[tuple[float, float]]] = {
    "hero": [(0.0, 1.0), (0.2, 1.0), (0.38, 0.4), (0.72, 0.4), (0.9, 1.0), (1.0, 1.0)],
    "montage": [(0.0, 1.0), (0.3, 1.0), (0.45, 0.5), (0.6, 0.5), (0.75, 1.6), (1.0, 1.6)],
    "bullet": [(0.0, 1.0), (0.3, 1.0), (0.4, 0.25), (0.8, 0.25), (0.9, 1.0), (1.0, 1.0)],
    "flash_in": [(0.0, 3.0), (0.3, 1.0), (1.0, 1.0)],
    "flash_out": [(0.0, 1.0), (0.7, 1.0), (1.0, 3.0)],
}
LABELS = {"hero": "Hero (slow motion in the middle)", "montage": "Montage", "bullet": "Bullet (very slow)",
          "flash_in": "Flash in", "flash_out": "Flash out"}


def _smooth(x: np.ndarray) -> np.ndarray:
    return x * x * (3 - 2 * x)


def curve(ramp: str | None, speed: float = 1.0, n: int = 200) -> tuple[np.ndarray, np.ndarray]:
    """(u, Tempo) mit weichen Übergängen (ease in/out zwischen den Punkten)."""
    u = np.linspace(0, 1, n)
    pts = RAMPS.get(ramp or "", None)
    if not pts:
        return u, np.full(n, float(speed))
    xs, ys = zip(*pts)
    out = np.empty(n)
    for i, x in enumerate(u):
        k = max(0, min(len(xs) - 2, int(np.searchsorted(xs, x, side="right") - 1)))
        a, b = xs[k], xs[k + 1]
        f = 0 if b <= a else (x - a) / (b - a)
        out[i] = ys[k] + (ys[k + 1] - ys[k]) * _smooth(np.clip(f, 0, 1))
    return u, out * float(speed)


def mean_speed(ramp: str | None, speed: float = 1.0) -> float:
    u, s = curve(ramp, speed)
    return float(np.trapezoid(s, u) if hasattr(np, "trapezoid") else np.trapz(s, u))


def end_speeds(ramp: str | None, speed: float = 1.0) -> tuple[float, float]:
    _, s = curve(ramp, speed)
    return float(s[0]), float(s[-1])


def pieces(ramp: str | None, speed: float, dur: float, k: int = 12) -> list[tuple[float, float]]:
    """Zerlegung in k Stücke: [(Ausgabe-Länge, Tempo)], Summe der Längen = dur."""
    if not RAMPS.get(ramp or ""):
        return [(dur, float(speed))]
    u, s = curve(ramp, speed, 600)
    edges = np.linspace(0, 1, k + 1)
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (u >= a) & (u <= b)
        out.append(((b - a) * dur, float(s[m].mean())))
    return out
