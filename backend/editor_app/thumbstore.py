"""Thumbnail-Maker: Arbeitsstand (Foto, Freisteller, Versionen) pro YouTube-Projekt oder als eigenes Projekt.

Ablage: Projekt → projekte/<id>/thumbmaker/ · eigenes Projekt → daten/thumbmaker/<own-…>/
Fertige PNGs liegen dort und zusätzlich auf dem Desktop (SOCIAL MEDIA APP/Thumbnails/<Name>/).
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import threading
import time
import zipfile
from dataclasses import asdict
from pathlib import Path

from PIL import Image, ImageOps

from . import image_gen, media, projects, thumbmaker
from .config import ROOT
from .errors import UserError

OWN = ROOT / "daten" / "thumbmaker"
_lock = threading.RLock()


def _is_project(wid: str) -> bool:
    try:
        projects.load(wid)
        return True
    except Exception:  # noqa: BLE001
        return False


def wdir(wid: str) -> Path:
    if not re.fullmatch(r"[\w-]+", wid or ""):
        raise UserError("Unknown thumbnail project.")
    d = projects.path(wid, "thumbmaker") if _is_project(wid) else OWN / wid
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_own() -> str:
    wid = "own-" + time.strftime("%Y%m%d-%H%M%S")
    wdir(wid)
    _save(wid, {"name": "Thumbnail", "versions": []})
    return wid


def load(wid: str) -> dict:
    f = wdir(wid) / "state.json"
    st = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"versions": []}
    if _is_project(wid):
        st["name"] = projects.load(wid)["name"]
    st["wid"] = wid
    st["has_video"] = _is_project(wid)
    st["cost"] = image_gen.cost_text(n=3)
    st["provider"] = image_gen.settings()["provider"]
    return st


def _save(wid: str, st: dict) -> dict:
    with _lock:
        keep = {k: v for k, v in st.items() if k not in ("wid", "has_video", "cost", "provider")}
        (wdir(wid) / "state.json").write_text(json.dumps(keep, ensure_ascii=False, indent=1), encoding="utf-8")
    return load(wid)


def list_own() -> list[dict]:
    out = []
    for f in sorted(OWN.glob("own-*/state.json"), reverse=True):
        try:
            st = json.loads(f.read_text(encoding="utf-8"))
            out.append({"wid": f.parent.name, "name": st.get("name", "Thumbnail"), "count": len(st.get("versions", []))})
        except (OSError, ValueError):
            continue
    return out


# ---------------------------------------------------------------- Foto

def frames(wid: str, n: int = 12) -> list[dict]:
    """12 Bilder aus dem Video (gleichmäßig verteilt, ohne Anfang/Ende) zum Anklicken."""
    p = projects.load(wid)
    src = projects.path(wid, "vorschau.mp4")
    if not src.exists():
        src = projects.path(wid, p["original_file"])
    dur = (p.get("info") or {}).get("duration", 0) or 10
    d = wdir(wid) / "frames"
    d.mkdir(exist_ok=True)
    out = []
    for k in range(n):
        t = round(dur * (0.05 + 0.9 * k / max(1, n - 1)), 2)
        f = d / f"frame_{k:02d}.jpg"
        if not f.exists():
            subprocess.run([media.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(src),
                            "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "4", str(f)],
                           creationflags=media._NO_WINDOW)
        if f.exists():
            out.append({"k": k, "t": t, "file": f.name})
    return out


def frame_file(wid: str, name: str) -> Path:
    f = wdir(wid) / "frames" / name
    if not re.fullmatch(r"frame_\d{2}\.jpg", name) or not f.exists():
        raise UserError("Frame not found.")
    return f


def _grab_full(wid: str, t: float) -> Image.Image:
    p = projects.load(wid)
    src = projects.path(wid, p["original_file"])
    r = subprocess.run([media.ffmpeg(), "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(src),
                        "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True,
                       creationflags=media._NO_WINDOW)
    if r.returncode != 0 or not r.stdout:
        raise UserError("This frame could not be read from the video.")
    return Image.open(io.BytesIO(r.stdout)).convert("RGB")


def set_photo(wid: str, img: Image.Image, source: str) -> dict:
    """Foto übernehmen und Carina gleich freistellen (ihr Foto bleibt farblich unverändert)."""
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((2400, 2400))
    d = wdir(wid)
    img.save(d / "photo.png")
    cut, face = thumbmaker.cutout(img)
    cut.save(d / "cut.png")
    st = load(wid)
    st.update(photo="photo.png", cutout="cut.png", face=face, photo_source=source, photo_v=int(time.time()))
    return _save(wid, st)


def photo_from_frame(wid: str, k: int) -> dict:
    fr = {f["k"]: f for f in frames(wid)}.get(k)
    if not fr:
        raise UserError("Unknown frame.")
    return set_photo(wid, _grab_full(wid, fr["t"]), f"frame {fr['t']:.1f}s")


def file(wid: str, name: str) -> Path:
    f = wdir(wid) / name
    if not re.fullmatch(r"[\w.-]+\.(png|jpg)", name) or not f.exists():
        raise UserError("File not found.")
    return f


# ---------------------------------------------------------------- Vorschläge (Claude)

SUGGEST_SCHEMA = {"type": "object", "properties": {
    "backgrounds": {"type": "array", "items": {"type": "string"}},
    "titles": {"type": "array", "items": {"type": "object", "properties": {
        "word1": {"type": "string"}, "word2": {"type": "string"}}, "required": ["word1", "word2"],
        "additionalProperties": False}}},
    "required": ["backgrounds", "titles"], "additionalProperties": False}


def suggest(wid: str, engine: str = "claude") -> dict:
    """3 Hintergrund-Ideen + 3 Titel aus 2 Wörtern – nur Vorschläge, Carina entscheidet."""
    title, text = "", ""
    if _is_project(wid):
        p = projects.load(wid)
        title = p["name"]
        mf = projects.path(wid, "youtube_texte.json")
        if mf.exists():
            try:
                title = (json.loads(mf.read_text(encoding="utf-8")).get("titles") or [title])[0]
            except ValueError:
                pass
        try:
            from . import cuts, cutstore
            t = cutstore._transcript(wid)
            text = " ".join(w["w"] for w in cuts.flat_words(t))[:6000]
        except Exception:  # noqa: BLE001
            text = ""
    st = load(wid)
    prompt = f"""Carina Dorca macht ein YouTube-Thumbnail (Stress- & Burnout-PRÄVENTION, ruhig, ehrlich, Gen Z bis Boomer).
