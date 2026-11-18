"""Video-Studio-Projekte: daten/studio/<sid>/ mit state.json, clips/, analysis/, renders/, work/.

Ablauf Drone Cutter: Clips hochladen → analysieren → planen → Vorschau rendern → Final rendern.
Schwere Arbeit läuft in einem eigenen Hintergrund-Thread (eine Warteschlange), mit Fortschritt im state.
"""
from __future__ import annotations

import json
import queue
import re
import shutil
import threading
import time
import traceback
from pathlib import Path

from .. import media
from ..config import ROOT
from ..errors import UserError
from . import analysis, music, planner, render

BASE = ROOT / "daten" / "studio"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".mts"}
MAX_FILE = 40 * 1024 ** 3        # 40 GB pro Clip
LENGTHS = [15, 30, 45, 60]

DEFAULT_SETTINGS = {
    "format": "reel",            # reel | youtube | youtube4k
    "length": 15,                # Reel: Sekunden
    "minutes": 3.0,              # YouTube: Minuten
    "location": "",
    "subtitle": "",
    "title": {"enabled": True, "font": "Montserrat ExtraLight", "size": 0.075, "spacing": 0.45,
              "spacing_start": 0.62, "y": 0.44, "color": [255, 255, 255], "animate": True, "start": 0.2,
              "duration": 3.0},
    "grade": {"look": "vivid_travel", "strength": 1.0, "protect_skin": True},
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
                      "settings": dict(DEFAULT_SETTINGS), "plan": None, "renders": {}, "job": None})


def list_all() -> list[dict]:
    out = []
    for f in sorted(BASE.glob("vs-*/state.json"), reverse=True):
        try:
            st = json.loads(f.read_text(encoding="utf-8"))
            out.append({"sid": f.parent.name, "name": st.get("name", ""), "clips": len(st.get("clips", [])),
                        "has_final": bool((st.get("renders") or {}).get("final"))})
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
        st["plan"] = None
    return update(sid, add)


def reorder(sid: str, order: list[str]) -> dict:
    def fn(st):
        by = {c["id"]: c for c in st["clips"]}
        st["clips"] = [by[i] for i in order if i in by] + [c for c in st["clips"] if c["id"] not in order]
        st["plan"] = None
    return update(sid, fn)


def remove_clip(sid: str, cid: str) -> dict:
    def fn(st):
        for c in [c for c in st["clips"] if c["id"] == cid]:
            for f in (c["file"], c.get("thumb", "")):
                if f:
                    (pdir(sid) / "clips" / f).unlink(missing_ok=True)
            (pdir(sid) / "analysis" / f"{cid}.json").unlink(missing_ok=True)
        st["clips"] = [c for c in st["clips"] if c["id"] != cid]
        st["plan"] = None
    return update(sid, fn)


def set_settings(sid: str, s: dict) -> dict:
    def fn(st):
        st["settings"] = _deep(st["settings"], s)
    return update(sid, fn)


def file(sid: str, sub: str, name: str) -> Path:
    if sub not in ("clips", "renders", "music") or not re.fullmatch(r"[\w.-]+", name):
        raise UserError("File not found.")
    f = pdir(sid) / sub / name
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
        st["plan"] = None
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
        if not f.exists():
            _set_job(sid, progress=round(a + (b - a) * k / n, 3), message=f"Looking at clip {k + 1} of {n} …")
            res = analysis.analyse(c["id"], d / "clips" / c["file"], c["info"])
            f.write_text(json.dumps(res), encoding="utf-8")

            def mark(s, cid=c["id"]):
                for cc in s["clips"]:
                    if cc["id"] == cid:
                        cc["analysed"] = True
            update(sid, mark)
        out.append(analysis.refresh_moments(json.loads(f.read_text(encoding="utf-8"))))
    return out


def target_duration(s: dict) -> float:
    if s["format"] == "reel":
        return float(s["length"] if s["length"] in LENGTHS else 15)
    return max(0.5, min(60.0, float(s.get("minutes") or 3))) * 60.0


