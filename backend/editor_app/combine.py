"""Mehrere Videos zu einem verbinden (in Carinas Reihenfolge), dann wie ein YouTube-Projekt: selbst schneiden
(Transkript, Zeitbereiche) und Effekte darauf. Größe/Bildrate vom ersten Clip, Ton gleichmäßig;
Clips ohne Ton bekommen Stille, damit nichts verrutscht. Die Originale bleiben unverändert."""
from __future__ import annotations

import re
import shutil
import subprocess
import time
from fractions import Fraction
from pathlib import Path

from . import media, projects
from .config import ROOT
from .errors import UserError

DRAFTS = ROOT / "daten" / "kombi"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm", ".mts"}


def _draft(did: str) -> Path:
    if not re.fullmatch(r"[\w-]+", did or ""):
        raise UserError("Unknown draft.")
    return DRAFTS / did


def new_draft() -> str:
    did = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
    (DRAFTS / did).mkdir(parents=True, exist_ok=True)
    return did


def write_chunk(did: str, k: int, name: str, offset: int, data: bytes) -> int:
    ext = Path(name).suffix.lower() or ".mp4"
    if ext not in VIDEO_EXT:
        raise UserError(f"File type '{ext}' is not supported. Please use videos (e.g. MP4 or MOV).")
    f = _draft(did) / f"clip_{k:02d}{ext}"
    current = f.stat().st_size if f.exists() else 0
    if offset != current:
        return current  # Browser macht an der richtigen Stelle weiter
    with open(f, "ab") as fh:
        fh.write(data)
    return current + len(data)


def _even(x: float) -> int:
    return max(2, int(round(x / 2)) * 2)


# Übergänge zwischen zwei Clips: (xfade-Art, Dauer in s, Effekt an der Nahtstelle)
TRANSITIONS = {
    "cut": (None, 0.0, None),          # harter Schnitt
    "fade": ("fade", 0.6, None),       # weich überblenden
    "smoke": ("dissolve", 0.9, "poof"),  # erscheinen/verschwinden im Rauch (leerer Raum ↔ Carina, Stativ)
    "cover": ("fade", 0.12, None),     # Glas/Hand vor der Linse: genau im abgedeckten Moment schneiden
    "flash": ("fadewhite", 0.45, None),
    "zoom": ("zoomin", 0.5, None),
    "whip": ("smoothleft", 0.35, "whip"),
}
TRANSITION_LABELS = {"cut": "Cut", "fade": "Soft fade", "smoke": "Appear / disappear in smoke",
                     "cover": "Cover transition (glass/hand in front of the lens)", "flash": "Flash",
                     "zoom": "Zoom", "whip": "Whip"}


def _detail_curve(path: Path, start: float, length: float) -> list[tuple[float, float]]:
    """Wie viel Bild-Detail (Kanten) jedes Bild hat – abgedeckte Linse = sehr wenig Detail."""
    import numpy as np
    r = subprocess.run([media.ffmpeg(), "-hide_banner", "-loglevel", "error", "-ss", f"{max(0.0, start):.3f}",
                        "-t", f"{length:.3f}", "-i", str(path), "-vf", "fps=15,scale=96:96,format=gray",
                        "-f", "rawvideo", "-"], capture_output=True, creationflags=media._NO_WINDOW)
    raw = np.frombuffer(r.stdout, dtype=np.uint8)
    n = len(raw) // (96 * 96)
    out = []
    for k in range(n):
        f = raw[k * 9216:(k + 1) * 9216].reshape(96, 96).astype(np.float32)
        detail = float(np.abs(np.diff(f, axis=0)).mean() + np.abs(np.diff(f, axis=1)).mean())
        out.append((max(0.0, start) + k / 15, detail))
    return out


