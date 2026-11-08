"""Final rendern: aus Original + Schnittliste das fertige MP4 bauen.

- Schnittkanten werden auf ganze Bilder gerundet, damit Bild und Ton auch nach hunderten Schnitten synchron bleiben.
- Ton: an jeder Schnittkante 10 ms sanft aus- und eingeblendet (keine Knackser).
- Video: H.264, Qualität CRF 18 (bzw. Nvidia-Chip, wenn vorhanden), Ton AAC 192 kbit/s.
"""
from __future__ import annotations

import re
import time
from fractions import Fraction
from pathlib import Path
from typing import Callable

import numpy as np

from . import media
from .errors import UserError

SR = 48000
CH = 2
FADE = 0.010  # Sekunden

QUALITIES = {
    "1080": "1080p (empfohlen)",
    "2160": "4K (wenn das Original so groß ist)",
    "original": "Original-Auflösung",
}


def frame_rate(info: dict) -> Fraction:
    r = info.get("fps_rational")
    if r:
        num, _, den = r.partition("/")
        if int(den or 1):
            return Fraction(int(num), int(den or 1)).limit_denominator(1001)
    return Fraction(info.get("fps") or 30).limit_denominator(1001)


def snap(segments: list[list[float]], fps: Fraction, duration: float) -> list[tuple[int, int]]:
    """Segmente in ganze Bilder umrechnen: [(erstes Bild, Bild nach dem letzten), …], ohne Überlappung."""
    out: list[tuple[int, int]] = []
    last_frame = int(duration * fps)
    for s, e in segments:
        a = max(0, round(Fraction(s).limit_denominator(100000) * fps))
        b = min(last_frame, round(Fraction(e).limit_denominator(100000) * fps))
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        elif b > a:
            out.append((a, b))
    return out


def _scale_filter(info: dict, quality: str) -> str:
    w, h = info["width"], info["height"]
    short = min(w, h)
    target = {"1080": 1080, "2160": 2160}.get(quality)
    if target and short > target:
        return f"scale={target}:-2" if w < h else f"scale=-2:{target}"
    return "scale=trunc(iw/2)*2:trunc(ih/2)*2"


def _encoder() -> list[str]:
    if media.h264_encoder()[1] == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "19", "-b:v", "0", "-profile:v", "high"]
    return ["-c:v", "libx264", "-preset", "fast", "-crf", "18", "-profile:v", "high"]


def build_audio(src: Path, info: dict, frames: list[tuple[int, int]], fps: Fraction, work: Path) -> Path:
    """Schneidet den Ton exakt passend zu den Bildern und blendet an jeder Kante 10 ms weich."""
    raw = work / "ton_48k.pcm"
    if not raw.exists():
        if not info["has_audio"]:
            raise UserError("Das Video hat keine Tonspur.")
        tmp = raw.with_suffix(".tmp")
        r = media.run([media.ffmpeg(), "-hide_banner", "-y", "-i", str(src), "-map", f"0:{info['audio_index']}",
                       "-vn", "-ac", str(CH), "-ar", str(SR), "-f", "s16le", "-c:a", "pcm_s16le", str(tmp)])
        if r.returncode != 0:
            raise UserError("Der Ton konnte nicht gelesen werden: " + r.stderr[-300:])
        tmp.replace(raw)
    data = np.memmap(raw, dtype=np.int16, mode="r")
    total = len(data) // CH
    data = data[: total * CH].reshape(total, CH)

    out_path = work / "ton_schnitt.pcm"
    fade = int(FADE * SR)
    ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)[:, None]
    out_frames = 0
    out_samples = 0
    with open(out_path, "wb") as fh:
        for a, b in frames:
            out_frames += b - a
            target = round(out_frames / fps * SR)  # kumulativ → keine Verschiebung über viele Schnitte
            n = target - out_samples
            start = round(a / fps * SR)
            chunk = np.zeros((n, CH), dtype=np.float32)
            avail = max(0, min(n, total - start))
            if avail:
                chunk[:avail] = data[start:start + avail]
            if n > 2 * fade:
                chunk[:fade] *= ramp
                chunk[-fade:] *= ramp[::-1]
            fh.write(np.clip(chunk, -32768, 32767).astype(np.int16).tobytes())
            out_samples = target
    return out_path


def render(src: Path, info: dict, segments: list[list[float]], out: Path, work: Path, quality: str = "1080",
           progress: Callable[[float, str], None] | None = None) -> dict:
    report = progress or (lambda f, m: None)
    if quality not in QUALITIES:
        raise UserError("Unbekannte Qualität.")
    if not segments:
        raise UserError("Es ist nichts mehr übrig: Alle Wörter sind geschnitten.")
    work.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    fps = frame_rate(info)
    frames = snap(segments, fps, info["duration"])
    n_frames = sum(b - a for a, b in frames)
    new_duration = float(n_frames / fps)

    report(0.02, "Ton wird geschnitten …")
    audio = build_audio(src, info, frames, fps, work)

    h = 0.5 / float(fps)
    terms = "+".join(f"between(t\\,{float(Fraction(a) / fps) - h:.6f}\\,{float(Fraction(b) / fps) - h:.6f})"
                     for a, b in frames)
    fps_str = f"{fps.numerator}/{fps.denominator}"
    graph = (f"[0:{info['video_index']}]fps={fps_str},select='{terms}',setpts=N/({fps_str})/TB,"
             f"{_scale_filter(info, quality)},format=yuv420p[v]")
    script = work / "filter.txt"
    script.write_text(graph, encoding="utf-8")

    tmp = out.with_suffix(".tmp.mp4")
    args = ["-i", str(src), "-f", "s16le", "-ar", str(SR), "-ac", str(CH), "-i", str(audio),
            "-filter_complex_script", str(script), "-map", "[v]", "-map", "1:a",
            *_encoder(), "-r", fps_str, "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", "-map_metadata", "-1", "-shortest", str(tmp)]
    started = time.time()

    def on_video(f: float):
        el = time.time() - started
        rest = el / f * (1 - f) if f > 0.02 else None
        msg = f"Video wird berechnet ({f:.0%})" + (f", noch ca. {int(rest // 60)} Min {int(rest % 60)} s" if rest else "")
        report(0.05 + 0.95 * f, msg)

    media._run_with_progress(args, new_duration, on_video)
    tmp.replace(out)
    for f in ("ton_schnitt.pcm",):
        try:
            (work / f).unlink()
        except OSError:
            pass
    report(1.0, "Fertig gerendert")
    return {"file": out.name, "duration": round(new_duration, 2), "segments": len(frames),
            "size": out.stat().st_size, "quality": quality}


def safe_name(name: str) -> str:
    return re.sub(r"[^\w\-. ]+", "_", name).strip()[:60] or "video"
