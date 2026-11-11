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
    "1080": "1080p (recommended)",
    "2160": "4K (if the original is that big)",
    "original": "Original resolution",
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
            raise UserError("The video has no audio track.")
        tmp = raw.with_suffix(".tmp")
        r = media.run([media.ffmpeg(), "-hide_banner", "-y", "-i", str(src), "-map", f"0:{info['audio_index']}",
                       "-vn", "-ac", str(CH), "-ar", str(SR), "-f", "s16le", "-c:a", "pcm_s16le", str(tmp)])
        if r.returncode != 0:
            raise UserError("The audio could not be read: " + r.stderr[-300:])
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
                  centers: list[tuple[float, float] | None], k0: int = 0) -> str:
    """Abwechselnde Zoom-Stufen pro Abschnitt (100/108/115 %), Ausschnitt um das Gesicht.
    k0: Nummer des ersten Abschnitts (beim Rendern in Teilen geht der Wechsel nahtlos weiter)."""
    big_w, big_h = int(round(out_w * 1.15 / 2)) * 2, int(round(out_h * 1.15 / 2)) * 2
    z_terms, x_terms, y_terms = [], [], []
    pos = 0
    for k, (a, b) in enumerate(frames):
        n = b - a
        z = ZOOM_LEVELS[(k + k0) % len(ZOOM_LEVELS)]
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
        raise UserError("The audio could not be processed: " + r.stderr[-300:])
    return out


