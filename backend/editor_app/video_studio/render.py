"""Rendern eines Drone-Cutter-Plans mit ffmpeg.

1. Jede Aufnahme einzeln: zuschneiden (bildgenau), Tempo, Format (9:16 / 16:9, mittig zugeschnitten),
   Farbe (gebackene LUT), feste Bildrate → seg_XXX.mp4 (sehr hohe Qualität, Zwischendatei)
2. Aneinanderhängen ohne neu zu kodieren (concat)
3. Endfassung: Ort-Titel darüberlegen, Musik (gekürzt/geloopt, Blenden, Ducking), optional Originalton
Vorschau = 540 px breit (schnell), Final = 1080×1920 bzw. bis 4K, H.264 oder H.265, AAC.
Originale werden nie verändert.
"""
from __future__ import annotations

import functools
import shutil
from pathlib import Path

from .. import media
from . import color as colormod
from . import music as musicmod
from . import speed as speedmod
from . import text as textmod
from . import transitions as transmod

FORMATS = {"reel": (1080, 1920), "youtube": (1920, 1080), "youtube4k": (3840, 2160)}


def out_size(fmt: str, quality: str) -> tuple[int, int]:
    W, H = FORMATS.get(fmt, FORMATS["reel"])
    if quality == "preview":
        f = 540 / min(W, H)
        W, H = int(round(W * f / 2) * 2), int(round(H * f / 2) * 2)
    return W, H


def out_fps(infos: list[dict]) -> float:
    """Bildrate der Quellen übernehmen: 60 wenn alle ≥50 fps, sonst 30 (25 bei PAL-Material)."""
    fps = [i.get("fps") or 30 for i in infos] or [30]
    if min(fps) >= 49:
        return 60.0 if min(fps) >= 59 else 50.0
    if all(abs(f - 25) < 0.5 for f in fps):
        return 25.0
    return 30.0


@functools.cache
def _nvenc() -> bool:
    return media.h264_encoder()[1] == "h264_nvenc"


