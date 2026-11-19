"""Video-Studio-Projekte: daten/studio/<sid>/ mit state.json, clips/, analysis/, renders/, work/.

Ablauf Drone Cutter: Clips hochladen → analysieren → planen → Vorschau rendern → Final rendern.
Schwere Arbeit läuft in einem eigenen Hintergrund-Thread (eine Warteschlange), mit Fortschritt im state.
"""
from __future__ import annotations

import json
import numpy as np
import queue
import re
import subprocess
import shutil
import threading
import time
import traceback
from pathlib import Path

from .. import media
from ..config import ROOT
from ..errors import UserError
from . import analysis, music, planner, render
from . import transitions as transmod

BASE = ROOT / "daten" / "studio"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".mts"}
MAX_FILE = 40 * 1024 ** 3        # 40 GB pro Clip
LENGTHS = [15, 30, 45, 60]

DEFAULT_SETTINGS = {
    "format": "reel",            # reel | youtube | youtube4k | both (Reel 9:16 + YouTube 16:9)
    "yt4k": False,               # bei "both": YouTube in 4K statt HD
    "length": 15,                # Reel: Sekunden
    "minutes": 3.0,              # YouTube: Minuten
    "location": "",
    "subtitle": "",
    "title": {"enabled": True, "font": "Montserrat ExtraLight", "size": 0.075, "spacing": 0.45,
              "spacing_start": 0.62, "y": 0.44, "color": [255, 255, 255], "animate": True, "start": 0.2,
              "duration": 3.0, "anim_in": "tracking", "anim_out": "fade", "youtube_card": True},
    "outro": {"enabled": False, "text": "", "duration": 2.5},
    "ramps": True,               # Zeitlupen-Rampen auf schönen Momenten
    "speedup": True,             # schnelle Fahrten doppelt so schnell
    "smooth_slowmo": True,       # Zeitlupe mit Zwischenbildern (optischer Fluss) im Final
    "transition": "auto",        # auto | cut | dissolve | … (transitions.TRANSITIONS)
    "transition_dur": 0.0,       # 0 = Standarddauer des Übergangs
    "grade": {"look": "vivid_travel", "strength": 1.0, "protect_skin": True, "match": True,
              "fx": {"sharpen": 15, "clarity": 10, "vignette": 0, "grain": 0}, "stabilize": ""},
    "captions": {"enabled": False, "style": "clean", "language": "auto", "drop_fillers": True},
    "normalize": True,           # Lautheit auf −14 LUFS (YouTube/Instagram)
    "music": {"mode": "none", "mood": "", "file": "", "gain_db": 0.0, "duck": True},
    "keep_audio": False,
    "codec": "h264",
    "seed": 0,
}
_lock = threading.RLock()


def pdir(sid: str) -> Path:
    if not re.fullmatch(r"[\w-]+", sid or ""):
        raise UserError("Unknown Video Studio project.")
    return BASE / sid