def render(src: Path, info: dict, segments: list[list[float]], out: Path, work: Path, quality: str = "1080",
           progress: Callable[[float, str], None] | None = None, options: dict | None = None) -> dict:
    """options: zoom, loudness, denoise (bool), subtitles ("aus"/"srt"/"einbrennen"), karaoke (bool),
    words + flags (Transkript), buzzwords ([{start,end,text?}]), gaze (blick.json-Daten), fonts_dir."""
    from . import animations, gaze, subtitles

    opts = {"zoom": True, "loudness": True, "denoise": False, "subtitles": "srt", "karaoke": False,
            "audio_copy": False, "reel": False, **(options or {})}
    report = progress or (lambda f, m: None)
    if quality not in QUALITIES:
        raise UserError("Unknown quality.")
    if not segments:
        raise UserError("Nothing is left: all words are cut.")
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
        report(0.02, "Cutting audio …")
        audio = build_audio(src, info, frames, fps, work)
    if audio is not None and (opts["loudness"] or opts["denoise"]):
        report(0.04, "Polishing audio (loudness −14 LUFS) …")
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
    hooks = [{"s": tmap.clamp(o["start"]), "e": tmap.clamp(o["end"]), "text": o["text"], "anim": o.get("anim", "karte")}
             for o in opts.get("overlays") or [] if o.get("kind") not in ("yt", "fx")]
    face = gaze.face_box(gaze_data) if gaze_data else None
    yt_items = [o for o in opts.get("overlays") or [] if o.get("kind") == "yt"]
    yt_events = animations.ass_events(yt_items, tmap, out_w, out_h, face) if yt_items else []
    if yt_events:
        # Buzzwords nie gleichzeitig mit einer Animation
        spans = [(tmap.clamp(o["start"]), tmap.clamp(o["end"])) for o in yt_items if o.get("on", True)]
        buzz = [b for b in buzz if all(b["e"] <= s or b["s"] >= e for s, e in spans)]
    ass_filter = ""
    if burn_subs or buzz or hooks or yt_events:
        ass_path = work / "texte.ass"
        ass_path.write_text(subtitles.ass(out_w, out_h, groups if burn_subs else None, buzz, face, opts["karaoke"],
                                          hooks, extra_styles=animations.ass_styles(out_h / 1080) if yt_events else None,
                                          extra_events=yt_events),
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
        msg = f"Rendering video ({f:.0%})" + (f", about {int(rest // 60)} min {int(rest % 60)} s left" if rest else "")
        report(0.06 + 0.94 * f, msg)

    fx_items = []
    if opts.get("overlays"):
        from . import fxrender
        kw_all = subtitles.kept_words(words, flags, tmap) if words else []
        fx_items = fxrender.prepare(opts["overlays"], tmap, kw_all, new_duration)
    share = 0.6 if fx_items else 1.0
    if len(frames) > CHUNK_SEGMENTS:
        # Viele Schnitte: in Teilen rendern (eine einzige riesige Schnitt-Regel bringt ffmpeg 7/8 zum Absturz:
        # "Cannot allocate memory"), dann die Teile ohne Qualitätsverlust aneinanderhängen
        _render_chunked(src, info, frames, fps, fps_str, out_w, out_h, opts, gaze_data, keep_t, ass_filter, audio,
                        audio_in, audio_map, audio_codec, encoder, tmp, work, lambda f: on_video(f * share))
    else:
        media._run_with_progress(args, new_duration, (lambda f: on_video(f * share)))
    if fx_items:
        from . import fxrender
        fxrender.apply(tmp, out.with_suffix(".fx.mp4"), fx_items, out_w, out_h, fps_str, face, encoder, work,
                       lambda f, m: report(0.06 + 0.94 * (0.6 + 0.4 * f), m), source=src)
        tmp.unlink(missing_ok=True)
        tmp = out.with_suffix(".fx.mp4")
    if opts.get("speed"):
        from . import fxrender
        sp = fxrender.prepare_speed(opts["speed"], tmap, new_duration)
        if sp:
            fxrender.apply_speed(tmp, out.with_suffix(".speed.mp4"), sp, encoder, fps_str, work,
                                 lambda f, m: report(0.95 + 0.05 * f, m))
            tmp.unlink(missing_ok=True)
            tmp = out.with_suffix(".speed.mp4")
            new_duration = float(media.probe(tmp)["duration"])
    tmp.replace(out)
    for f in ("ton_schnitt.pcm", "ton_fertig.pcm"):
        try:
            (work / f).unlink()
        except OSError:
            pass
    report(1.0, "Rendering done")
    return {"file": out.name, "duration": round(new_duration, 2), "segments": len(frames),
            "size": out.stat().st_size, "quality": quality, "extra": extra_files,
            "options": {k: opts[k] for k in ("zoom", "loudness", "denoise", "subtitles", "karaoke", "audio_copy", "reel")},
            "buzzwords": len(buzz)}


CHUNK_SEGMENTS = 60


def _render_chunked(src, info, frames, fps, fps_str, out_w, out_h, opts, gaze_data, keep_t, ass_filter, audio,
                    audio_in, audio_map, audio_codec, encoder, tmp: Path, work: Path, on_video) -> None:
    """Video in Teilen von höchstens CHUNK_SEGMENTS Stücken rendern (jeder Teil springt direkt an seine Stelle im
    Original), Untertitel/Texte laufen mit der Gesamtzeit weiter, am Ende werden die Teile verlustfrei verbunden."""
    from . import gaze
    total = sum(b - a for a, b in frames)
    done = 0
    parts = []
    h = 0.5 / float(fps)
    for c0 in range(0, len(frames), CHUNK_SEGMENTS):
        chunk = frames[c0:c0 + CHUNK_SEGMENTS]
        cs = max(0.0, float(Fraction(chunk[0][0]) / fps) - 1.0)  # etwas früher anspringen, dann bildgenau auswählen
        ce = float(Fraction(chunk[-1][1]) / fps) + 0.5
        terms = "+".join(f"between(t\\,{float(Fraction(a) / fps) - cs - h:.6f}\\,{float(Fraction(b) / fps) - cs - h:.6f})"
                         for a, b in chunk)
        n_chunk = sum(b - a for a, b in chunk)
        if opts["zoom"] and len(frames) > 1:
            centers = [gaze.face_center(gaze_data, a, b) if gaze_data else None for a, b in keep_t[c0:c0 + len(chunk)]]
            scale = _zoom_filters(chunk, fps, out_w, out_h, centers, k0=c0)
        else:
            scale = f"scale={out_w}:{out_h}:flags=lanczos"
        offset = done  # Bildnummer im fertigen Video, an der dieser Teil beginnt
        graph = (f"[0:{info['video_index']}]fps={fps_str},select='{terms}',setpts=N/({fps_str})/TB,"
                 f"{scale},setsar=1,format=yuv420p,setpts=PTS+{offset}/({fps_str})/TB{ass_filter},"
                 f"setpts=PTS-STARTPTS[v]")
        script = work / f"filter_part{c0:05d}.txt"
        script.write_text(graph, encoding="utf-8")
        part = work / f"teil_{c0:05d}.mp4"
        args = ["-ss", f"{cs:.4f}", "-t", f"{ce - cs:.4f}", "-i", str(src), *media.filter_script_args(script),
                "-map", "[v]", "-frames:v", str(n_chunk), *encoder, "-r", fps_str, "-an", str(part)]
        base = done
        media._run_with_progress(args, n_chunk / float(fps), lambda f, base=base, n=n_chunk: on_video((base + f * n) / total))
        parts.append(part)
        done += n_chunk
    lst = work / "teile.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    if opts["audio_copy"]:
        audio_args = ["-i", str(src)]
        amap = ["-map", f"1:{info['audio_index']}"]
    elif audio_in:
        audio_args = audio_in
        amap = ["-map", "1:a"]
    else:
        audio_args, amap = [], []
    args = ["-f", "concat", "-safe", "0", "-i", str(lst), *audio_args, "-map", "0:v", *amap, "-c:v", "copy",
            *audio_codec, "-movflags", "+faststart", "-map_metadata", "-1", "-shortest", str(tmp)]
    media._run_with_progress(args, total / float(fps), None)
    for p in parts:
        p.unlink(missing_ok=True)


def render_clip(src: Path, info: dict, segments: list[list[float]], out: Path, work: Path, words: list[dict],
                flags: list, hook_text: str, face_box: list[float] | None, fonts_dir: str | None,
                progress: Callable[[float, str], None] | None = None, texts: list[str] | None = None,
                fx: list[dict] | None = None) -> dict:
    """Reel aus Stücken eines langen Videos (Reihenfolge frei). 1080×1920; Querformat ohne Zoom mittig mit
    schwarzen Balken (Hook-Text im oberen Balken), Untertitel mit Karaoke, Ton auf -14 LUFS, < 30 MB."""
    from . import subtitles

    report = progress or (lambda f, m: None)
    if not segments:
        raise UserError("The clip is empty.")
    work.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    fps = frame_rate(info)
    last = int(info["duration"] * fps)
    frames = [(max(0, round(Fraction(a).limit_denominator(100000) * fps)),
               min(last, round(Fraction(b).limit_denominator(100000) * fps))) for a, b in segments]
    frames = [(a, b) for a, b in frames if b > a]
    total = float(sum(b - a for a, b in frames) / fps)
    fps_str = f"{fps.numerator}/{fps.denominator}"
    W, H = 1080, 1920

    report(0.02, "Putting the audio together …")
    audio = build_audio(src, info, frames, fps, work)
    audio = process_audio(audio, work / "clip_ton.pcm", True, False)

    # Wörter in die Clip-Zeit umrechnen (Stücke können aus verschiedenen Stellen kommen)
    clip_words, offset = [], 0.0
    for a, b in frames:
        ta, tb = float(Fraction(a) / fps), float(Fraction(b) / fps)
        for k, w in enumerate(words):
            if not flags[k] and ta <= (w["s"] + w["e"]) / 2 <= tb:
                clip_words.append({"i": k, "w": w["w"], "s": offset + max(0.0, w["s"] - ta),
                                   "e": offset + min(tb, w["e"]) - ta})
        offset += tb - ta
    groups = subtitles.lines(clip_words, max_chars=26)

    landscape = info["width"] > info["height"]
    if landscape:
        vh = int(round(W * info["height"] / info["width"] / 2)) * 2
        top = 1250 - vh  # Video endet am Rand der Safe Zone, darüber der Balken für den Hook
        layout = f"scale={W}:{vh}:flags=lanczos,pad={W}:{H}:0:{top}:black"
        sub_y = top + round(vh * 0.86)
        hook_y = max(290, top - 300)
        fb = None
    else:
        layout = f"scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black"
        sub_y, hook_y, fb = round(H * 0.70), None, face_box
    from .clips import overlay_plan
    hooks = overlay_plan(hook_text, texts or [], total)
    ass_path = work / "clip.ass"
    ass_path.write_text(subtitles.ass(W, H, groups, [], fb, True, hooks, sub_y_override=sub_y,
                                      hook_y_override=hook_y), encoding="utf-8")
    ass_f = f",ass={_filter_path(ass_path)}" + (f":fontsdir={_filter_path(Path(fonts_dir))}" if fonts_dir else "")
    n = len(frames)
    # Jedes Stück direkt anspringen (statt das lange Video von vorn bis zur letzten Stelle zu lesen)
    seg_inputs, parts = [], []
    for k, (a, b) in enumerate(frames):
        ta, tb = float(Fraction(a) / fps), float(Fraction(b) / fps)
        seg_inputs += ["-ss", f"{ta:.4f}", "-t", f"{tb - ta + 0.5:.4f}", "-i", str(src)]
        parts.append(f"[{k}:{info['video_index']}]fps={fps_str},trim=end_frame={b - a},setpts=PTS-STARTPTS[s{k}]")
    parts.append("".join(f"[s{k}]" for k in range(n)) + f"concat=n={n}:v=1:a=0[c]")
    parts.append(f"[c]{layout},setsar=1,format=yuv420p{ass_f}[v]")
    script = work / "clip_filter.txt"
    script.write_text(";".join(parts), encoding="utf-8")

    audio_kbps = 192
    max_kbps = max(800, min(5000, int(30 * 8 * 1000 * 0.88 / max(1.0, total)) - audio_kbps))
    enc = _encoder()
    rate = ["-maxrate", f"{max_kbps}k", "-bufsize", f"{max_kbps * 2}k"]
    enc = (["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "20", *rate] if enc[1] == "h264_nvenc"
           else ["-c:v", "libx264", "-preset", "fast", "-crf", "20", *rate])
    tmp = out.with_suffix(".tmp.mp4")
    args = [*seg_inputs, "-f", "s16le", "-ar", str(SR), "-ac", str(CH), "-i", str(audio),
            *media.filter_script_args(script), "-map", "[v]", "-map", f"{n}:a", *enc, "-profile:v", "high",
            "-r", fps_str, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-map_metadata", "-1",
            "-shortest", str(tmp)]
    fx_items = []
    if fx:
        from . import fxrender
        fx_items = fxrender.prepare(fx, subtitles.TimeMap([(0.0, total)]), clip_words, total)
    share = 0.55 if fx_items else 1.0
    media._run_with_progress(args, total, lambda f: report(0.05 + 0.95 * share * f, f"Rendering reel ({f:.0%})"))
    if fx_items:
        from . import fxrender
        face_out = clip_face_box(info, face_box)
        fxrender.apply(tmp, out.with_suffix(".fx.mp4"), fx_items, W, H, fps_str, face_out, enc + ["-profile:v", "high"],
                       work, lambda f, m: report(0.05 + 0.95 * (share + (1 - share) * f), m))
        tmp.unlink(missing_ok=True)
        tmp = out.with_suffix(".fx.mp4")
    tmp.replace(out)
    srt = out.with_suffix(".srt")
    srt.write_text(subtitles.srt(groups), encoding="utf-8")
    report(1.0, "Done")
    return {"file": out.name, "duration": round(total, 2), "size": out.stat().st_size, "srt": srt.name}


def clip_layout(info: dict) -> tuple[int, int]:
    """Wo das Video im Hochformat-Reel liegt: (oben, Höhe) in Pixeln von 1920."""
    if info["width"] > info["height"]:
        vh = int(round(1080 * info["height"] / info["width"] / 2)) * 2
        return 1250 - vh, vh
    return 0, 1920


def clip_face_box(info: dict, face_box: list[float] | None) -> list[float] | None:
    """Gesichts-Position im Reel (Querformat-Videos liegen als Band in der Mitte)."""
    if not face_box:
        return None
    top, vh = clip_layout(info)
    if top == 0:
        return face_box
    fx0, fy0, fx1, fy1 = face_box
    return [fx0, (top + fy0 * vh) / 1920, fx1, (top + fy1 * vh) / 1920]


def safe_name(name: str) -> str:
    return re.sub(r"[^\w\-. ]+", "_", name).strip()[:60] or "video"