def encoder(quality: str, codec: str = "h264") -> list[str]:
    if quality == "intermediate":
        if _nvenc():
            return ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "14", "-b:v", "0"]
        return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "14"]
    if quality == "preview":
        return media.h264_encoder()
    if codec == "h265":
        return (["-c:v", "hevc_nvenc", "-preset", "p5", "-cq", "21", "-b:v", "0", "-tag:v", "hvc1"] if _nvenc()
                else ["-c:v", "libx265", "-preset", "medium", "-crf", "20", "-tag:v", "hvc1"])
    return (["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "19", "-b:v", "0", "-profile:v", "high"] if _nvenc()
            else ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high"])


def _crop_filter(info: dict, W: int, H: int, xpos: float = 0.5) -> str:
    """Auf das Zielformat zuschneiden (ohne Balken), dann skalieren. xpos = horizontale Lage 0..1 (Mitte 0,5)."""
    sw, sh = info["width"], info["height"]
    target = W / H
    if sw / sh > target:          # Quelle breiter → links/rechts abschneiden
        cw = int(sh * target / 2) * 2
        x = int(max(0, min(sw - cw, (sw - cw) * xpos)) / 2) * 2
        crop = f"crop={cw}:{sh}:{x}:0"
    else:                         # Quelle höher → oben/unten abschneiden
        ch = int(sw / target / 2) * 2
        crop = f"crop={sw}:{ch}:0:{int((sh - ch) / 4) * 2}"
    return f"{crop},scale={W}:{H}:flags=lanczos,setsar=1"


def render_shot(src: Path, info: dict, shot: dict, out: Path, W: int, H: int, fps: float, lut: Path | None,
                work: Path, keep_audio: bool = False, head: float = 0.0, tail: float = 0.0,
                smooth: bool = False) -> None:
    """Eine Aufnahme rendern. head/tail = zusätzliche Ausgabe-Sekunden vor/nach der Aufnahme für Übergänge.
    Tempo: fest (speed) oder Kurve (ramp) – in Stücke zerlegt; smooth = Zeitlupe mit Zwischenbildern (optischer Fluss)."""
    ramp = shot.get("ramp") or ""
    sp = float(shot.get("speed", 1.0) or 1.0)
    s0, s1 = speedmod.end_speeds(ramp, sp)
    parts = ([(head, s0)] if head > 0 else []) + speedmod.pieces(ramp, sp, shot["dur"]) + \
        ([(tail, s1)] if tail > 0 else [])
    src_start = max(0.0, float(shot["src_in"]) - head * s0)
    src_total = sum(L * v for L, v in parts)
    out_total = head + shot["dur"] + tail
    n_frames = max(1, int(round(out_total * fps)))
    pre = [x for x in (media.sdr_filter(info).rstrip(","), _crop_filter(info, W, H, float(shot.get("xpos", 0.5)))) if x]
    chain = [f"[0:v:0]{','.join(pre)}[base]"]
    if len(parts) == 1:
        chain.append(f"[base]setpts=(PTS-STARTPTS)/{parts[0][1]:.6f}[sp]")
    else:
        labels = "".join(f"[i{k}]" for k in range(len(parts)))
        chain.append(f"[base]split={len(parts)}{labels}")
        t = 0.0
        outs = ""
        for k, (L, v) in enumerate(parts):
            a, b = t, t + L * v
            chain.append(f"[i{k}]trim=start={a:.4f}:end={b:.4f},setpts=(PTS-STARTPTS)/{v:.6f}[p{k}]")
            outs += f"[p{k}]"
            t = b
        chain.append(f"{outs}concat=n={len(parts)}:v=1:a=0[sp]")
    slow = min(v for _, v in parts) < 0.75
    tail_f = [f"minterpolate=fps={fps:g}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1" if smooth and slow
              else f"fps={fps:g}"]
    extra_inputs: list[str] = []
    if lut is not None:
        lf, extra = colormod.ffmpeg_filter(lut, work)
        if lf == "HALD":
            extra_inputs = extra
        else:
            tail_f.append(lf)
    args = ["-ss", f"{src_start:.3f}", "-t", f"{src_total + 0.5:.3f}", "-i", str(src)]
    if extra_inputs:
        args += ["-i", extra_inputs[0]]
        chain.append(f"[sp]{','.join(tail_f)}[g];[g][1:v]haldclut,format=yuv420p[v]")
    else:
        chain.append(f"[sp]{','.join(tail_f)},format=yuv420p[v]")
    fc = ";".join(chain)
    if keep_audio and info.get("has_audio"):
        at = src_total / out_total   # mittleres Tempo (Ton bei Rampen nur ungefähr – unter Musik unauffällig)
        tempo = []
        while at > 2.0:
            tempo.append("atempo=2.0")
            at /= 2
        while at < 0.5:
            tempo.append("atempo=0.5")
            at /= 0.5
        tempo.append(f"atempo={at:.4f}")
        fc += f";[0:a:0]asetpts=PTS-STARTPTS,{','.join(tempo)},aformat=sample_rates=48000:channel_layouts=stereo," \
              f"atrim=0:{out_total:.4f},apad=whole_dur={out_total:.4f}[a]"
    args += ["-filter_complex", fc, "-map", "[v]"]
    if keep_audio and info.get("has_audio"):
        args += ["-map", "[a]", "-c:a", "pcm_s16le"]
    else:
        args += ["-an"]
    args += ["-frames:v", str(n_frames), *encoder("intermediate"), "-r", f"{fps:g}", "-g", str(int(fps)),
             str(out)]
    media._run_with_progress(args, out_total, None)


def _join(segs: list[Path], shots: list[dict], trans: list[dict], body: Path, fps: float, keep: bool,
          heads: list[float]) -> None:
    """Aufnahmen verbinden: harte Schnitte per concat (ohne neu zu kodieren), sonst xfade-Kette."""
    total = sum(s["dur"] for s in shots)
    if not any(t.get("dur", 0) > 0 for t in trans):
        lst = body.parent / "list.txt"
        lst.write_text("".join(f"file '{s.name}'\n" for s in segs), encoding="utf-8")
        media._run_with_progress(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(body)], total, None)
        return
    args: list[str] = []
    for f in segs:
        args += ["-i", str(f)]
    fc, cur = [], "[0:v]"
    for k in range(1, len(segs)):
        t = trans[k - 1]
        d = float(t.get("dur", 0))
        nxt = f"[x{k}]"
        if d > 0:
            xf = transmod.TRANSITIONS.get(t["id"], transmod.TRANSITIONS["dissolve"])["xfade"] or "fade"
            off = shots[k]["t0"] - d / 2
            fc.append(f"{cur}[{k}:v]xfade=transition={xf}:duration={d:.4f}:offset={off:.4f}{nxt}")
        else:
            fc.append(f"{cur}[{k}:v]concat=n=2:v=1:a=0{nxt}")
        cur = nxt
    fc.append(f"{cur}fps={fps:g},format=yuv420p[v]")
    maps = ["-map", "[v]"]
    if keep:
        aparts = "".join(f"[a{k}]" for k in range(len(segs)))
        for k, sh in enumerate(shots):
            fc.append(f"[{k}:a]atrim=start={heads[k]:.4f}:end={heads[k] + sh['dur']:.4f},asetpts=PTS-STARTPTS[a{k}]")
        fc.append(f"{aparts}concat=n={len(segs)}:v=0:a=1[a]")
        maps += ["-map", "[a]", "-c:a", "pcm_s16le"]
    script = body.parent / "join_filter.txt"
    script.write_text(";".join(fc), encoding="utf-8")
    media._run_with_progress([*args, *media.filter_script_args(script), *maps, *encoder("intermediate"),
                              "-r", f"{fps:g}", "-t", f"{total:.4f}", str(body)], total, None)


def render(plan: dict, clips: dict[str, dict], work: Path, out: Path, quality: str = "preview",
           progress: media.Progress | None = None) -> dict:
    """plan: {format, duration, shots[], grade{look,strength,protect_skin,overrides}, title{}, music{}, keep_audio, codec}
    clips: {id: {"path": Path, "info": probe}}. Gibt Infos zur fertigen Datei zurück."""
    prog = progress or (lambda f: None)
    fmt = plan.get("format", "reel")
    W, H = out_size(fmt, quality)
    infos = [c["info"] for c in clips.values()]
    fps = out_fps(infos) if quality != "preview" else min(30.0, out_fps(infos))
    shots = plan["shots"]
    total = round(sum(s["dur"] for s in shots), 6)
    work.mkdir(parents=True, exist_ok=True)
    segdir = work / f"seg_{quality}"
    if segdir.exists():
        shutil.rmtree(segdir)
    segdir.mkdir()
    g = plan.get("grade") or {}
    lut = None
    if g.get("look", "vivid_travel") != "none" and g.get("strength", 1) > 0:
        p = colormod.params_for(g.get("look", "vivid_travel"), float(g.get("strength", 1.0)), g.get("overrides"),
                                bool(g.get("protect_skin", True)))
        lut = colormod.lut_file(p, work / "luts")
    keep = bool(plan.get("keep_audio"))
    trans = list(plan.get("transitions") or [])
    trans = (trans + [{"id": "cut", "dur": 0.0}] * len(shots))[: max(0, len(shots) - 1)]
    smooth = bool(plan.get("smooth_slowmo", True)) and quality != "preview"
    segs, heads = [], []
    for k, sh in enumerate(shots):
        media.check_cancel()
        c = clips[sh["clip"]]
        head = float(trans[k - 1]["dur"]) / 2 if k > 0 else 0.0
        tail = float(trans[k]["dur"]) / 2 if k < len(shots) - 1 else 0.0
        f = segdir / f"seg_{k:03d}.mov" if keep else segdir / f"seg_{k:03d}.mp4"
        render_shot(c["path"], c["info"], sh, f, W, H, fps, lut, work, keep, head, tail, smooth)
        segs.append(f)
        heads.append(head)
        prog(0.75 * (k + 1) / len(shots))
    body = segdir / ("body.mov" if keep else "body.mp4")
    _join(segs, shots, trans, body, fps, keep, heads)
    prog(0.8)

    # ---------- Endfassung: Titel + Musik
    args = ["-i", str(body)]
    fc, vlabel, n_in = [], "0:v", 1
    title = plan.get("title")
    if title and (title.get("text") or "").strip() and title.get("enabled", True):
        t = textmod.Title.from_dict(title)
        tdir = work / f"title_{quality}"
        start, n = textmod.render_sequence(t, W, H, fps, tdir)
        args += ["-framerate", f"{fps:g}", "-start_number", "0", "-itsoffset", f"{start:.3f}",
                 "-i", str(tdir / "t_%05d.png")]
        fc.append(f"[0:v][{n_in}:v]overlay=0:0:eof_action=pass:format=auto,format=yuv420p[v]")
        vlabel, n_in = "[v]", n_in + 1
    outro = plan.get("outro") or {}
    if outro.get("enabled") and (outro.get("text") or "").strip():
        od = float(outro.get("duration", 2.5))
        t = textmod.Title.from_dict({"text": outro["text"], "subtitle": outro.get("subtitle", ""),
                                     "font": (title or {}).get("font", "Montserrat ExtraLight"), "size": 0.05,
                                     "spacing": 0.25, "spacing_start": 0.32, "y": 0.5, "start": max(0.0, total - od),
                                     "duration": od, "fade_in": 0.6, "fade_out": 0.5, "anim_in": "fade",
                                     "keep_case": True})
        odir = work / f"outro_{quality}"
        start, n = textmod.render_sequence(t, W, H, fps, odir)
        args += ["-framerate", f"{fps:g}", "-start_number", "0", "-itsoffset", f"{start:.3f}",
                 "-i", str(odir / "t_%05d.png")]
        src = vlabel if vlabel.startswith("[") else "[0:v]"
        fc.append(f"{src}[{n_in}:v]overlay=0:0:eof_action=pass:format=auto,format=yuv420p[vo]")
        vlabel, n_in = "[vo]", n_in + 1
    m = plan.get("music") or {}
    alabel = None
    if m.get("file"):
        path = Path(m["path"]) if m.get("path") else musicmod.MUSIC_DIR / m["file"]
        duck = None
        if title and title.get("text") and m.get("duck", True):
            t = textmod.Title.from_dict(title)
            duck = (t.start, t.start + t.duration)
        inp, chain = musicmod.audio_filter(path, float(m.get("start", 0)), total, float(m.get("gain_db", 0)),
                                           duck=duck)
        args += inp
        fc.append(f"[{n_in}:a]{chain}[m]")
        alabel, n_in = "[m]", n_in + 1
        if keep:
            fc.append(f"[0:a]volume={float(m.get('original_db', -10)):.1f}dB[o];[m][o]amix=inputs=2:normalize=0[a]")
            alabel = "[a]"
    elif keep:
        alabel = "0:a"
    if fc:
        args += ["-filter_complex", ";".join(fc)]
    args += ["-map", vlabel]
    if alabel:
        args += ["-map", alabel, "-c:a", "aac", "-b:a", "192k" if quality != "preview" else "128k", "-ar", "48000"]
    else:
        args += ["-an"]
    args += [*encoder(quality, plan.get("codec", "h264")), "-pix_fmt", "yuv420p", "-r", f"{fps:g}",
             *media.SDR_TAGS, "-t", f"{total:.4f}", "-movflags", "+faststart", str(out)]
    media._run_with_progress(args, total, lambda f: prog(0.8 + 0.2 * f))
    prog(1.0)
    shutil.rmtree(segdir, ignore_errors=True)
    return {"file": out.name, "width": W, "height": H, "fps": fps, "duration": total, "size": out.stat().st_size}