def _music_for(st: dict, duration: float) -> dict | None:
    m = st["settings"]["music"]
    if m.get("mode") == "none":
        return None
    if m.get("mode") == "own" and st.get("own_music"):
        tr = dict(st["own_music"])
    elif m.get("mode") == "file" and m.get("file"):
        tr = next((t for t in music.library() if t["file"] == m["file"]), None)
    else:
        tr = music.pick(duration, m.get("mood") or ("cinematic" if st["settings"]["format"] != "reel" else None),
                        seed=int(st["settings"].get("seed", 0)))
    if not tr:
        return None
    start = music.best_start(tr, duration)
    return {"file": tr["file"], "title": tr.get("title", tr["file"]), "path": tr.get("path", ""), "start": start,
            "bpm": tr.get("bpm"), "gain_db": m.get("gain_db", 0.0), "duck": m.get("duck", True),
            "beats": music.beats_in_window(tr, start, duration), "source": tr.get("source", "library")}


def make_plan(sid: str, analyses: list[dict]) -> dict:
    st = load(sid)
    s = st["settings"]
    dur = target_duration(s)
    mode = "reel" if s["format"] == "reel" else "youtube"
    key = "moments" if mode == "reel" else "moments_long"
    moments = [m for a in analyses for m in (a.get(key) or a["moments"])]
    fps = render.out_fps([c["info"] for c in st["clips"]])
    mus = _music_for(st, dur)
    title = dict(s["title"])
    title["text"] = s.get("location", "")
    title["subtitle"] = s.get("subtitle", "")
    if mode != "reel" and not title.get("youtube", False):
        title["enabled"] = bool(s["title"].get("youtube_card", False))
    shots = planner.plan(moments, dur, mode, mus["beats"] if mus else None, fps, int(s.get("seed", 0)),
                         title_len=float(title.get("duration", 3)) if title.get("text") else 0.0)
    warnings = []
    usable = sum(m["dur"] for a in analyses for m in a["moments"] if m["score"] >= 0.55 * max(
        [mm["score"] for aa in analyses for mm in aa["moments"]] or [1]))
    if any(x.speed < 0.99 for x in shots) or usable < dur * 0.9:
        warnings.append(f"Your clips have about {int(usable)} s of good footage for a {int(dur)} s video, so some shots "
                        "play in slow motion or repeat. Choose a shorter length or add more clips.")
    plan = {"format": s["format"], "duration": dur, "warnings": warnings, "fps": fps, "shots": [x.to_dict() for x in shots],
            "grade": s["grade"], "title": title, "music": {k: v for k, v in (mus or {}).items() if k != "beats"},
            "beats": (mus or {}).get("beats", []), "keep_audio": s.get("keep_audio", False), "codec": s.get("codec"),
            "created": time.time()}
    update(sid, lambda st_: st_.__setitem__("plan", plan))
    return plan


def _clips(st: dict) -> dict:
    d = pdir(st["sid"])
    return {c["id"]: {"path": d / "clips" / c["file"], "info": c["info"]} for c in st["clips"]}


def generate(sid: str) -> dict:
    analyses = analyse_all(sid)
    _set_job(sid, message="Choosing the best moments …", progress=0.37)
    plan = make_plan(sid, analyses)
    st = load(sid)
    out = pdir(sid) / "renders" / f"preview_{int(time.time())}.mp4"
    for old in (pdir(sid) / "renders").glob("preview_*.mp4"):
        old.unlink(missing_ok=True)
    res = render.render(plan, _clips(st), pdir(sid) / "work", out, "preview",
                        _progress(sid, 0.4, 1.0, "Making the preview …"))
    update(sid, lambda s: s["renders"].__setitem__("preview", res))
    return res


def render_final(sid: str) -> dict:
    st = load(sid)
    if not st.get("plan"):
        generate(sid)
        st = load(sid)
    plan = dict(st["plan"])
    plan["grade"], plan["codec"] = st["settings"]["grade"], st["settings"].get("codec", "h264")
    name = re.sub(r"[^\w-]+", "_", (st["settings"].get("location") or st["name"]).strip()).strip("_") or "video"
    out = pdir(sid) / "renders" / f"{name}_{plan['format']}_{int(plan['duration'])}s_{int(time.time())}.mp4"
    res = render.render(plan, _clips(st), pdir(sid) / "work", out, "final",
                        _progress(sid, 0.0, 1.0, "Rendering the final video …"))
    from .. import outbox
    outbox.save("reels" if plan["format"] == "reel" else "youtube", out, out.name)
    update(sid, lambda s: s["renders"].__setitem__("final", res))
    return res
