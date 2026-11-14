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


def build(did: str, name: str, manual: bool, language: str, model: str, progress=None) -> dict:
    """Clips verbinden → neues YouTube-Projekt (Schneiden + Effekte) und verarbeiten lassen."""
    from . import jobs, render

    d = _draft(did)
    clips = sorted(p for p in d.iterdir() if p.name.startswith("clip_") and p.suffix.lower() in VIDEO_EXT)
    if len(clips) < 2:
        raise UserError("Please add at least 2 videos.")
    infos = [media.probe(c) for c in clips]
    first = infos[0]
    W, H = _even(first["width"]), _even(first["height"])
    fps = render.frame_rate(first)
    if fps > 60:
        fps = Fraction(60)
    fps_s = f"{fps.numerator}/{fps.denominator}"
    args, parts, n_in = [], [], 0
    starts, t = [], 0.0
    for c, info in zip(clips, infos):
        args += ["-i", str(c)]
        vi = n_in
        n_in += 1
        if info.get("has_audio"):
            ai = f"{vi}:a:0"
        else:  # Stille in passender Länge
            args += ["-f", "lavfi", "-t", f"{info['duration']:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
            ai = f"{n_in}:a"
            n_in += 1
        k = len(starts)
        parts.append(f"[{vi}:v:0]scale={W}:{H}:force_original_aspect_ratio=decrease,"
                     f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={fps_s},format=yuv420p[v{k}];"
                     f"[{ai}]aresample=48000,aformat=channel_layouts=stereo,"
                     f"atrim=0:{info['duration']:.3f},asetpts=PTS-STARTPTS[a{k}]")
        starts.append(round(t, 3))
        t += info["duration"]
    n = len(clips)
    graph = ";".join(parts) + ";" + "".join(f"[v{k}][a{k}]" for k in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
    script = d / "filter.txt"
    script.write_text(graph, encoding="utf-8")
    out = d / "verbunden.mp4"
    if progress:
        progress("Joining your videos …")
    cmd = [*args, *media.filter_script_args(script), "-map", "[v]", "-map", "[a]", *render._encoder(),
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    media._run_with_progress(cmd, t, None)
    p = projects.create(name.strip() or "Combined video", "youtube", "verbunden.mp4", out.stat().st_size,
                        {"model": model or "auto", "language": language if language in ("de", "en", "auto") else "auto"})
    pid = p["id"]
    shutil.move(str(out), projects.path(pid, p["original_file"]))
    projects.update(pid, uploaded=p["size"], manual_cut=bool(manual),
                    clip_starts=[{"n": k + 1, "t": s, "name": f"Video {k + 1}"} for k, s in enumerate(starts)])
    shutil.rmtree(d, ignore_errors=True)
    jobs.enqueue(pid)
    return projects.load(pid)
