"""Alles rund um ffmpeg: Video-Infos lesen, Ton herausziehen, Vorschau-Video erstellen.

Das Original wird nie verändert. Es wird nur gelesen.
"""
from __future__ import annotations

import functools
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from .config import PROXY_HEIGHT, TOOLS_DIR
from .errors import UserError

Progress = Callable[[float], None]  # Wert von 0.0 bis 1.0

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0  # kein schwarzes Fenster unter Windows


def _find(name: str) -> str:
    exe = name + (".exe" if sys.platform == "win32" else "")
    candidates = [TOOLS_DIR / "ffmpeg" / "bin" / exe]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "Microsoft" / "WinGet" / "Links" / exe)
    for c in candidates:
        if c.is_file():
            return str(c)
    found = shutil.which(name)
    if found:
        return found
    raise UserError(f"The program {name} is missing. Please start the app with 'start.bat', it installs it automatically.")


@functools.cache
def ffmpeg() -> str:
    return _find("ffmpeg")


@functools.cache
def ffprobe() -> str:
    return _find("ffprobe")


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          creationflags=_NO_WINDOW)


def probe(path: Path) -> dict:
    """Liest Länge, Auflösung, Bildrate usw. aus der Videodatei."""
    r = run([ffprobe(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    if r.returncode != 0:
        raise UserError("The file could not be read. Is it really a video? " + r.stderr[-300:])
    data = json.loads(r.stdout)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"
                  and s.get("disposition", {}).get("attached_pic") != 1 and s.get("codec_name") != "mjpeg"), None)
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if video is None:
        raise UserError("No video was found in the file.")
    num, _, den = (video.get("avg_frame_rate") or video.get("r_frame_rate") or "30/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 30.0
    width, height = int(video.get("width", 0)), int(video.get("height", 0))
    rotation = 0
    for sd in video.get("side_data_list", []) or []:
        if "rotation" in sd:
            rotation = int(sd["rotation"])
    if abs(rotation) in (90, 270):
        width, height = height, width
    return {
        "duration": float(data["format"].get("duration") or video.get("duration") or 0),
        "size": int(data["format"].get("size") or 0),
        "width": width,
        "height": height,
        "fps": round(fps, 3),
        "fps_rational": video.get("avg_frame_rate") or video.get("r_frame_rate"),
        "video_codec": video.get("codec_name"),
        "video_index": int(video["index"]),
        "has_audio": audio is not None,
        "audio_index": int(audio["index"]) if audio else None,
        "audio_codec": audio.get("codec_name") if audio else None,
        "sample_rate": int(audio.get("sample_rate", 0)) if audio else None,
    }


_TIME = re.compile(r"out_time_us=(\d+)")


# ---------------------------------------------------------------- Abbrechen
import threading as _threading

_job = _threading.local()       # welcher Auftrag läuft in diesem Arbeits-Thread
CANCEL: set[str] = set()        # Aufträge, die abgebrochen werden sollen


class Cancelled(Exception):
    """Carina hat auf "Cancel" gedrückt."""


def set_job(key: str | None) -> None:
    _job.key = key


def cancelled() -> bool:
    key = getattr(_job, "key", None)
    return key is not None and key in CANCEL


def check_cancel() -> None:
    if cancelled():
        raise Cancelled()


def _run_with_progress(args: list[str], duration: float, progress: Progress | None) -> None:
    """Startet ffmpeg und meldet den Fortschritt."""
    import collections
    import threading

    cmd = [ffmpeg(), "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-progress", "pipe:1", "-nostats",
           *args]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace", creationflags=_NO_WINDOW)
    assert proc.stdout is not None
    # Fehlermeldungen laufend mitlesen: sonst läuft unter Windows der kleine Puffer voll und ffmpeg bleibt
    # für immer stehen (Video hängt bei "Vorschau-Video wird erstellt" / "Rendern")
    tail: collections.deque = collections.deque(maxlen=60)

    def drain():
        for ln in proc.stderr:  # type: ignore[union-attr]
            tail.append(ln)

    t = threading.Thread(target=drain, daemon=True)
    t.start()
    try:
        for line in proc.stdout:
            if cancelled():
                raise Cancelled()
            m = _TIME.match(line.strip())
            if m and progress and duration > 0:
                progress(min(1.0, int(m.group(1)) / 1e6 / duration))
    except BaseException:
        proc.kill()  # abgebrochen oder Fehler: ffmpeg sofort beenden, nicht weiterlaufen lassen
        proc.wait()
        raise
    t.join(timeout=10)
    err = "".join(tail)
    if proc.wait() != 0:
        raise UserError("ffmpeg ran into a problem: " + err[-500:])
    if progress:
        progress(1.0)


@functools.cache
def ffmpeg_major() -> int:
    r = run([ffmpeg(), "-hide_banner", "-version"])
    m = re.search(r"ffmpeg version n?(\d+)", r.stdout)
    return int(m.group(1)) if m else 0


def filter_script_args(script: Path) -> list[str]:
    """Filter aus Datei lesen. ffmpeg 7+: "-/filter_complex datei", ältere Versionen: "-filter_complex_script"."""
    major = ffmpeg_major()
    if major == 0:  # unbekannte Version (z. B. Entwicklerversion "N-12345"): neue Schreibweise testen
        test = run([ffmpeg(), "-hide_banner", "-h", "full"])
        major = 6 if "filter_complex_script" in test.stdout else 7
    return ["-/filter_complex", str(script)] if major >= 7 else ["-filter_complex_script", str(script)]


@functools.cache
def h264_encoder() -> list[str]:
    """Nimmt den Video-Chip der Nvidia-Grafikkarte (viel schneller), wenn er da ist, sonst den Prozessor."""
    test = run([ffmpeg(), "-hide_banner", "-f", "lavfi", "-i", "color=black:s=256x256:d=0.1",
                "-c:v", "h264_nvenc", "-f", "null", "-"])
    if test.returncode == 0:
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "30"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "28"]


def make_proxy(src: Path, dst: Path, info: dict, progress: Progress | None = None) -> None:
    """Kleines Vorschau-Video (540p, H.264) zum flüssigen Abspielen im Browser.

    Ein Schlüsselbild pro Sekunde, damit Springen im Player sofort geht.
    """
    w, h = info["width"], info["height"]
    if w >= h:  # Querformat: Höhe 540
        scale = f"scale=-2:{min(PROXY_HEIGHT, h)}"
    else:       # Hochformat: Breite 540
        scale = f"scale={min(PROXY_HEIGHT, w)}:-2"
    fps = min(30.0, info["fps"] or 30.0)
    tmp = dst.with_suffix(".tmp.mp4")
    # Mit Nvidia-Karte auch das Entpacken (HEVC/4K von DJI und Handy) auf der Grafikkarte
    hw = ["-hwaccel", "auto"] if h264_encoder()[1] == "h264_nvenc" else []
    args = [*hw, "-i", str(src), "-map", f"0:{info['video_index']}"]
    if info["has_audio"]:
        args += ["-map", f"0:{info['audio_index']}"]
    args += ["-vf", f"{scale},fps={fps:g},format=yuv420p", *h264_encoder(), "-g", str(round(fps)),
             "-c:a", "aac", "-b:a", "96k", "-ac", "2", "-movflags", "+faststart", "-map_metadata", "-1",
             "-dn", "-sn", str(tmp)]
    try:
        _run_with_progress(args, info["duration"], progress)
    except UserError:
        if not hw:
            raise
        _run_with_progress(args[len(hw):], info["duration"], progress)  # nochmal ohne Grafikkarte
    tmp.replace(dst)


def extract_audio(src: Path, dst: Path, info: dict, progress: Progress | None = None) -> None:
    """Tonspur als 16-kHz-Mono-WAV (das Format, das die Spracherkennung braucht)."""
    if not info["has_audio"]:
        raise UserError("The video has no audio track. Without sound no transcript can be made.")
    tmp = dst.with_suffix(".tmp.wav")
    _run_with_progress(["-i", str(src), "-map", f"0:{info['audio_index']}", "-vn", "-ac", "1", "-ar", "16000",
                        "-c:a", "pcm_s16le", str(tmp)], info["duration"], progress)
    tmp.replace(dst)


def thumbnail(src: Path, dst: Path, at: float) -> None:
    r = run([ffmpeg(), "-hide_banner", "-y", "-ss", f"{at:.2f}", "-i", str(src), "-frames:v", "1",
             "-vf", "scale=360:-2", "-q:v", "4", str(dst)])
    if r.returncode != 0:
        raise UserError("The preview image could not be created.")


def stills_base64(video: Path, duration: float, n: int = 5, width: int = 512) -> list[str]:
    """Gleichmäßig verteilte Standbilder als JPEG-Base64 (für Claude/Ollama: "Was passiert im Clip?")."""
    import base64
    import tempfile

    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for k in range(n):
            t = duration * (k + 0.5) / n
            f = Path(tmp) / f"s{k}.jpg"
            r = run([ffmpeg(), "-hide_banner", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                     "-vf", f"scale={width}:-2", "-q:v", "5", str(f)])
            if r.returncode == 0 and f.exists():
                out.append(base64.b64encode(f.read_bytes()).decode())
    return out