Video-Titel: "{title or st.get('name', '')}"
Was sie sagt (Ausschnitt): {text or '(kein Transkript)'}

1. backgrounds: genau 3 Ideen für einen realistischen Foto-Hintergrund HINTER ihr (Englisch, je 8–15 Wörter,
   ein konkreter Ort mit Licht und Stimmung, z. B. "cosy home office at night, lilac neon light, two monitors").
   Ohne Menschen, ohne Text. Passend zum Thema; leicht lila/warmes Licht ist schön.
2. titles: genau 3 Titel aus GENAU 2 Wörtern in der Ich-Form/Umgangssprache wie "I | quit.", "burned | out.",
   "worth | it?" – word1 kurz und kräftig, word2 das emotionale Wort mit Satzzeichen. Englisch, wenn der Titel
   englisch ist, sonst Deutsch. Keine Heilversprechen.
Antworte NUR mit JSON nach dem Schema."""
    if engine == "claude":
        from . import claude
        raw = claude.ask_json(prompt, SUGGEST_SCHEMA, effort="low")
    else:
        from . import llm
        raw = llm.ask_json(prompt, "Du antwortest ausschließlich mit gültigem JSON.", timeout=300)
    bgs = [str(b).strip() for b in (raw.get("backgrounds") or []) if str(b).strip()][:3]
    tts = [[str(t.get("word1", "")).strip(), str(t.get("word2", "")).strip()] for t in (raw.get("titles") or [])
           if isinstance(t, dict)][:3]
    st["ideas"] = {"backgrounds": bgs, "titles": tts}
    return _save(wid, st)


# ---------------------------------------------------------------- Versionen

def _spec(d: dict) -> thumbmaker.Spec:
    return thumbmaker.Spec(title1=str(d.get("title1", "")), title2=str(d.get("title2", "")),
                           layout=d.get("layout", "auto"), behind=bool(d.get("behind")), doodles=bool(d.get("doodles")),
                           doodle_text=str(d.get("doodle_text", "me")), person=d.get("person") or {},
                           text=d.get("text") or {})


def _render(wid: str, v: dict) -> dict:
    st = load(wid)
    d = wdir(wid)
    if not st.get("cutout"):
        raise UserError("Please choose your photo first.")
    cut = Image.open(d / st["cutout"]).convert("RGBA")
    bg = Image.open(d / v["bg"]).convert("RGB")
    res = thumbmaker.compose(bg, cut, st.get("face"), _spec(v["spec"]))
    png = thumbmaker.to_png(res.image)
    name = f"thumb_{v['id']}_{int(time.time())}.png"
    for old in d.glob(f"thumb_{v['id']}_*.png"):
        old.unlink()
    (d / name).write_bytes(png)
    v.update(png=name, layout_used=res.layout, warnings=res.warnings, size=len(png),
             face_box=list(res.face_box) if res.face_box else None, person_box=list(res.person_box),
             word_boxes=[list(b) for b in res.word_boxes], visible=[round(x, 2) for x in res.visible])
    try:  # auch auf den Desktop (SOCIAL MEDIA APP › Thumbnails › Name)
        from . import outbox
        outbox.save("thumbnails", d / name, f"{st.get('name', 'Thumbnail')} – version {v['id']}.png",
                    sub=st.get("name", "Thumbnail"))
    except Exception:  # noqa: BLE001
        pass
    return v


def _background(wid: str, prompt: str, seed: int) -> tuple[str, str]:
    d = wdir(wid)
    fallback = Image.open(d / "photo.png").convert("RGB") if (d / "photo.png").exists() else None
    img, used = image_gen.generate(prompt, thumbmaker.W, thumbmaker.H, seed=seed, fallback_frame=fallback)
    name = f"bg_{int(time.time() * 1000)}_{seed}.png"
    img.save(d / name)
    return name, used


def generate(wid: str, mode: str, prompts: list[str], titles: list[list[str]], layout: str, behind: bool,
             doodles: bool) -> dict:
    """3 Versionen: mode "backgrounds" = 3 Hintergründe mit demselben Titel; "titles" = 1 Hintergrund, 3 Titel."""
    st = load(wid)
    if not st.get("cutout"):
        raise UserError("Please choose your photo first (step 1).")
    prompts = [p for p in prompts if p.strip()] or ["cosy bright living room with plants, soft daylight"]
    titles = [t for t in titles if any(x.strip() for x in t)]
    if not titles:
        raise UserError("Please write your title first (2 words) – or press “Suggest” and pick one.")
    versions, used_all = [], set()
    if mode == "titles":
        bg, used = _background(wid, prompts[0], seed=11)
        used_all.add(used)
        plan = [(prompts[0], bg, titles[k % len(titles)]) for k in range(3)]
    else:
        plan = []
        for k in range(3):
            pr = prompts[k % len(prompts)]
            bg, used = _background(wid, pr, seed=11 + k * 7)
            used_all.add(used)
            plan.append((pr, bg, titles[0]))
    for k, (pr, bg, tt) in enumerate(plan):
        v = {"id": f"v{k + 1}", "prompt": pr, "bg": bg,
             "spec": {"title1": tt[0], "title2": tt[1] if len(tt) > 1 else "", "layout": layout, "behind": behind,
                      "doodles": doodles, "doodle_text": "me", "person": {}, "text": {}}}
        versions.append(_render(wid, v))
    st["versions"] = versions
    st["last_mode"] = mode
    st["fallback_used"] = "frame" in used_all and image_gen.settings()["provider"] != "frame"
    return _save(wid, st)


def update_version(wid: str, vid: str, spec: dict) -> dict:
    st = load(wid)
    for v in st.get("versions", []):
        if v["id"] == vid:
            allowed = ("title1", "title2", "layout", "behind", "doodles", "doodle_text", "person", "text")
            v["spec"].update({k: spec[k] for k in allowed if k in spec})
            _render(wid, v)
            return _save(wid, st)
    raise UserError("Unknown version.")


def new_background(wid: str, vid: str, prompt: str) -> dict:
    st = load(wid)
    for v in st.get("versions", []):
        if v["id"] == vid:
            v["prompt"] = prompt.strip() or v.get("prompt", "")
            v["bg"], used = _background(wid, v["prompt"], seed=int(time.time()) % 100000)
            st["fallback_used"] = used == "frame" and image_gen.settings()["provider"] != "frame"
            _render(wid, v)
            return _save(wid, st)
    raise UserError("Unknown version.")


def zip_all(wid: str) -> bytes:
    st = load(wid)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for v in st.get("versions", []):
            if v.get("png"):
                z.write(wdir(wid) / v["png"], f"thumbnail_{v['id']}.png")
    return buf.getvalue()


_ = asdict  # (für spätere Exporte)
