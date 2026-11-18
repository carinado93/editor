"""Takt-Erkennung der Musik (BPM + Schlagzeitpunkte), nur mit numpy.

Warum nicht librosa? librosa braucht numba/llvmlite, das mit der neuen numpy-Version unter Windows oft
nicht passt. Das Verfahren hier ist das klassische: Spektral-Fluss (Onset-Stärke) → Tempo per
Autokorrelation (60–180 BPM, leichte Vorliebe um 100–120) → Schlagfolge per dynamischer Programmierung
(Ellis 2007, wie librosa.beat.beat_track).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from .. import media

SR = 22050
HOP = 512


def load_mono(path: Path, sr: int = SR, start: float = 0.0, dur: float | None = None) -> np.ndarray:
    cmd = [media.ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(path)]
    if dur:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True, creationflags=getattr(media, "_NO_WINDOW", 0))
    if r.returncode != 0:
        raise RuntimeError("Could not read the music: " + r.stderr.decode("utf-8", "replace")[-300:])
    return np.frombuffer(r.stdout, np.float32).copy()


def onset_envelope(y: np.ndarray, sr: int = SR, hop: int = HOP) -> np.ndarray:
    n_fft = 2048
    if y.size < n_fft:
        return np.zeros(1, np.float32)
    win = np.hanning(n_fft).astype(np.float32)
    n = 1 + (y.size - n_fft) // hop
    idx = np.arange(n_fft)[None, :] + hop * np.arange(n)[:, None]
    spec = np.abs(np.fft.rfft(y[idx] * win, axis=1))
    # Mel-ähnlich: nur bis ~8 kHz, log-Kompression
    spec = np.log1p(100 * spec[:, : int(8000 / (sr / n_fft))])
    flux = np.maximum(0, np.diff(spec, axis=0)).mean(axis=1)
    flux = np.concatenate([[0], flux])
    flux -= np.convolve(flux, np.ones(16) / 16, mode="same")   # lokalen Mittelwert abziehen
    flux = np.maximum(flux, 0)
    return (flux / (flux.max() + 1e-9)).astype(np.float32)


def tempo(env: np.ndarray, sr: int = SR, hop: int = HOP) -> float:
    fps = sr / hop
    env = env - env.mean()
    ac = np.correlate(env, env, mode="full")[env.size - 1:]
    lags = np.arange(ac.size)
    bpm = np.where(lags > 0, 60.0 * fps / np.maximum(lags, 1), 0)
    ok = (bpm >= 60) & (bpm <= 180)
    if not ok.any():
        return 100.0
    # Vorliebe für "normale" Tempi (log-normal um 110 BPM)
    w = np.exp(-0.5 * (np.log2(np.maximum(bpm, 1) / 110.0) / 0.9) ** 2)
    score = np.where(ok, ac * w, -np.inf)
    lag = int(np.argmax(score))
    return float(60.0 * fps / lag)


def track(env: np.ndarray, bpm: float, sr: int = SR, hop: int = HOP, tightness: float = 100.0) -> np.ndarray:
    """Schlagzeitpunkte (Sekunden) per dynamischer Programmierung."""
    fps = sr / hop
    period = 60.0 * fps / bpm
    n = env.size
    if n < 4:
        return np.zeros(0)
    score = env.astype(np.float64).copy()
    back = np.full(n, -1)
    lo, hi = int(round(period * 0.5)), int(round(period * 2))
    prev_offsets = np.arange(-hi, -lo + 1)
    penalty = -tightness * np.log(-prev_offsets / period) ** 2
    for i in range(n):
        cand = i + prev_offsets
        m = cand >= 0
        if not m.any():
            continue
        vals = score[cand[m]] + penalty[m]
        j = int(np.argmax(vals))
        if vals[j] > 0:
            score[i] = env[i] + vals[j]
            back[i] = cand[m][j]
    # Ende: höchster Wert in der letzten Periode
    tail = max(0, n - int(period) - 1)
    i = tail + int(np.argmax(score[tail:]))
    beats = []
    while i >= 0:
        beats.append(i)
        i = back[i]
    beats = np.array(beats[::-1], dtype=np.float64)
    # Das Analysefenster (2048) "sieht" einen Schlag schon, bevor er in seiner Mitte liegt → Versatz ausgleichen
    return beats / fps + 0.75 * 2048 / sr


def analyse(path: Path, max_seconds: float = 600) -> dict:
    y = load_mono(path, dur=max_seconds)
    env = onset_envelope(y)
    bpm = tempo(env)
    beats = track(env, bpm)
    if beats.size > 8:   # genaueres Tempo aus der Schlagfolge (Lineare Regression statt ganzzahliger Verzögerung)
        k = np.arange(beats.size)
        bpm = 60.0 / float(np.polyfit(k, beats, 1)[0])
    # Energie pro Sekunde (für "ruhig/episch" und für die Wahl der Startstelle)
    sec = max(1, y.size // SR)
    rms = np.sqrt(np.mean(y[: sec * SR].reshape(sec, SR) ** 2, axis=1)) if y.size >= SR else np.zeros(1)
    return {"bpm": round(bpm, 2), "beats": [round(float(b), 3) for b in beats], "duration": round(y.size / SR, 3),
            "energy": [round(float(e), 4) for e in rms]}
