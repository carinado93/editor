"""Effekte ins fertige Video bringen.

1. Für jeden Effekt wird nur sein Zeitfenster aus dem fertigen Video gelesen, Bild für Bild bearbeitet
   (fx.render_frame) und als kurzer Clip gespeichert.
2. Ein letzter Durchgang legt alle Clips an ihre Stelle über das Video. Der Ton bleibt unverändert.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image, ImageFilter

from . import fx, media
from .errors import UserError


def prepare(overlays: list[dict], tmap, words_new: list[dict], total: float) -> list[dict]:
    """Effekte aus der Schnittliste (Original-Zeit) → Fenster in neuer Zeit, mit Wörtern und Punkt-Zeiten."""
    out = []
    for o in overlays:
        if o.get("kind") != "fx" or not o.get("on", True) or o.get("type") not in fx.TYPES:
            continue
        s, e = tmap.clamp(o["start"]), tmap.clamp(o["end"])
        # liegt der Effekt (teilweise) in einem weggeschnittenen Stück: an der nächsten Stelle mit voller Länge zeigen
        e = max(e, s + min(o["end"] - o["start"], 8.0))
        e = min(e, total - 0.05)
        if e - s < 0.6:
            continue
        it = dict(o, s=round(s, 3), e=round(e, 3))
        it["times"] = [max(0.0, tmap.clamp(t) - s) for t in o.get("item_t") or []] or None
        it["_words"] = [{"w": w["w"], "s": w["s"] - s, "e": w["e"] - s} for w in words_new if s - 0.3 <= w["s"] <= e]
        out.append(it)
    out.sort(key=lambda x: x["s"])
    # nie zwei gleichzeitig
    clean: list[dict] = []
    for it in out:
        if clean and it["s"] < clean[-1]["e"]:
            if it["s"] - clean[-1]["s"] < 1.0:
                continue
            clean[-1]["e"] = it["s"]
        clean.append(it)
    return [c for c in clean if c["e"] - c["s"] >= 0.6]


def _fps_float(fps_str: str) -> float:
    a, _, b = fps_str.partition("/")
    return float(a) / float(b or 1)


def grab_frame(source: Path, t: float, w: int, h: int) -> Image.Image | None:
    """Ein Bild aus dem Originalvideo (Original-Zeit), auf die Ausgabegröße gebracht."""
    r = subprocess.run([media.ffmpeg(), "-hide_banner", "-loglevel", "error", "-ss", f"{max(0.0, t):.3f}", "-i",
                        str(source), "-frames:v", "1", "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-"], capture_output=True, creationflags=media._NO_WINDOW)
    if r.returncode != 0 or len(r.stdout) < w * h * 3:
        return None
    return Image.frombuffer("RGB", (w, h), r.stdout[: w * h * 3], "raw", "RGB", 0, 1).copy()


_samples_cache: dict = {}


def _samples(source: Path, w: int, h: int, segmenter: fx.Segmenter, n: int = 24) -> list[tuple[float, Image.Image, Image.Image]]:
    """Gleichmäßig verteilte Bilder aus dem ganzen Video mit Personen-Maske (einmal pro Video berechnet)."""
    key = (str(source), w, h)
    if key in _samples_cache:
        return _samples_cache[key]
    dur = float(media.probe(source)["duration"])
    out = []
    for k in range(n):
        t = dur * (k + 0.5) / n
        fr = grab_frame(source, t, w, h)
        if fr is not None:
            out.append((t, fr, segmenter.mask(fr)))
    _samples_cache[key] = out
    return out


def auto_plate(source: Path, w: int, h: int, segmenter: fx.Segmenter, sharp: Image.Image | None = None) -> Image.Image | None:
    """Leerer Raum OHNE eigene Aufnahme: aus vielen Bildern des Videos die Stellen nehmen, an denen Carina gerade
    nicht ist (Median), was sie immer verdeckt wird aus der Umgebung ergänzt. Wo im aktuellen Bild schon Raum zu sehen
    ist, bleibt das scharfe Originalbild."""
    import cv2

    cache = source.parent / f"leerer_raum_{w}x{h}.png"
    if cache.exists() and sharp is None:
        return Image.open(cache).convert("RGB")
    smp = _samples(source, w, h, segmenter)
    if not smp:
        return None
    sw = 640
    sh = max(2, int(round(h * sw / w)))
    stack, valid = [], []
    for _, fr, m in smp:
        stack.append(np.asarray(fr.resize((sw, sh)), dtype=np.float32))
        # großzügig um Carina herum aussparen, sonst bleibt ein Umriss ihrer Haare im leeren Raum
        mm = np.asarray(m.resize((sw, sh)).point(lambda v: 255 if v > 45 else 0).filter(ImageFilter.MaxFilter(31)),
                        dtype=np.uint8) < 128
        valid.append(mm)
    arr = np.stack(stack)
    ok = np.stack(valid)[..., None]
    arr = np.where(ok, arr, np.nan)
    import warnings
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        med = np.nanmedian(arr, axis=0)
    hole = np.isnan(med[..., 0])
    med = np.nan_to_num(med, nan=0).clip(0, 255).astype(np.uint8)
    if hole.any():
        med = cv2.inpaint(med, hole.astype(np.uint8) * 255, 12, cv2.INPAINT_TELEA)
    soft = Image.fromarray(med).resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(1.5))
    base = sharp if sharp is not None else smp[len(smp) // 2][1]
    # weiter Rand um Carina: dünne Haarsträhnen und Brillenränder dürfen nicht durchscheinen
    k = max(3, int(w / 24) | 1)
    bmask = (segmenter.mask(base).point(lambda v: 255 if v > 60 else 0).filter(ImageFilter.MaxFilter(k))
             .filter(ImageFilter.GaussianBlur(w / 100)))
    plate = Image.composite(soft, base, bmask)
    if sharp is None:
        try:
            plate.save(cache)
        except OSError:
            pass
    return plate


def auto_poses(source: Path, w: int, h: int, segmenter: fx.Segmenter, n: int = 4) -> list:
    """Posen ohne Auswahl: Momente im Video, in denen Carina an möglichst verschiedenen Stellen ist."""
    smp = _samples(source, w, h, segmenter)
    cand = []
    for t, fr, m in smp:
        box = m.point(lambda v: 255 if v > 128 else 0).getbbox()
        if box:
            cand.append(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2, fr, m))
    if not cand:
        return []
    picks = [cand[0]]
    while len(picks) < min(n, len(cand)):
        best = max(cand, key=lambda c: min(abs(c[0] - p[0]) + abs(c[1] - p[1]) for p in picks))
        if best in picks:
            break
        picks.append(best)
    return [(fr, m) for _, _, fr, m in picks]


def load_stills(it: dict, source: Path | None, w: int, h: int, segmenter: fx.Segmenter | None) -> dict:
    """Leerer Raum und Posen für die Stativ-Tricks. Ohne eigene Aufnahme vom leeren Raum baut die App ihn selbst."""
    out: dict = {}
    if source is None or it.get("type") not in fx.NEEDS_STILLS:
        return out
    if it.get("bg_t") is not None:
        out["plate"] = grab_frame(source, float(it["bg_t"]), w, h)
    elif segmenter is not None:
        sharp = grab_frame(source, float(it.get("start", 0)), w, h)
        out["plate"] = auto_plate(source, w, h, segmenter, sharp)
    if it.get("type") == "flash" and segmenter is not None:
        poses = []
        for t in it.get("pose_t") or []:
            fr = grab_frame(source, float(t), w, h)
            if fr is not None:
                poses.append((fr, segmenter.mask(fr)))
        out["poses"] = poses or auto_poses(source, w, h, segmenter)
        out["own_plate"] = it.get("bg_t") is not None
    return out


def render_window(video: Path, it: dict, w: int, h: int, fps_str: str, face_box, out: Path,
                  segmenter: fx.Segmenter | None, on_frame: Callable[[], None], source: Path | None = None) -> None:
    fps = _fps_float(fps_str)
    d = it["e"] - it["s"]
    n = max(1, int(round(d * fps)))
    ff = media.ffmpeg()
    dec = subprocess.Popen([ff, "-hide_banner", "-loglevel", "error", "-ss", f"{it['s']:.3f}", "-i", str(video),
                            "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE, creationflags=media._NO_WINDOW)
    enc = subprocess.Popen([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{w}x{h}", "-r", fps_str, "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                            "-crf", "16", "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE,
                           creationflags=media._NO_WINDOW)
    ctx = fx.Ctx(w, h, face_box, it.get("_words"))
    ctx.stills = load_stills(it, source, w, h, segmenter)
    need_mask = it.get("type") in fx.NEEDS_MASK and segmenter is not None
    mask = None
    size = w * h * 3
    try:
        for k in range(n):
            raw = dec.stdout.read(size)
            if len(raw) < size:
                break
            frame = Image.frombuffer("RGB", (w, h), raw, "raw", "RGB", 0, 1)
            if need_mask and (mask is None or k % 2 == 0):  # Maske jedes 2. Bild (Bewegung ist langsam)
                mask = segmenter.mask(frame)
            img = fx.render_frame(frame, it, k / fps, d, ctx, mask)
            enc.stdin.write(np.asarray(img, dtype=np.uint8).tobytes())
            on_frame()
    finally:
        enc.stdin.close()
        dec.stdout.close()
        dec.wait()
        enc.wait()
    if enc.returncode != 0:
        raise UserError("An effect could not be rendered.")


def apply(video: Path, out: Path, items: list[dict], w: int, h: int, fps_str: str, face_box, encoder: list[str],
          work: Path, progress: Callable[[float, str], None], source: Path | None = None) -> None:
    """Effekte in `video` einbauen → `out`. items kommen aus prepare()."""
    if not items:
        video.replace(out)
        return
    fps = _fps_float(fps_str)
    total_frames = sum(max(1, int(round((it["e"] - it["s"]) * fps))) for it in items)
    done = [0]

    def tick():
        done[0] += 1
        if done[0] % 15 == 0:
            progress(0.85 * done[0] / total_frames, f"Building effects ({done[0] * 100 // total_frames}%)")

    seg = fx.Segmenter() if any(it.get("type") in fx.NEEDS_MASK | {"flash"} for it in items) else None
    clips: list[tuple[dict, Path]] = []
    try:
        for k, it in enumerate(items):
            p = work / f"fx_{k:03d}.mp4"
            render_window(video, it, w, h, fps_str, face_box, p, seg, tick, source)
            clips.append((it, p))
    finally:
        if seg:
            seg.close()
    # Zusammensetzen: jeder Clip genau an seiner Stelle über das Video
    inputs, parts, last = ["-i", str(video)], [], "0:v"
    for k, (it, p) in enumerate(clips, start=1):
        inputs += ["-i", str(p)]
        parts.append(f"[{k}:v]setpts=PTS-STARTPTS+{it['s']:.4f}/TB[f{k}]")
        parts.append(f"[{last}][f{k}]overlay=eof_action=pass:enable='between(t,{it['s']:.4f},{it['e'] + 0.02:.4f})'"
                     f"[o{k}]")
        last = f"o{k}"
    parts.append(f"[{last}]format=yuv420p[v]")
    script = work / "fx_filter.txt"
    script.write_text(";\n".join(parts), encoding="utf-8")
    progress(0.86, "Putting the effects into the video …")
    args = [*inputs, *media.filter_script_args(script), "-map", "[v]", "-map", "0:a?", *encoder, "-r", fps_str,
            "-c:a", "copy", "-movflags", "+faststart", str(out)]
    dur = float(media.probe(video)["duration"])
    media._run_with_progress(args, dur, lambda f: progress(0.86 + 0.14 * f, "Putting the effects into the video …"))
    for _, p in clips:
        try:
            p.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------- Zeitraffer / Zeitlupe

SPEEDS = (0.25, 0.5, 2.0, 4.0, 8.0)


def prepare_speed(ranges: list[dict], tmap, total: float) -> list[tuple[float, float, float, bool]]:
    """Tempo-Bereiche (Original-Zeit) → (Start, Ende, Faktor, stumm) in neuer Zeit, ohne Überlappung."""
    out = []
    for r in ranges or []:
        f = float(r.get("factor", 1))
        if f == 1 or f <= 0:
            continue
        s, e = tmap.clamp(r["start"]), min(total, tmap.clamp(r["end"]))
        if e - s >= 0.3:
            out.append((round(s, 3), round(e, 3), f, bool(r.get("mute", f > 2))))
    out.sort()
    clean = []
    for r in out:
        if clean and r[0] < clean[-1][1]:
            continue
        clean.append(r)
    return clean


def _atempo(f: float) -> str:
    """atempo kann nur 0,5–2 pro Stufe sauber: hintereinander schalten."""
    parts = []
    while f > 2.0:
        parts.append("atempo=2.0")
        f /= 2.0
    while f < 0.5:
        parts.append("atempo=0.5")
        f /= 0.5
    parts.append(f"atempo={f:.4f}")
    return ",".join(parts)


def apply_speed(video: Path, out: Path, ranges: list[tuple[float, float, float, bool]], encoder: list[str],
                fps_str: str, work: Path, progress: Callable[[float, str], None]) -> None:
    """Bereiche schneller (Zeitraffer) oder langsamer (Zeitlupe) machen. Ton: mit Tonhöhe erhalten oder stumm."""
    if not ranges:
        video.replace(out)
        return
    info = media.probe(video)
    total = float(info["duration"])
    has_audio = bool(info.get("has_audio"))
    pieces, t = [], 0.0
    for s, e, f, mute in ranges:
        if s > t + 0.02:
            pieces.append((t, s, 1.0, False))
        pieces.append((s, e, f, mute))
        t = e
    if total > t + 0.02:
        pieces.append((t, total, 1.0, False))
    parts, labels = [], ""
    for k, (s, e, f, mute) in enumerate(pieces):
        parts.append(f"[0:v]trim=start={s:.4f}:end={e:.4f},setpts=(PTS-STARTPTS)/{f:.4f},fps={fps_str}[v{k}]")
        if has_audio:
            a = f"[0:a]atrim=start={s:.4f}:end={e:.4f},asetpts=PTS-STARTPTS"
            if f != 1:
                a += "," + _atempo(f)
            if mute:
                a += ",volume=0"
            parts.append(a + f"[a{k}]")
            labels += f"[v{k}][a{k}]"
        else:
            labels += f"[v{k}]"
    parts.append(f"{labels}concat=n={len(pieces)}:v=1:a={1 if has_audio else 0}[v]" + ("[a]" if has_audio else ""))
    script = work / "speed_filter.txt"
    script.write_text(";\n".join(parts), encoding="utf-8")
    new_total = sum((e - s) / f for s, e, f, _ in pieces)
    args = ["-i", str(video), *media.filter_script_args(script), "-map", "[v]", *(["-map", "[a]"] if has_audio else []),
            *encoder, "-r", fps_str, *(["-c:a", "aac", "-b:a", "192k"] if has_audio else []),
            "-movflags", "+faststart", str(out)]
    media._run_with_progress(args, new_total, lambda f: progress(f, "Speeding up / slowing down …"))
