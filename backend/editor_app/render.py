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


def output_size(info: dict, quality: str) -> tuple[int, int]:
    w, h = info["width"], info["height"]
    short = min(w, h)
    target = {"1080": 1080, "2160": 2160}.get(quality)
    if target and short > target:
        f = target / short
        w, h = w * f, h * f
    return int(round(w / 2)) * 2, int(round(h / 2)) * 2


def _filter_path(p: Path) -> str:
    s = str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    return f"'{s}'"


ZOOM_LEVELS = [1.0, 1.08, 1.15]


def _zoom_filters(frames: list[tuple[int, int]], fps: Fraction, out_w: int, out_h: int,
                  centers: list[tuple[float, float] | None]) -> str:
    """Abwechselnde Zoom-Stufen pro Abschnitt (100/108/115 %), Ausschnitt um das Gesicht."""
    big_w, big_h = int(round(out_w * 1.15 / 2)) * 2, int(round(out_h * 1.15 / 2)) * 2
    z_terms, x_terms, y_terms = [], [], []
    pos = 0
    for k, (a, b) in enumerate(frames):
        n = b - a
        z = ZOOM_LEVELS[k % len(ZOOM_LEVELS)]
        cx, cy = centers[k] or (0.5, 0.45)
        rng = f"between(in\\,{pos}\\,{pos + n - 1})"
        if z != 1.0:
            z_terms.append(f"{z - 1:.3f}*{rng}")
            # Gesicht in die Bildmitte (waagrecht) und ins obere Drittel (senkrecht) rücken, ohne über den Rand zu gehen
            x_terms.append(f"{rng}*max(0\\,min(iw-iw/zoom\\,{cx:.4f}*iw-iw/zoom/2))")
            y_terms.append(f"{rng}*max(0\\,min(ih-ih/zoom\\,{cy:.4f}*ih-ih/zoom*0.42))")
        pos += n
    z_expr = "1+" + "+".join(z_terms) if z_terms else "1"
    x_expr = "+".join(x_terms) if x_terms else "0"
    y_expr = "+".join(y_terms) if y_terms else "0"
    fps_str = f"{fps.numerator}/{fps.denominator}"
    return (f"scale={big_w}:{big_h}:flags=lanczos,"
            f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d=1:s={out_w}x{out_h}:fps={fps_str}")


def process_audio(raw: Path, out: Path, loudness: bool, denoise: bool) -> Path:
    """Ton veredeln: optional Rauschen mindern, sanft komprimieren, auf -14 LUFS (YouTube) bringen (2 Durchgänge)."""
    if not loudness and not denoise:
        return raw
    chain = []
    if denoise:
        chain.append("afftdn=nr=10:nf=-45")
    if loudness:
        chain.append("acompressor=threshold=-20dB:ratio=2.5:attack=15:release=200:makeup=2")
    pcm_in = ["-f", "s16le", "-ar", str(SR), "-ac", str(CH), "-i", str(raw)]
    if loudness:
        r = media.run([media.ffmpeg(), "-hide_banner", "-nostdin", *pcm_in, "-af",
                       ",".join(chain + ["loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json"]), "-f", "null", "-"])
        m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
        if m:
            import json as _json
            st = _json.loads(m.group(0))
            chain.append(f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={st['input_i']}:measured_TP={st['input_tp']}:"
                         f"measured_LRA={st['input_lra']}:measured_thresh={st['input_thresh']}:"
                         f"offset={st['target_offset']}:linear=true")
        else:
            chain.append("loudnorm=I=-14:TP=-1.5:LRA=11")
        chain.append(f"aresample={SR}")
    r = media.run([media.ffmpeg(), "-hide_banner", "-nostdin", "-y", *pcm_in, "-af", ",".join(chain),
                   "-ar", str(SR), "-ac", str(CH), "-f", "s16le", str(out)])
    if r.returncode != 0:
        raise UserError("Der Ton konnte nicht bearbeitet werden: " + r.stderr[-300:])
    return out


def render(src: Path, info: dict, segments: list[list[float]], out: Path, work: Path, quality: str = "1080",
           progress: Callable[[float, str], None] | None = None, options: dict | None = None) -> dict:
    """options: zoom, loudness, denoise (bool), subtitles ("aus"/"srt"/"einbrennen"), karaoke (bool),
    words + flags (Transkript), buzzwords ([{start,end,text?}]), gaze (blick.json-Daten), fonts_dir."""
    from . import gaze, subtitles

    opts = {"zoom": True, "loudness": True, "denoise": False, "subtitles": "srt", "karaoke": False,
            "audio_copy": False, "reel": False, **(options or {})}
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
    out_w, out_h = output_size(info, quality)
    fps_str = f"{fps.numerator}/{fps.denominator}"
    keep_t = [(float(Fraction(a) / fps), float(Fraction(b) / fps)) for a, b in frames]
    tmap = subtitles.TimeMap(keep_t)
    gaze_data = opts.get("gaze") or {}

    audio = None
    if not info.get("has_audio"):
        opts["audio_copy"] = False  # stummer Clip: Video ohne Ton
    elif opts["audio_copy"] and len(frames) == 1 and frames[0][0] == 0:
        pass  # Reel: Ton bleibt exakt wie im Original (wird nur übernommen)
    else:
        opts["audio_copy"] = False
        report(0.02, "Ton wird geschnitten …")
        audio = build_audio(src, info, frames, fps, work)
    if audio is not None and (opts["loudness"] or opts["denoise"]):
        report(0.04, "Ton wird veredelt (Lautstärke −14 LUFS) …")
        audio = process_audio(audio, work / "ton_fertig.pcm", opts["loudness"], opts["denoise"])

    # Untertitel / Buzzwords
    extra_files = []
    words, flags = opts.get("words") or [], opts.get("flags") or []
    groups = None
    if words and opts["subtitles"] in ("srt", "einbrennen"):
        kw = subtitles.kept_words(words, flags, tmap)
        groups = subtitles.lines(kw, max_chars=26 if out_h > out_w else 42)
        srt_path = out.with_suffix(".srt")
        srt_path.write_text(subtitles.srt(groups), encoding="utf-8")
        extra_files.append(srt_path.name)
    buzz = subtitles.buzz_events(opts.get("buzzwords") or [], words, tmap) if words else []
    burn_subs = opts["subtitles"] == "einbrennen" and groups
    hooks = [{"s": tmap.clamp(o["start"]), "e": tmap.clamp(o["end"]), "text": o["text"]}
             for o in opts.get("overlays") or []]
    ass_filter = ""
    if burn_subs or buzz or hooks:
        ass_path = work / "texte.ass"
        ass_path.write_text(subtitles.ass(out_w, out_h, groups if burn_subs else None, buzz,
                                          gaze.face_box(gaze_data) if gaze_data else None, opts["karaoke"], hooks),
                            encoding="utf-8")
        ass_filter = f",ass={_filter_path(ass_path)}"
        if opts.get("fonts_dir"):
            ass_filter += f":fontsdir={_filter_path(Path(opts['fonts_dir']))}"

    h = 0.5 / float(fps)
    terms = "+".join(f"between(t\\,{float(Fraction(a) / fps) - h:.6f}\\,{float(Fraction(b) / fps) - h:.6f})"
                     for a, b in frames)
    if opts["zoom"] and len(frames) > 1:
        centers = [gaze.face_center(gaze_data, a, b) if gaze_data else None for a, b in keep_t]
        scale = _zoom_filters(frames, fps, out_w, out_h, centers)
    else:
        scale = f"scale={out_w}:{out_h}:flags=lanczos"
    graph = (f"[0:{info['video_index']}]fps={fps_str},select='{terms}',setpts=N/({fps_str})/TB,"
             f"{scale},setsar=1,format=yuv420p{ass_filter}[v]")
    script = work / "filter.txt"
    script.write_text(graph, encoding="utf-8")

    tmp = out.with_suffix(".tmp.mp4")
    encoder = _encoder()
    if opts["reel"]:
        # Reels: unter 30 MB bleiben (Instagram/Metricool). Bitrate passend zur Länge, höchstens 5 Mbit/s.
        # Übernommener Original-Ton kann größer sein (z. B. 320 kbit/s bei DJI) → großzügig einrechnen
        audio_kbps = 330 if opts["audio_copy"] else 192
        max_kbps = max(800, min(5000, int(30 * 8 * 1000 * 0.88 / max(1.0, new_duration)) - audio_kbps))
        rate = ["-maxrate", f"{max_kbps}k", "-bufsize", f"{max_kbps * 2}k"]
        if encoder[1] == "h264_nvenc":
            encoder = ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "20", *rate, "-profile:v", "high"]
        else:
            encoder = ["-c:v", "libx264", "-preset", "fast", "-crf", "20", *rate, "-profile:v", "high"]
    if not info.get("has_audio"):
        audio_in, audio_map, audio_codec = [], [], ["-an"]
    elif opts["audio_copy"]:
        audio_in, audio_map, audio_codec = [], ["-map", f"0:{info['audio_index']}"], ["-c:a", "copy"]
        if info.get("audio_codec") not in ("aac", "mp3"):
            audio_codec = ["-c:a", "aac", "-b:a", "192k"]
    else:
        audio_in = ["-f", "s16le", "-ar", str(SR), "-ac", str(CH), "-i", str(audio)]
        audio_map, audio_codec = ["-map", "1:a"], ["-c:a", "aac", "-b:a", "192k"]
    args = ["-i", str(src), *audio_in, *media.filter_script_args(script), "-map", "[v]", *audio_map,
            *encoder, "-r", fps_str, *audio_codec,
            "-movflags", "+faststart", "-map_metadata", "-1", "-shortest", str(tmp)]
    started = time.time()

    def on_video(f: float):
        el = time.time() - started
        rest = el / f * (1 - f) if f > 0.02 else None
        msg = f"Video wird berechnet ({f:.0%})" + (f", noch ca. {int(rest // 60)} Min {int(rest % 60)} s" if rest else "")
        report(0.06 + 0.94 * f, msg)

    media._run_with_progress(args, new_duration, on_video)
    tmp.replace(out)
    for f in ("ton_schnitt.pcm", "ton_fertig.pcm"):
        try:
            (work / f).unlink()
        except OSError:
            pass
    report(1.0, "Fertig gerendert")
    return {"file": out.name, "duration": round(new_duration, 2), "segments": len(frames),
            "size": out.stat().st_size, "quality": quality, "extra": extra_files,
            "options": {k: opts[k] for k in ("zoom", "loudness", "denoise", "subtitles", "karaoke", "audio_copy", "reel")},
            "buzzwords": len(buzz)}


def safe_name(name: str) -> str:
    return re.sub(r"[^\w\-. ]+", "_", name).strip()[:60] or "video"