def find_cover(path: Path, duration: float, at_end: bool) -> float:
    """Zeitpunkt, an dem etwas die Linse abdeckt (am Ende von Clip A bzw. am Anfang von Clip B)."""
    win = min(4.0, duration)
    curve = _detail_curve(path, duration - win if at_end else 0.0, win)
    if not curve:
        return duration if at_end else 0.0
    vals = sorted(x[1] for x in curve)
    lo, med = vals[0], vals[len(vals) // 2]
    thr = lo + 0.15 * max(0.0, med - lo)  # "so gut wie ganz abgedeckt"
    k = min(range(len(curve)), key=lambda i: curve[i][1])
    if at_end:  # Clip A: der erste ganz abgedeckte Moment
        while k > 0 and curve[k - 1][1] <= thr:
            k -= 1
    else:  # Clip B: der letzte abgedeckte Moment, bevor das Glas/die Hand wieder weggeht
        while k + 1 < len(curve) and curve[k + 1][1] <= thr:
            k += 1
    return round(curve[k][0], 3)


def build(did: str, name: str, manual: bool, language: str, model: str, transitions: list[str] | None = None,
          progress=None) -> dict:
    """Clips verbinden (mit Übergängen) → neues YouTube-Projekt (Schneiden + Effekte) und verarbeiten lassen."""
    from . import jobs, render

    d = _draft(did)
    clips = sorted(p for p in d.iterdir() if p.name.startswith("clip_") and p.suffix.lower() in VIDEO_EXT)
    if len(clips) < 2:
        raise UserError("Please add at least 2 videos.")
    infos = [media.probe(c) for c in clips]
    trans = [(t if t in TRANSITIONS else "cut") for t in (transitions or [])] + ["cut"] * len(clips)
    first = infos[0]
    W, H = _even(first["width"]), _even(first["height"])
    fps = render.frame_rate(first)
    if fps > 60:
        fps = Fraction(60)
    fps_s = f"{fps.numerator}/{fps.denominator}"
    # Abdeck-Übergang: Clip A endet und Clip B beginnt genau im abgedeckten Moment
    trims = [[0.0, info["duration"]] for info in infos]
    for k in range(len(clips) - 1):
        if trans[k] == "cover":
            trims[k][1] = max(trims[k][0] + 0.5, find_cover(clips[k], infos[k]["duration"], at_end=True))
            trims[k + 1][0] = min(trims[k + 1][1] - 0.5, find_cover(clips[k + 1], infos[k + 1]["duration"], at_end=False))
    args, parts, n_in = [], [], 0
    for k, (c, info) in enumerate(zip(clips, infos)):
        a0, a1 = trims[k]
        args += ["-i", str(c)]
        vi = n_in
        n_in += 1
        if info.get("has_audio"):
            ai = f"{vi}:a:0"
        else:  # Stille in passender Länge
            args += ["-f", "lavfi", "-t", f"{info['duration']:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
            ai = f"{n_in}:a"
            n_in += 1
        parts.append(f"[{vi}:v:0]trim={a0:.3f}:{a1:.3f},setpts=PTS-STARTPTS,{media.sdr_filter(info)}"
                     f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
                     f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={fps_s},format=yuv420p[v{k}];"
                     f"[{ai}]atrim={a0:.3f}:{a1:.3f},asetpts=PTS-STARTPTS,aresample=48000,"
                     f"aformat=channel_layouts=stereo[a{k}]")
    # nacheinander zusammensetzen: harter Schnitt = concat, sonst xfade + acrossfade
    lens = [b - a for a, b in trims]
    cur_v, cur_a, cur_len = "v0", "a0", lens[0]
    starts, auto_fx = [0.0], []
    for k in range(1, len(clips)):
        kind, dur, fx_type = TRANSITIONS[trans[k - 1]]
        dur = min(dur, lens[k - 1] / 2, lens[k] / 2)
        nv, na = f"vx{k}", f"ax{k}"
        if not kind or dur < 0.05:
            parts.append(f"[{cur_v}][{cur_a}][v{k}][a{k}]concat=n=2:v=1:a=1[{nv}][{na}]")
            seam = cur_len
            cur_len += lens[k]
        else:
            off = cur_len - dur
            parts.append(f"[{cur_v}][v{k}]xfade=transition={kind}:duration={dur:.3f}:offset={off:.3f}[{nv}]")
            parts.append(f"[{cur_a}][a{k}]acrossfade=d={dur:.3f}[{na}]")
            seam = off + dur / 2
            cur_len += lens[k] - dur
        starts.append(round(seam, 3))
        if fx_type:  # Rauchwolke bzw. Zoom-Unschärfe genau an der Nahtstelle
            span = 1.2 if fx_type == "poof" else 0.6
            auto_fx.append({"type": fx_type, "start": round(max(0.0, seam - span / 2), 2),
                            "end": round(seam + span / 2, 2)})
        cur_v, cur_a = nv, na
    parts.append(f"[{cur_v}]format=yuv420p[vout]")  # nach Überblendungen wieder ins übliche Bildformat
    cur_v = "vout"
    graph = ";".join(parts)
    script = d / "filter.txt"
    script.write_text(graph, encoding="utf-8")
    out = d / "verbunden.mp4"
    if progress:
        progress("Joining your videos …")
    cmd = [*args, *media.filter_script_args(script), "-map", f"[{cur_v}]", "-map", f"[{cur_a}]", *render._encoder(),
           *media.SDR_TAGS, "-fps_mode", "cfr", "-r", fps_s, "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-map_metadata", "-1", "-movflags", "+faststart", str(out)]
    media._run_with_progress(cmd, cur_len, None)
    p = projects.create(name.strip() or "Combined video", "youtube", "verbunden.mp4", out.stat().st_size,
                        {"model": model or "auto", "language": language if language in ("de", "en", "auto") else "auto"})
    pid = p["id"]
    shutil.move(str(out), projects.path(pid, p["original_file"]))
    projects.update(pid, uploaded=p["size"], manual_cut=bool(manual), auto_fx=auto_fx,
                    clip_starts=[{"n": k + 1, "t": s_, "name": f"Video {k + 1}"} for k, s_ in enumerate(starts)],
                    transitions=trans[:len(clips) - 1])
    shutil.rmtree(d, ignore_errors=True)
    jobs.enqueue(pid)
    return projects.load(pid)


PLAN_SCHEMA = {"type": "object", "properties": {"transitions": {"type": "array", "items": {
    "type": "string", "enum": list(TRANSITIONS)}}, "note": {"type": "string"}},
    "required": ["transitions", "note"], "additionalProperties": False}


def plan_transitions(description: str, names: list[str], engine: str = "claude") -> dict:
    """Carinas Beschreibung ("ich erscheine im Rauch", "Glas vor der Kamera, dann anderes Outfit") → Übergänge."""
    n = max(1, len(names) - 1)
    listing = "\n".join(f"{k + 1}. {nm}" for k, nm in enumerate(names))
    menu = "\n".join(f"- {k}: {v}" for k, v in TRANSITION_LABELS.items())
    prompt = f"""Carina verbindet diese Videos in dieser Reihenfolge:
{listing}

Sie beschreibt, was passieren soll: "{description.strip()}"

Wähle für jede der {n} Nahtstellen (zwischen Video 1 und 2, 2 und 3, …) genau einen Übergang:
{menu}
Hinweise: "erscheinen/verschwinden/auftauchen/weg" → smoke (Stativ: leerer Raum + sie im Raum).
Etwas vor die Kamera halten (Glas, Hand, Jacke), neues Outfit, Szenenwechsel durch Abdecken → cover.
note: ein kurzer Satz auf Englisch, was du gewählt hast und was sie beim Filmen beachten muss.
Antworte NUR mit JSON nach dem Schema."""
    if engine == "claude":
        from . import claude
        raw = claude.ask_json(prompt, PLAN_SCHEMA, effort="low")
    else:
        from . import llm
        raw = llm.ask_json(prompt, "Du antwortest ausschließlich mit gültigem JSON.", timeout=300)
    tr = [t if t in TRANSITIONS else "cut" for t in (raw.get("transitions") or [])][:n]
    tr += ["cut"] * (n - len(tr))
    return {"transitions": tr, "note": str(raw.get("note", "")).strip()}