def _deep(base: dict, upd: dict) -> dict:
    out = dict(base)
    for k, v in (upd or {}).items():
        out[k] = _deep(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load(sid: str) -> dict:
    f = pdir(sid) / "state.json"
    if not f.exists():
        raise UserError("Unknown Video Studio project.")
    with _lock:
        st = json.loads(f.read_text(encoding="utf-8"))
    st["settings"] = _deep(DEFAULT_SETTINGS, st.get("settings") or {})
    # alte Projekte (ein Plan) → Pläne/Ergebnisse je Format
    st.setdefault("plans", {})
    if st.get("plan"):
        st["plans"].setdefault(st["plan"].get("format", "reel"), st["plan"])
    st.pop("plan", None)
    r = st.get("renders") or {}
    if "preview" in r or "final" in r:
        fmt = next(iter(st["plans"]), "reel")
        r = {fmt: {k: v for k, v in r.items() if k in ("preview", "final")}}
    st["renders"] = r
    job = st.get("job") or {}
    if job.get("status") in ("waiting", "running") and (_worker is None or not _worker.is_alive()):
        job.update(status="error", error="The app was restarted while working – please press the button again.")
    st["sid"] = sid
    return st


def save(sid: str, st: dict) -> dict:
    with _lock:
        d = pdir(sid)
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "state.json.tmp"
        tmp.write_text(json.dumps({k: v for k, v in st.items() if k != "sid"}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        tmp.replace(d / "state.json")
    st["sid"] = sid
    return st


def update(sid: str, fn) -> dict:
    with _lock:
        st = load(sid)
        fn(st)
        return save(sid, st)


def create(name: str = "") -> dict:
    sid = "vs-" + time.strftime("%Y%m%d-%H%M%S")
    while pdir(sid).exists():
        sid += "x"
    for sub in ("clips", "analysis", "renders", "work"):
        (pdir(sid) / sub).mkdir(parents=True, exist_ok=True)
    return save(sid, {"name": name.strip() or "Drone video", "created": time.time(), "clips": [],
                      "settings": dict(DEFAULT_SETTINGS), "plans": {}, "renders": {}, "job": None})


def list_all() -> list[dict]:
    out = []
    for f in sorted(BASE.glob("vs-*/state.json"), reverse=True):
        try:
            st = json.loads(f.read_text(encoding="utf-8"))
            out.append({"sid": f.parent.name, "name": st.get("name", ""), "clips": len(st.get("clips", [])),
                        "has_final": any(isinstance(v, dict) and v.get("final")
                                         for v in (st.get("renders") or {}).values())})
        except (OSError, ValueError):
            continue
    return out


def delete(sid: str) -> None:
    shutil.rmtree(pdir(sid), ignore_errors=True)


# ---------------------------------------------------------------- Clips

def write_chunk(sid: str, upload_id: str, offset: int, data: bytes) -> int:
    if not re.fullmatch(r"[\w-]{4,64}", upload_id):
        raise UserError("Bad upload.")
    f = pdir(sid) / "clips" / f"{upload_id}.part"
    f.parent.mkdir(parents=True, exist_ok=True)
    size = f.stat().st_size if f.exists() else 0
    if offset != size:   # Wiederaufnahme: Client schickt ab der richtigen Stelle
        return size
    if size + len(data) > MAX_FILE:
        f.unlink(missing_ok=True)
        raise UserError("This clip is larger than 40 GB.")
    with f.open("ab") as fh:
        fh.write(data)
    return size + len(data)


def finish_upload(sid: str, upload_id: str, name: str) -> dict:
    d = pdir(sid) / "clips"
    part = d / f"{upload_id}.part"
    ext = Path(name).suffix.lower()
    if not part.exists():
        raise UserError("Upload not found – please try again.")
    if ext not in VIDEO_EXT:
        part.unlink(missing_ok=True)
        raise UserError("Please upload a video (mp4, mov, m4v, mkv).")
    cid = f"c{int(time.time() * 1000) % 10_000_000}"
    dst = d / f"{cid}{ext}"
    part.replace(dst)
    try:
        info = media.probe(dst)
    except UserError:
        dst.unlink(missing_ok=True)
        raise
    media.thumbnail(dst, d / f"{cid}.jpg", min(info["duration"] / 3, 5.0))

    def add(st):
        st["clips"].append({"id": cid, "name": name, "file": dst.name, "info": info, "thumb": f"{cid}.jpg",
                            "analysed": False})
        st["plans"] = {}
    return update(sid, add)


def reorder(sid: str, order: list[str]) -> dict:
    def fn(st):
        by = {c["id"]: c for c in st["clips"]}
        st["clips"] = [by[i] for i in order if i in by] + [c for c in st["clips"] if c["id"] not in order]
        st["plans"] = {}
    return update(sid, fn)


def remove_clip(sid: str, cid: str) -> dict:
    def fn(st):
        for c in [c for c in st["clips"] if c["id"] == cid]:
            for f in (c["file"], c.get("thumb", "")):
                if f:
                    (pdir(sid) / "clips" / f).unlink(missing_ok=True)
            (pdir(sid) / "analysis" / f"{cid}.json").unlink(missing_ok=True)
        st["clips"] = [c for c in st["clips"] if c["id"] != cid]
        st["plans"] = {}
    return update(sid, fn)


def set_settings(sid: str, s: dict) -> dict:
    def fn(st):
        st["settings"] = _deep(st["settings"], s)
    return update(sid, fn)


def file(sid: str, sub: str, name: str) -> Path:
    if sub not in ("clips", "renders", "music", "looks") or not re.fullmatch(r"[\w.-]+", name):
        raise UserError("File not found.")
    f = (pdir(sid) / "work" / "looks" / name) if sub == "looks" else (pdir(sid) / sub / name)
    if not f.exists():
        raise UserError("File not found.")
    return f


def upload_music(sid: str, name: str, data: bytes) -> dict:
    ext = Path(name).suffix.lower()
    if ext not in music.EXT:
        raise UserError("Please upload an audio file (mp3, wav, m4a).")
    d = pdir(sid) / "music"
    d.mkdir(exist_ok=True)
    fname = re.sub(r"[^\w.-]", "_", Path(name).stem)[:60] + ext
    (d / fname).write_bytes(data)
    from . import beats
    a = beats.analyse(d / fname)

    def fn(st):
        st["own_music"] = {"file": fname, "title": Path(name).stem, "bpm": a["bpm"], "duration": a["duration"],
                           "beats": a["beats"], "energy": a["energy"], "path": str(d / fname), "source": "upload"}
        st["settings"]["music"]["mode"] = "own"
        st["plans"] = {}
    return update(sid, fn)


# ---------------------------------------------------------------- Arbeit (Hintergrund)

_q: "queue.Queue[tuple[str, str]]" = queue.Queue()
_worker: threading.Thread | None = None


def _set_job(sid: str, **kw) -> None:
    def fn(st):
        job = st.get("job") or {}
        job.update(kw)
        st["job"] = job
    update(sid, fn)


def enqueue(sid: str, kind: str) -> dict:
    global _worker
    st = load(sid)
    if not st["clips"]:
        raise UserError("Please upload at least one clip first.")
    job = st.get("job") or {}
    if job.get("status") in ("waiting", "running"):
        raise UserError("Video Studio is already working on this project – please wait.")
    media.CANCEL.discard(f"studio:{sid}")
    _set_job(sid, kind=kind, status="waiting", progress=0.0, message="Waiting …", error=None)
    _q.put((sid, kind))
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=_work, daemon=True, name="video-studio")
        _worker.start()
    return load(sid)


def cancel(sid: str) -> dict:
    media.CANCEL.add(f"studio:{sid}")
    return load(sid)


def _work() -> None:
    while True:
        sid, kind = _q.get()
        media.set_job(f"studio:{sid}")
        try:
            _set_job(sid, status="running", message="Starting …")
            if kind == "generate":
                generate(sid)
            elif kind == "final":
                render_final(sid)
            elif kind == "preview":
                preview_again(sid)
            _set_job(sid, status="done", progress=1.0, message="Done")
        except media.Cancelled:
            _set_job(sid, status="cancelled", message="Cancelled")
        except UserError as exc:
            _set_job(sid, status="error", error=str(exc), message="")
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            _set_job(sid, status="error", error=f"Something went wrong: {exc}", message="")
        finally:
            media.set_job(None)
            media.CANCEL.discard(f"studio:{sid}")


def _progress(sid: str, a: float, b: float, msg: str):
    last = [0.0]

    def p(f: float):
        v = a + (b - a) * max(0.0, min(1.0, f))
        if v - last[0] >= 0.01 or f >= 1:
            last[0] = v
            _set_job(sid, progress=round(v, 3), message=msg)
    return p


def analyse_all(sid: str, a: float = 0.0, b: float = 0.35) -> list[dict]:
    st = load(sid)
    d = pdir(sid)
    out = []
    n = len(st["clips"])
    for k, c in enumerate(st["clips"]):
        media.check_cancel()
        f = d / "analysis" / f"{c['id']}.json"
        if f.exists():   # ältere Analyse ohne Mini-Bilder → einmal neu
            try:
                if json.loads(f.read_text(encoding="utf-8")).get("version", 1) < analysis.VERSION:
                    f.unlink()
            except (OSError, ValueError):
                f.unlink(missing_ok=True)
        if not f.exists():
            _set_job(sid, progress=round(a + (b - a) * k / n, 3), message=f"Looking at clip {k + 1} of {n} …")
            mins = max(1, round(c["info"]["duration"] / 60))
            res = analysis.analyse(c["id"], d / "clips" / c["file"], c["info"],
                                   _progress(sid, a + (b - a) * k / n, a + (b - a) * (k + 1) / n,
                                             f"Looking at clip {k + 1} of {n} ({mins} min of video) …"))
            f.write_text(json.dumps(res), encoding="utf-8")

            def mark(s, cid=c["id"]):
                for cc in s["clips"]:
                    if cc["id"] == cid:
                        cc["analysed"] = True
            update(sid, mark)
        out.append(analysis.refresh_moments(json.loads(f.read_text(encoding="utf-8"))))
    return out


def formats(s: dict) -> list[str]:
    if s["format"] == "both":
        return ["reel", "youtube4k" if s.get("yt4k") else "youtube"]
    return [s["format"] if s["format"] in render.FORMATS else "reel"]


def target_duration(s: dict, fmt: str | None = None) -> float:
    if (fmt or s["format"]) == "reel":
        return float(s["length"] if s["length"] in LENGTHS else 15)
    return max(0.5, min(60.0, float(s.get("minutes") or 3))) * 60.0


def _music_for(st: dict, duration: float, fmt: str = "reel") -> dict | None:
    m = st["settings"]["music"]
    if m.get("mode") == "none":
        return None
    if m.get("mode") == "own" and st.get("own_music"):
        tr = dict(st["own_music"])
    elif m.get("mode") == "file" and m.get("file"):
        tr = next((t for t in music.library() if t["file"] == m["file"]), None)
    else:
        tr = music.pick(duration, m.get("mood") or ("cinematic" if fmt != "reel" else None),
                        seed=int(st["settings"].get("seed", 0)))
    if not tr:
        return None
    start = music.best_start(tr, duration)
    return {"file": tr["file"], "title": tr.get("title", tr["file"]), "path": tr.get("path", ""), "start": start,
            "bpm": tr.get("bpm"), "gain_db": m.get("gain_db", 0.0), "duck": m.get("duck", True),
            "beats": music.beats_in_window(tr, start, duration), "source": tr.get("source", "library")}


def _title(s: dict, mode: str) -> dict:
    title = dict(s["title"])
    title["text"] = s.get("location", "")
    title["subtitle"] = s.get("subtitle", "")
    if mode != "reel":
        title["enabled"] = bool(title.get("enabled", True) and title.get("youtube_card", True))
    return title


def _transitions(s: dict, shots: list[dict], mode: str) -> list[dict]:
    return transmod.choose(shots, mode, s.get("transition", "auto"), float(s.get("transition_dur") or 0) or None,
                           int(s.get("seed", 0)))


def make_plan(sid: str, analyses: list[dict], fmt: str) -> dict:
    st = load(sid)
    s = st["settings"]
    dur = target_duration(s, fmt)
    mode = "reel" if fmt == "reel" else "youtube"
    key = "moments" if mode == "reel" else "moments_long"
    moments = [m for a in analyses for m in (a.get(key) or a["moments"])]
    fps = render.out_fps([c["info"] for c in st["clips"]])
    mus = _music_for(st, dur, fmt)
    title = _title(s, mode)
    shots = planner.plan(moments, dur, mode, mus["beats"] if mus else None, fps, int(s.get("seed", 0)),
                         title_len=float(title.get("duration", 3)) if title.get("text") and title.get("enabled") else 0.0,
                         # Rampen/2× nur im Reel – YouTube bleibt ruhig in Originaltempo (wie die Referenz)
                         ramps=bool(s.get("ramps", True)) and mode == "reel",
                         speedup=bool(s.get("speedup", True)) and mode == "reel")
    if mode == "youtube":   # YouTube erzählt: Reihenfolge der Clips und Zeit im Clip (wie geflogen)
        shots = _story_order(shots, [c["id"] for c in st["clips"]])
    shot_dicts = [x.to_dict() for x in shots]
    _auto_shot_settings(sid, st, shot_dicts, analyses, fmt)
    warnings = []
    usable = sum(m["dur"] for a in analyses for m in a["moments"] if m["score"] >= 0.55 * max(
        [mm["score"] for aa in analyses for mm in aa["moments"]] or [1]))
    if any(x.speed < 0.99 and not x.ramp for x in shots) or usable < dur * 0.9:
        warnings.append(f"Your clips have about {int(usable)} s of good footage for a {int(dur)} s video, so some shots "
                        "play in slow motion or repeat. Choose a shorter length or add more clips.")
    plan = {"format": fmt, "duration": dur, "warnings": warnings, "fps": fps, "shots": shot_dicts,
            "transitions": _transitions(s, shot_dicts, mode),
            "transition_key": [s.get("transition", "auto"), s.get("transition_dur", 0)],
            "grade": s["grade"], "title": title, "outro": s.get("outro"),
            "music": {k: v for k, v in (mus or {}).items() if k != "beats"},
            "beats": (mus or {}).get("beats", []), "keep_audio": s.get("keep_audio", False), "codec": s.get("codec"),
            "smooth_slowmo": s.get("smooth_slowmo", True), "created": time.time()}
    update(sid, lambda st_: st_["plans"].__setitem__(fmt, plan))
    return plan


def grab(sid: str, clip_id: str, t: float, width: int = 480):
    """Ein Bild aus einem Clip (für Auto-Ausschnitt und Filter-Vorschau)."""
    import io
    from PIL import Image
    st = load(sid)
    c = next(c for c in st["clips"] if c["id"] == clip_id)
    r = subprocess.run([media.ffmpeg(), "-hide_banner", "-loglevel", "error", "-ss", f"{max(0.0, t):.2f}", "-i",
                        str(pdir(sid) / "clips" / c["file"]), "-frames:v", "1",
                        "-vf", f"{media.sdr_filter(c['info'])}scale={width}:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                       capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    return Image.open(io.BytesIO(r.stdout)).convert("RGB")


def _auto_shot_settings(sid: str, st: dict, shots: list[dict], analyses: list[dict], fmt: str) -> None:
    """Auto-Reframe (Hochkant: Ausschnitt dort, wo am meisten los ist) + Belichtung der Aufnahmen angleichen."""
    by_clip = {a["clip"]: a for a in analyses}
    brights = []
    for sh in shots:
        a = by_clip.get(sh["clip"])
        c = sh["src_in"] + sh["src_dur"] / 2
        b = None
        if a and a.get("samples"):
            b = min(a["samples"], key=lambda x: abs(x["t"] - c))["bright"]
        brights.append(b)
    vals = sorted(b for b in brights if b)
    med = vals[len(vals) // 2] if vals else None
    for sh, b in zip(shots, brights):
        if med and b and b > 0.03:
            import math
            d = max(-0.4, min(0.4, math.log2(med / b) * 0.6))
            if abs(d) > 0.05:
                sh["auto"] = {"exposure": round(d, 3)}
        if fmt == "reel":
            img = grab(sid, sh["clip"], sh["src_in"] + sh["src_dur"] / 2, 480)
            if img is not None:
                sh["xpos"] = analysis.best_xpos(img, 9 / 16)


def _story_order(shots: list, clip_order: list[str]) -> list:
    """Aufnahmen nach Clip-Reihenfolge und Zeit im Clip sortieren; Längen bleiben in Taktreihenfolge."""
    lens = [x.dur for x in shots]
    rank = {c: i for i, c in enumerate(clip_order)}
    ordered = sorted(shots, key=lambda x: (rank.get(x.clip, 99), x.src_in))
    t = 0.0
    for x, L in zip(ordered, lens):
        ratio = x.src_dur / x.dur if x.dur else 1.0
        x.dur = L
        x.src_dur = round(L * ratio, 3)
        x.t0 = round(t, 6)
        t += L
    return ordered


def _clips(st: dict) -> dict:
    d = pdir(st["sid"])
    return {c["id"]: {"path": d / "clips" / c["file"], "info": c["info"]} for c in st["clips"]}


def _live_plan(st: dict, fmt: str) -> dict:
    """Plan mit den aktuellen Einstellungen für Farbe, Titel, Abspann, Musik-Lautstärke, Übergänge."""
    s = st["settings"]
    plan = dict(st["plans"][fmt])
    mode = "reel" if fmt == "reel" else "youtube"
    plan["grade"], plan["codec"] = s["grade"], s.get("codec", "h264")
    plan["title"] = _title(s, mode)
    plan["outro"] = s.get("outro")
    plan["keep_audio"] = s.get("keep_audio", False)
    plan["smooth_slowmo"] = s.get("smooth_slowmo", True)
    plan["normalize"] = s.get("normalize", True)
    plan["captions"] = s.get("captions")
    key = [s.get("transition", "auto"), s.get("transition_dur", 0)]
    if plan.get("transition_key") != key and not plan.get("trans_edited"):   # Übergangs-Einstellung geändert
        plan["transitions"] = _transitions(s, plan["shots"], mode)
    if plan.get("music"):
        plan["music"] = {**plan["music"], "gain_db": s["music"].get("gain_db", 0.0)}
    return plan


def _render_previews(sid: str, fmts: list[str], a: float, b: float) -> None:
    for i, fmt in enumerate(fmts):
        st = load(sid)
        plan = _live_plan(st, fmt)
        out = pdir(sid) / "renders" / f"preview_{fmt}_{int(time.time())}.mp4"
        for old in (pdir(sid) / "renders").glob(f"preview_{fmt}_*.mp4"):
            old.unlink(missing_ok=True)
        lo, hi = a + (b - a) * i / len(fmts), a + (b - a) * (i + 1) / len(fmts)
        label = {"reel": "vertical reel", "youtube": "landscape video", "youtube4k": "landscape video"}[fmt]
        res = render.render(plan, _clips(st), pdir(sid) / "work", out, "preview",
                            _progress(sid, lo, hi, f"Making the preview ({label}) …"))
        update(sid, lambda s, f=fmt, r=res: s["renders"].setdefault(f, {}).__setitem__("preview", r))


def generate(sid: str) -> None:
    analyses = analyse_all(sid)
    st = load(sid)
    fmts = formats(st["settings"])
    _set_job(sid, message="Choosing the best moments …", progress=0.37)
    update(sid, lambda s: (s.__setitem__("plans", {}), s.__setitem__("renders", {})))
    for fmt in fmts:
        make_plan(sid, analyses, fmt)
    _render_previews(sid, fmts, 0.4, 1.0)


def preview_again(sid: str) -> None:
    """Nach Änderungen in der Zeitleiste: Vorschau aus den vorhandenen Plänen neu rendern (ohne neu zu planen)."""
    st = load(sid)
    fmts = [f for f in formats(st["settings"]) if f in st["plans"]] or list(st["plans"])
    if not fmts:
        return generate(sid)
    _render_previews(sid, fmts, 0.0, 1.0)


def render_final(sid: str) -> None:
    st = load(sid)
    fmts = formats(st["settings"])
    if not all(f in st["plans"] for f in fmts):
        generate(sid)
        st = load(sid)
    for i, fmt in enumerate(fmts):
        st = load(sid)
        plan = _live_plan(st, fmt)
        name = re.sub(r"[^\w-]+", "_", (st["settings"].get("location") or st["name"]).strip()).strip("_") or "video"
        tag = {"reel": "reel_9x16", "youtube": "youtube_16x9", "youtube4k": "youtube_4k"}[fmt]
        out = pdir(sid) / "renders" / f"{name}_{tag}_{int(plan['duration'])}s_{int(time.time())}.mp4"
        res = render.render(plan, _clips(st), pdir(sid) / "work", out, "final",
                            _progress(sid, i / len(fmts), (i + 1) / len(fmts),
                                      f"Rendering the final video {i + 1} of {len(fmts)} …"))
        from .. import outbox
        outbox.save("reels" if fmt == "reel" else "youtube", out, out.name)
        update(sid, lambda s, f=fmt, r=res: s["renders"].setdefault(f, {}).__setitem__("final", r))


# ---------------------------------------------------------------- Zeitleiste (einzelne Aufnahmen ändern)

def _src_window(center: float, need: float, clip_dur: float) -> float:
    start = center - need / 2
    return round(max(0.0, min(start, clip_dur - need - 0.05)), 3)


def edit_shot(sid: str, fmt: str, k: int, action: str, value: str | float | None = None) -> dict:
    """action: swap (andere Aufnahme) | left | right (verschieben) | speed (1, 0.5, 2 …) | ramp (hero/…/"")
    | transition (Übergang NACH dieser Aufnahme)."""
    from . import speed as speedmod
    st = load(sid)
    plan = st["plans"].get(fmt)
    if not plan or not (0 <= k < len(plan["shots"])):
        raise UserError("Please make the preview first.")
    shots = plan["shots"]
    clip_dur = {c["id"]: c["info"]["duration"] for c in st["clips"]}
    mode = "reel" if fmt == "reel" else "youtube"

    def refit(sh: dict) -> None:
        need = sh["dur"] * speedmod.mean_speed(sh.get("ramp") or None, sh.get("speed", 1.0))
        center = sh["src_in"] + sh["src_dur"] / 2
        sh["src_dur"] = round(min(need, clip_dur.get(sh["clip"], need) - 0.1), 3)
        sh["src_in"] = _src_window(center, sh["src_dur"], clip_dur.get(sh["clip"], 1e9))

    if action in ("left", "right"):
        j = k - 1 if action == "left" else k + 1
        if not 0 <= j < len(shots):
            raise UserError("This shot is already at the edge.")
        a, b = shots[k], shots[j]
        for key in ("clip", "src_in", "src_dur", "speed", "score", "hero", "transit", "direction", "ramp"):
            a[key], b[key] = b.get(key), a.get(key)
        refit(a)
        refit(b)
    elif action == "speed":
        shots[k]["speed"] = max(0.25, min(4.0, float(value or 1)))
        shots[k]["ramp"] = ""
        refit(shots[k])
    elif action == "ramp":
        shots[k]["ramp"] = str(value or "") if (value or "") in speedmod.RAMPS else ""
        shots[k]["speed"] = 1.0
        refit(shots[k])
    elif action == "transition":
        if k >= len(shots) - 1:
            raise UserError("There is no cut after the last shot.")
        tid = str(value or "cut")
        t = transmod.TRANSITIONS.get(tid, transmod.TRANSITIONS["cut"])
        d = 0.0 if tid == "cut" else min(t["dur"], 0.45 * min(shots[k]["dur"], shots[k + 1]["dur"]))
        plan.setdefault("transitions", [{"id": "cut", "dur": 0.0}] * (len(shots) - 1))[k] = {"id": tid, "dur": round(d, 3)}
        plan["trans_edited"] = True
    elif action == "set":   # Regler einer Aufnahme (Farbe, Effekte, Look, Ausschnitt, Zoom, Stabilisieren)
        allowed = {"adjust", "fx", "look", "strength", "xpos", "ypos", "zoom", "zoom_end", "stabilize", "mask", "ai"}
        for key2, v2 in (value or {}).items() if isinstance(value, dict) else []:
            if key2 in allowed:
                if v2 is None or v2 == "":
                    shots[k].pop(key2, None)
                else:
                    shots[k][key2] = v2
    elif action == "apply_all":   # Farbe/Effekte dieser Aufnahme auf alle übertragen
        src_sh = shots[k]
        for other in shots:
            for key2 in ("adjust", "fx", "look", "strength", "stabilize", "mask"):
                if key2 in src_sh:
                    other[key2] = json.loads(json.dumps(src_sh[key2]))
                else:
                    other.pop(key2, None)
    elif action == "add_text":
        v = value if isinstance(value, dict) else {}
        tpl = v.get("tpl", "caption")
        start = float(v.get("t0", shots[k]["t0"]))
        dur = float(v.get("dur", min(3.0, plan["duration"] - start)))
        plan.setdefault("texts", []).append({"tpl": tpl, "text": str(v.get("text", "")), "t0": round(start, 3),
                                             "dur": round(max(0.5, dur), 3)})
    elif action == "remove_text":
        texts = plan.get("texts") or []
        if 0 <= int(value or 0) < len(texts):
            texts.pop(int(value or 0))
    elif action == "swap":
        analyses = [analysis.refresh_moments(json.loads(f.read_text(encoding="utf-8")))
                    for f in sorted((pdir(sid) / "analysis").glob("*.json"))]
        key = "moments" if mode == "reel" else "moments_long"
        cands = sorted((m for a in analyses for m in (a.get(key) or a["moments"])), key=lambda m: m["score"], reverse=True)
        cur = shots[k]
        used = [(x["clip"], x["src_in"], x["src_in"] + x["src_dur"]) for x in shots]
        need = cur["dur"] * speedmod.mean_speed(cur.get("ramp") or None, cur.get("speed", 1.0))
        tried = set(cur.get("swapped") or [])
        pick = None
        for m in cands:
            if m["dur"] < need or f"{m['clip']}@{m['start']}" in tried:
                continue
            c = m["start"] + m["dur"] / 2
            if any(cl == m["clip"] and abs(c - (a0 + a1) / 2) < max(4.0, need * 1.5) for cl, a0, a1 in used):
                continue
            pick = m
            break
        if pick is None:
            raise UserError("No other good shot left – add more clips or choose a shorter length.")
        cur.update(clip=pick["clip"], src_dur=round(need, 3),
                   src_in=_src_window(pick["start"] + pick["dur"] / 2, need, clip_dur.get(pick["clip"], 1e9)),
                   score=pick["score"], hero=pick.get("hero", False), transit=pick.get("transit", False),
                   direction=pick.get("direction", ""), swapped=sorted(tried | {f"{pick['clip']}@{pick['start']}"}))
    else:
        raise UserError("Unknown action.")
    plan["edited"] = True
    update(sid, lambda s: s["plans"].__setitem__(fmt, plan))
    return load(sid)


def looks_preview(sid: str, fmt: str, k: int, strength: float = 1.0) -> list[dict]:
    """Filter-Raster: Carinas eigenes Bild (Aufnahme k) mit jedem Look – zum Ausprobieren vor dem Rendern."""
    from PIL import Image
    from . import color as colormod
    thumb = shot_thumb(sid, fmt, k)
    img = Image.open(thumb).convert("RGB")
    d = pdir(sid) / "work" / "looks"
    d.mkdir(parents=True, exist_ok=True)
    out = []
    names = list(colormod.PRESETS) + [f"file:{f.name}" for f in sorted((pdir(sid) / "luts").glob("*.cube"))]
    for look in names:
        f = d / f"{thumb.stem}_{re.sub(r'[^\w.-]', '_', look)}_{int(strength * 100)}.jpg"
        if not f.exists():
            if look.startswith("file:"):
                src = colormod.read_cube(pdir(sid) / "luts" / look[5:])
                n = src.shape[0]
                x = np.linspace(0, 1, n)
                ident = np.stack(np.meshgrid(x, x, x, indexing="ij")[::-1], -1)
                im = colormod.preview_image(img, cube=np.clip(ident + (src - ident) * strength, 0, 1))
            else:
                im = colormod.preview_image(img, colormod.params_for(look, strength))
            im.save(f, quality=86)
        out.append({"look": look, "file": f.name})
    return out


def import_lut(sid: str, name: str, data: bytes) -> dict:
    from . import color as colormod
    d = pdir(sid) / "luts"
    d.mkdir(exist_ok=True)
    fname = re.sub(r"[^\w.-]", "_", Path(name).stem)[:50] + ".cube"
    f = d / fname
    f.write_bytes(data)
    try:
        colormod.read_cube(f)
    except ValueError as exc:
        f.unlink(missing_ok=True)
        raise UserError("This file is not a 3D .cube LUT.") from exc
    return load(sid)


def shot_thumb(sid: str, fmt: str, k: int) -> Path:
    """Kleines Vorschaubild einer Aufnahme (Mitte des Ausschnitts), zwischengespeichert."""
    st = load(sid)
    plan = st["plans"].get(fmt)
    if not plan or not (0 <= k < len(plan["shots"])):
        raise UserError("File not found.")
    sh = plan["shots"][k]
    c = next(c for c in st["clips"] if c["id"] == sh["clip"])
    t = sh["src_in"] + sh["src_dur"] / 2
    d = pdir(sid) / "work" / "thumbs"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{sh['clip']}_{int(t * 10)}.jpg"
    if not f.exists():
        media.run([media.ffmpeg(), "-hide_banner", "-y", "-ss", f"{t:.2f}", "-i", str(pdir(sid) / "clips" / c["file"]),
                   "-frames:v", "1", "-vf", "scale=320:-2", "-q:v", "5", str(f)])
    if not f.exists():
        raise UserError("File not found.")
    return f
