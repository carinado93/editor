"""Musik-Bibliothek für den Drone Cutter.

Carina legt lizenzfreie Stücke (YouTube Audio Library, Pixabay Music …) in assets/music/.
Beim Einlesen bekommt jedes Stück automatisch BPM, Schläge, Länge, Energie und eine Stimmung
(calm / cinematic / epic / upbeat). Die Angaben stehen in assets/music/library.json und dürfen
von Hand geändert werden (z. B. "mood", "license").
Eigene hochgeladene Songs: Warnung wegen Content-ID (bekannte Songs können Ansprüche auslösen).
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np

from ..config import ROOT
from . import beats as beatmod

MUSIC_DIR = ROOT / "assets" / "music"
LIB = MUSIC_DIR / "library.json"
EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
MOODS = ["calm", "cinematic", "epic", "upbeat"]
CONTENT_ID_NOTE = ("Popular commercial songs can trigger YouTube/Instagram Content ID claims (muted audio or "
                   "blocked video). Use royalty-free music or music you have a licence for.")


def _guess_mood(bpm: float, energy: list[float]) -> str:
    e = np.array(energy or [0])
    loud = float(np.percentile(e, 80)) if e.size else 0
    dyn = float(np.percentile(e, 90) / (np.percentile(e, 20) + 1e-4)) if e.size else 1
    if bpm < 85 and loud < 0.12:
        return "calm"
    if bpm >= 118 and loud >= 0.12:
        return "upbeat"
    if dyn > 3.5 or loud > 0.18:
        return "epic"
    return "cinematic"


def library(scan: bool = True) -> list[dict]:
    """Alle Stücke (neue Dateien werden beim Aufruf analysiert und gespeichert)."""
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if LIB.exists():
        try:
            data = {d["file"]: d for d in json.loads(LIB.read_text(encoding="utf-8"))}
        except (OSError, ValueError, KeyError):
            data = {}
    changed = False
    if scan:
        files = {f.name for f in MUSIC_DIR.iterdir() if f.suffix.lower() in EXT}
        for name in sorted(files - set(data)):
            try:
                a = beatmod.analyse(MUSIC_DIR / name)
            except Exception:  # noqa: BLE001 – kaputte Datei überspringen
                continue
            data[name] = {"file": name, "title": Path(name).stem.replace("_", " "), "bpm": a["bpm"],
                          "duration": a["duration"], "mood": _guess_mood(a["bpm"], a["energy"]),
                          "beats": a["beats"], "energy": a["energy"], "license": "royalty-free (check source)",
                          "source": "library"}
            changed = True
        for name in set(data) - files:
            if data[name].get("source", "library") == "library":
                del data[name]
                changed = True
    if changed:
        LIB.write_text(json.dumps(list(data.values()), ensure_ascii=False, indent=1), encoding="utf-8")
    return sorted(data.values(), key=lambda d: d["title"].lower())


def pick(duration: float, mood: str | None = None, seed: int = 0, exclude: set[str] | None = None) -> dict | None:
    """Passendes Stück: gewünschte Stimmung, lang genug (sonst wird geloopt), bei mehreren zufällig per seed."""
    lib = [t for t in library() if t["file"] not in (exclude or set())] or library()
    if not lib:
        return None
    rnd = random.Random(seed)

    def score(t):
        s = 0.0
        if mood and t.get("mood") == mood:
            s += 2
        if t["duration"] >= duration:
            s += 1
        return s + rnd.random() * 0.5
    return max(lib, key=score)


def best_start(track: dict, duration: float) -> float:
    """Startstelle: auf einem Schlag, möglichst so, dass der Höhepunkt (lauteste Stelle) in die zweite Hälfte fällt
    und das Stück nicht mitten im Video endet. Kurze Stücke beginnen bei 0."""
    if track["duration"] <= duration + 1:
        return 0.0
    e = np.array(track.get("energy") or [0.0])
    bts = [b for b in track.get("beats", []) if b <= track["duration"] - duration]
    if not bts:
        return 0.0
    best, best_s = 0.0, -1e9
    for b in bts[:: max(1, len(bts) // 60)]:
        a, z = int(b), int(min(len(e), b + duration))
        if z - a < 2:
            continue
        seg = e[a:z]
        half = len(seg) // 2
        s = float(seg[half:].mean() - 0.3 * abs(seg[:2].mean() - seg.mean()) - 0.02 * b)
        if s > best_s:
            best, best_s = b, s
    return round(float(best), 3)


def beats_in_window(track: dict, start: float, duration: float) -> list[float]:
    """Schläge relativ zum Videoanfang (bei Loop werden sie wiederholt)."""
    bts = np.array(track.get("beats") or [])
    if bts.size == 0:
        period = 60.0 / max(40.0, track.get("bpm", 100))
        return list(np.arange(0, duration, period))
    out, offset = [], 0.0
    src_len = track["duration"]
    while offset - start < duration:
        for b in bts:
            t = b + offset - start
            if 0 <= t <= duration:
                out.append(round(float(t), 3))
        offset += src_len
        if src_len <= 0:
            break
    return sorted(set(out))


def audio_filter(track_path: Path, start: float, duration: float, gain_db: float = 0.0, fade_in: float = 0.6,
                 fade_out: float = 2.0, duck: tuple[float, float] | None = None, duck_db: float = -4.0,
                 loop: bool = True) -> tuple[list[str], str]:
    """(ffmpeg-Eingabe-Argumente, Filterkette für [m]) – kürzen/loopen, Blenden, Ducking unter dem Intro."""
    inp = (["-stream_loop", "-1"] if loop else []) + ["-ss", f"{start:.3f}", "-i", str(track_path)]
    chain = [f"atrim=0:{duration:.3f}", "asetpts=PTS-STARTPTS", "aformat=sample_rates=48000:channel_layouts=stereo"]
    if gain_db:
        chain.append(f"volume={gain_db:.2f}dB")
    if duck:
        a, b = duck
        lo = 10 ** (duck_db / 20)
        # weich absenken und am Ende des Titels über 0,8 s wieder anheben
        chain.append(f"volume='if(lt(t,{a:.2f}),1,if(lt(t,{b:.2f}),{lo:.4f},"
                     f"{lo:.4f}+(1-{lo:.4f})*min(1,(t-{b:.2f})/0.8)))':eval=frame")
    if fade_in:
        chain.append(f"afade=t=in:st=0:d={fade_in:.2f}")
    if fade_out:
        chain.append(f"afade=t=out:st={max(0.0, duration - fade_out):.2f}:d={fade_out:.2f}")
    return inp, ",".join(chain)

