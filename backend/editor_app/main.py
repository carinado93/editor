"""Die Web-Schnittstelle zwischen Oberfläche (Browser) und Motor."""
from __future__ import annotations

import json
import os
import re
import shutil
import time
import webbrowser
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, cuts, cutstore, jobs, media, projects, render, transcribe
from .errors import UserError, explain


@asynccontextmanager
async def lifespan(_app: FastAPI):
    jobs.start()
    yield


app = FastAPI(title="Carinas Video-Editor", lifespan=lifespan)


@app.exception_handler(UserError)
async def user_error(_req: Request, exc: UserError):
    return JSONResponse({"fehler": str(exc)}, status_code=400)


@app.exception_handler(Exception)
async def any_error(_req: Request, exc: Exception):
    return JSONResponse({"fehler": explain(exc)}, status_code=500)


# ---------- System ----------

@app.get("/api/system")
def system():
    try:
        ff = media.ffmpeg()
        encoder = media.h264_encoder()[1]
    except UserError as e:
        ff, encoder = None, str(e)
    gpu = transcribe.gpu_available()
    disk = shutil.disk_usage(config.PROJECTS_DIR)
    return {
        "ffmpeg": ff is not None,
        "video_encoder": "graphics card (NVENC)" if encoder == "h264_nvenc" else "processor",
        "gpu": gpu,
        "default_model": transcribe.default_model(gpu),
        "models": transcribe.MODEL_CHOICES,
        "modes": config.MODES,
        "disk_free_gb": round(disk.free / 1e9, 1),
    }


# ---------- Projekte ----------

class NewProject(BaseModel):
    name: str = ""
    mode: str
    filename: str
    size: int
    model: str = "auto"
    language: str = "auto"


@app.get("/api/projects")
def list_projects():
    return projects.list_all()


@app.post("/api/projects")
def create_project(body: NewProject):
    if body.model not in transcribe.MODEL_CHOICES:
        raise UserError("Unknown model.")
    if body.language not in ("auto", "de", "en"):
        raise UserError("Language must be automatic, German or English.")
    return projects.create(body.name, body.mode, body.filename, body.size,
                           {"model": body.model, "language": body.language})


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    return projects.load(pid)


@app.put("/api/projects/{pid}/upload")
async def upload_chunk(pid: str, request: Request, offset: int = 0):
    """Das Video kommt in Stücken (z. B. 8 MB), damit auch mehrere GB sicher ankommen."""
    data = await request.body()
    return {"uploaded": projects.write_chunk(pid, offset, data)}


@app.post("/api/projects/{pid}/upload/done")
def upload_done(pid: str):
    p = projects.load(pid)
    f = projects.path(pid, p["original_file"])
    have = f.stat().st_size if f.exists() else 0
    if have != p["size"]:
        raise UserError(f"The video has not fully arrived yet ({have / max(1, p['size']):.0%}).")
    jobs.enqueue(pid)
    return projects.load(pid)


@app.post("/api/projects/{pid}/retry")
def retry(pid: str):
    p = projects.load(pid)
    if p["status"] not in ("fehler", "fertig"):
        raise UserError("The project is still being processed.")
    jobs.enqueue(pid)
    return projects.load(pid)


@app.delete("/api/projects/{pid}")
def delete_project(pid: str):
    p = projects.load(pid)
    if p["status"] == "arbeitet":
        raise UserError("The project is being processed. Please wait until it is done.")
    projects.delete(pid)
    return {"ok": True}


@app.get("/api/projects/{pid}/transcript")
def get_transcript(pid: str):
    f = projects.path(pid, "transkript.json")
    if not f.exists():
        raise HTTPException(404, "No transcript yet.")
    return json.loads(f.read_text(encoding="utf-8"))


@app.get("/api/projects/{pid}/vorschau.mp4")
def get_proxy(pid: str):
    f = projects.path(pid, "vorschau.mp4")
    if not f.exists():
        raise HTTPException(404, "Preview video not ready yet.")
    return FileResponse(f, media_type="video/mp4")


@app.get("/api/projects/{pid}/bild.jpg")
def get_thumb(pid: str):
    f = projects.path(pid, "bild.jpg")
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(f, media_type="image/jpeg")


# ---------- Schnitte (YouTube-Modus) ----------

class ToggleBody(BaseModel):
    id: str
    active: bool


class WordsBody(BaseModel):
    indices: list[int]
    cut: bool


class PauseBody(BaseModel):
    after: int
    keep: bool


class SettingsBody(BaseModel):
    tempo: str | None = None
    max_gap: float | None = None
    signal_words: list[str] | None = None
    fillers: dict[str, bool] | None = None


class RenderOptionsBody(BaseModel):
    zoom: bool | None = None
    loudness: bool | None = None
    denoise: bool | None = None
    subtitles: str | None = None
    karaoke: bool | None = None


class BuzzBody(BaseModel):
    start: int
    end: int
    on: bool


class RenderBody(BaseModel):
    quality: str = "1080"


@app.get("/api/schnitt-optionen")
def cut_options():
    return {"tempo": {k: {"max": v[0], "ziel": v[1]} for k, v in cuts.TEMPO.items()},
            "reasons": cuts.REASON_TEXT, "qualities": render.QUALITIES}


@app.get("/api/projects/{pid}/cuts")
def get_cuts(pid: str):
    return cutstore.view(pid)


@app.post("/api/projects/{pid}/cuts/toggle")
def toggle_cut(pid: str, body: ToggleBody):
    return cutstore.toggle_detection(pid, body.id, body.active)


@app.post("/api/projects/{pid}/cuts/words")
def cut_words(pid: str, body: WordsBody):
    return cutstore.set_words(pid, body.indices, body.cut)


@app.post("/api/projects/{pid}/cuts/pause")
def cut_pause(pid: str, body: PauseBody):
    return cutstore.set_pause(pid, body.after, body.keep)


@app.put("/api/projects/{pid}/cuts/settings")
def cut_settings(pid: str, body: SettingsBody):
    return cutstore.update_settings(pid, {k: v for k, v in body.model_dump().items() if v is not None})


@app.post("/api/projects/{pid}/cuts/reset")
def cut_reset(pid: str):
    return cutstore.reset(pid)


@app.post("/api/projects/{pid}/cuts/undo")
def cut_undo(pid: str):
    return cutstore.undo(pid)


@app.put("/api/projects/{pid}/cuts/render-options")
def render_options(pid: str, body: RenderOptionsBody):
    return cutstore.set_render_options(pid, {k: v for k, v in body.model_dump().items() if v is not None})


@app.post("/api/projects/{pid}/cuts/buzzword")
def buzzword(pid: str, body: BuzzBody):
    return cutstore.set_buzzword(pid, body.start, body.end, body.on)


@app.post("/api/projects/{pid}/animations/{engine}")
def animations_suggest(pid: str, engine: str):
    if engine not in ("claude", "ollama"):
        raise UserError("Unknown AI.")
    return cutstore.suggest_animations(pid, engine)


@app.post("/api/projects/{pid}/cuts/buzzwords-suggest")
def buzzwords_suggest(pid: str):
    return cutstore.suggest_buzzwords(pid)


@app.get("/api/projects/{pid}/blick")
def get_gaze_events(pid: str):
    """Blick-Ereignisse und Gesichtsbereich (für die Vorschau der Text-Platzierung)."""
    from . import gaze

    f = projects.path(pid, "blick.json")
    if not f.exists():
        return {"events": [], "face_box": None, "ready": False}
    data = json.loads(f.read_text(encoding="utf-8"))
    return {"events": gaze.away_events(data), "face_box": gaze.face_box(data), "ready": True}


@app.post("/api/projects/{pid}/render")
def start_render(pid: str, body: RenderBody):
    jobs.enqueue_render(pid, body.quality)
    return projects.load(pid)


@app.get("/api/projects/{pid}/export/{name}")
def get_export(pid: str, name: str):
    f = projects.path(pid, "export") / name
    if "/" in name or "\\" in name or not f.is_file():
        raise HTTPException(404, "File not found.")
    return FileResponse(f, filename=name)


@app.post("/api/projects/{pid}/open-folder")
def open_folder(pid: str):
    """Öffnet den Export-Ordner im Windows-Explorer."""
    import os
    import subprocess
    import sys

    folder = projects.path(pid, "export")
    folder.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(folder)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(folder)])
    else:
        raise UserError(f"The folder is here: {folder}")
    return {"ok": True}


# ---------- YouTube-Paket: Export, Texte, Thumbnails ----------

def _cut_context(pid: str):
    """Transkript, Schnittliste, Auswertung und Sätze in der neuen Zeit."""
    from . import subtitles

    t = cutstore._transcript(pid)
    v = cutstore.view(pid)
    words = cuts.flat_words(t)
    tmap = subtitles.TimeMap([tuple(x) for x in v["evaluation"]["keep"]])
    sentences, cur, start = [], [], None
    for w, f in zip(words, v["evaluation"]["flags"]):
        if f:
            continue
        if start is None:
            start = tmap.clamp(w["s"])
        cur.append(w["w"])
        if re.search(r"[.!?…]$", w["w"]) and len(cur) >= 3:
            sentences.append((start, " ".join(cur)))
            cur, start = [], None
    if cur:
        sentences.append((start or 0.0, " ".join(cur)))
    return t, v, sentences


class MetaImportBody(BaseModel):
    text: str


class MetaSaveBody(BaseModel):
    titles: list[str]
    chapters: list[dict]
    description: str
    tags: list[str]
    hashtags: list[str]


def _meta_file(pid: str):
    return projects.path(pid, "youtube_texte.json")


@app.get("/api/projects/{pid}/youtube-texte")
def get_meta(pid: str):
    from . import meta

    p = projects.load(pid)
    t, v, sentences = _cut_context(pid)
    prompt = meta.build_prompt(sentences, t.get("language", "de"), v["evaluation"]["new_duration"], p["name"])
    f = _meta_file(pid)
    data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    return {"prompt": prompt, "meta": data, "full_description": meta.full_description(data) if data else ""}


@app.post("/api/projects/{pid}/youtube-texte/ollama")
def meta_ollama(pid: str):
    from . import meta

    p = projects.load(pid)
    t, v, sentences = _cut_context(pid)
    prompt = meta.build_prompt(sentences, t.get("language", "de"), v["evaluation"]["new_duration"], p["name"])
    data = meta.from_ollama(prompt, v["evaluation"]["new_duration"], t.get("language", "en"))
    data["source"] = "ollama"
    _meta_file(pid).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"prompt": prompt, "meta": data, "full_description": meta.full_description(data)}


@app.post("/api/projects/{pid}/youtube-texte/import")
def meta_import(pid: str, body: MetaImportBody):
    from . import meta

    t, v, _ = _cut_context(pid)
    data = meta.parse(body.text, v["evaluation"]["new_duration"], t.get("language", "en"))
    data["source"] = "claude.ai"
    _meta_file(pid).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"meta": data, "full_description": meta.full_description(data)}


@app.put("/api/projects/{pid}/youtube-texte")
def meta_save(pid: str, body: MetaSaveBody):
    from . import meta

    t, v, _ = _cut_context(pid)
    data = meta.parse(body.model_dump(), v["evaluation"]["new_duration"], t.get("language", "en"))
    data["source"] = "bearbeitet"
    _meta_file(pid).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"meta": data, "full_description": meta.full_description(data)}


@app.post("/api/projects/{pid}/thumbnails")
def make_thumbnails(pid: str):
    from . import thumbs

    p = projects.load(pid)
    _, v, _ = _cut_context(pid)
    gf = projects.path(pid, "blick.json")
    data = json.loads(gf.read_text(encoding="utf-8")) if gf.exists() else {}
    shots = thumbs.make(projects.path(pid, p["original_file"]), data, v["evaluation"]["keep"],
                        projects.path(pid, "export") / "thumbnails")
    projects.update(pid, thumbnails=shots)
    return {"thumbnails": shots}


@app.get("/api/projects/{pid}/thumbnails/{name}")
def get_thumbnail(pid: str, name: str):
    f = projects.path(pid, "export") / "thumbnails" / name
    if "/" in name or "\\" in name or not f.is_file():
        raise HTTPException(404)
    return FileResponse(f, media_type="image/jpeg")


# ---------- Reel-Modus (M5) ----------

class OverlaysBody(BaseModel):
    overlays: list[dict]


class ReelTextsBody(BaseModel):
    caption: str
    hashtags: list[str]
    cover_text: str
    shorts_title: str


def _reel_file(pid: str):
    return projects.path(pid, "reel_texte.json")


def _reel_prompt(pid: str, idea: str = "", language: str = "", with_images: bool = False) -> tuple[str, str]:
    """Auftrag für Reel-Texte: immer Hook ab Sekunde 0 + weitere Texte über das Reel verteilt."""
    from . import captions

    t, v, sentences = _cut_context(pid)
    lang = language if language in ("de", "en") else t.get("language", "en")
    spoken = " ".join(s for _, s in sentences)
    return captions.build_idea_prompt(idea, lang, v["evaluation"]["new_duration"], spoken, with_images), lang


def _reel_stills(pid: str) -> list[str]:
    p = projects.load(pid)
    proxy = projects.path(pid, "vorschau.mp4")
    src = proxy if proxy.exists() else projects.path(pid, p["original_file"])
    return media.stills_base64(src, (p.get("info") or {}).get("duration", 10), n=5)


def _apply_scenes(pid: str, data: dict) -> dict:
    """Szenen-Texte direkt ins Video legen (Hook ab Sekunde 0, weitere verteilt, wechselnde Animationen)."""
    from . import captions

    if not data.get("scenes"):
        return {}
    _, v, _ = _cut_context(pid)
    overlays, warnings = captions.distribute_scenes(data["scenes"], v["evaluation"]["new_duration"])
    view = cutstore.set_overlays(pid, overlays)
    view["warnings"] = warnings
    return view


class ReelIdeaBody(BaseModel):
    idea: str = ""
    language: str = ""


class ReelImportBody(BaseModel):
    text: str
    idea: str = ""
    language: str = ""


@app.put("/api/projects/{pid}/cuts/overlays")
def put_overlays(pid: str, body: OverlaysBody):
    return cutstore.set_overlays(pid, body.overlays)


@app.get("/api/projects/{pid}/reel-texte")
def get_reel_texts(pid: str):
    from . import captions

    f = _reel_file(pid)
    data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    t = cutstore._transcript(pid)
    return {"texts": data, "full_caption": captions.full_caption(data) if data else "",
            "silent": not any(s["words"] for s in t.get("segments", [])), "language": t.get("language", "en"),
            "idea": (data or {}).get("idea", "")}


@app.post("/api/projects/{pid}/reel-texte/auftrag")
def reel_prompt(pid: str, body: ReelIdeaBody):
    prompt, _ = _reel_prompt(pid, body.idea, body.language)
    return {"prompt": prompt}


def _save_reel(pid: str, data: dict, source: str, idea: str = "") -> dict:
    from . import captions

    data["source"] = source
    data["idea"] = idea
    _reel_file(pid).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"texts": data, "full_caption": captions.full_caption(data)}


@app.post("/api/projects/{pid}/reel-texte/ollama")
def reel_texts_ollama(pid: str, body: ReelIdeaBody):
    from . import captions, llm

    images = _reel_stills(pid)
    prompt, lang = _reel_prompt(pid, body.idea, body.language, bool(images))
    raw = llm.ask_json(prompt, "Du antwortest ausschließlich mit gültigem JSON.", timeout=600, images=images)
    data = captions.parse(raw if isinstance(raw, dict) else {}, lang)
    res = _save_reel(pid, data, "ollama", body.idea)
    res["cuts"] = _apply_scenes(pid, data)
    return res


@app.post("/api/projects/{pid}/reel-texte/import")
def reel_texts_import(pid: str, body: ReelImportBody):
    from . import captions

    lang = body.language if body.language in ("de", "en") else cutstore._transcript(pid).get("language", "en")
    return _save_reel(pid, captions.parse(body.text, lang), "claude.ai", body.idea)


@app.put("/api/projects/{pid}/reel-texte")
def reel_texts_save(pid: str, body: ReelTextsBody):
    from . import captions

    f = _reel_file(pid)
    old = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    lang = cutstore._transcript(pid).get("language", "en")
    data = captions.parse({**body.model_dump(), "scenes": old.get("scenes", [])}, lang)
    return _save_reel(pid, data, "bearbeitet", old.get("idea", ""))


@app.post("/api/projects/{pid}/reel-texte/szenen-uebernehmen")
def reel_scenes_apply(pid: str):
    """Freigegebene Szenen-Texte als Einblendungen ins Video legen (gleichmäßig, je ≥ 4,4 s)."""
    from . import captions

    f = _reel_file(pid)
    data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    if not data.get("scenes"):
        raise UserError("There are no scene texts yet. Please create texts from your idea first.")
    _, v, _ = _cut_context(pid)
    overlays, warnings = captions.distribute_scenes(data["scenes"], v["evaluation"]["new_duration"])
    result = cutstore.set_overlays(pid, overlays)
    result["warnings"] = warnings
    return result


# ---------- Thumbnails & Cover (M4b) ----------

class CoverBody(BaseModel):
    kind: str  # youtube | meditation | reel
    text: str = ""
    pill: str = ""
    subtitle: str = ""
    top_pill: str = ""
    top_label: str = ""
    color: str = "auto"


def _ensure_thumbs(pid: str) -> list[dict]:
    from . import thumbs

    p = projects.load(pid)
    if p.get("thumbnails"):
        d = projects.path(pid, "export") / "thumbnails"
        if all((d / t["file"]).exists() for t in p["thumbnails"]):
            return p["thumbnails"]
    _, v, _ = _cut_context(pid)
    gf = projects.path(pid, "blick.json")
    data = json.loads(gf.read_text(encoding="utf-8")) if gf.exists() else {}
    shots = thumbs.make(projects.path(pid, p["original_file"]), data, v["evaluation"]["keep"],
                        projects.path(pid, "export") / "thumbnails")
    projects.update(pid, thumbnails=shots)
    return shots


@app.get("/api/projects/{pid}/cover-vorschlag")
def cover_defaults(pid: str):
    from . import buzz, covers

    _, _, sentences = _cut_context(pid)
    f = _meta_file(pid)
    meta_data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    title = (meta_data or {}).get("titles", [""])[0] if meta_data and meta_data.get("titles") else ""
    hook = sentences[0][1] if sentences else ""
    short_hook = " ".join(re.sub(r"[.!?…]+$", "", hook).split()[:7])
    reel_text = short_hook
    hook = next((o["text"].replace("*", "") for o in cutstore.view(pid)["cutlist"].get("overlays", [])
                 if o.get("on", True)), "")
    if hook:
        reel_text = hook
    rf = _reel_file(pid)
    if rf.exists():
        reel_text = json.loads(rf.read_text(encoding="utf-8")).get("cover_text") or reel_text
    return {
        "youtube": {"text": covers.default_thumb_text(title or short_hook, buzz.THEMEN), "pill": ""},
        "meditation": {"text": title or short_hook, "subtitle": "", "top_pill": "", "top_label": ""},
        "reel": {"text": reel_text, "color": covers.next_cover_color()},
        "next_color": covers.next_cover_color(),
    }


@app.post("/api/projects/{pid}/covers")
def make_covers(pid: str, body: CoverBody):
    from PIL import Image

    from . import covers

    if body.kind not in ("youtube", "meditation", "reel"):
        raise UserError("Unknown type.")
    if not body.text.strip():
        raise UserError("Please enter a text.")
    shots = _ensure_thumbs(pid)[:3]
    gf = projects.path(pid, "blick.json")
    samples = json.loads(gf.read_text(encoding="utf-8")).get("samples", []) if gf.exists() else []
    color = covers.next_cover_color() if body.color == "auto" else body.color
    out_dir = projects.path(pid, "export") / "cover"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob(f"{body.kind}_*"):
        old.unlink()
    files = []
    for n, shot in enumerate(shots, 1):
        img = Image.open(projects.path(pid, "export") / "thumbnails" / shot["file"]).convert("RGB")
        faces = [s for s in samples if s.get("face")]
        face = min(faces, key=lambda s: abs(s["t"] - shot["t"]))["box"] if faces else None
        if body.kind == "youtube":
            im = covers.youtube_talking(img, face, body.text, body.pill)
        elif body.kind == "meditation":
            im = covers.youtube_meditation(img, face, body.text, body.subtitle, body.top_pill, body.top_label)
        else:
            im = covers.reel_cover(img, face, body.text, color)
        name = f"{body.kind}_{n}_{int(time.time())}.jpg"
        im.save(out_dir / name, "JPEG", quality=92)  # YouTube erlaubt max. 2 MB
        files.append(name)
    return {"files": files, "color": color if body.kind == "reel" else None}


@app.get("/api/projects/{pid}/cover/{name}")
def get_cover(pid: str, name: str):
    f = projects.path(pid, "export") / "cover" / name
    if "/" in name or "\\" in name or not f.is_file():
        raise HTTPException(404)
    return FileResponse(f, media_type="image/jpeg", filename=name)


class ColorBody(BaseModel):
    used: str


@app.post("/api/cover-farbe/verwendet")
def cover_color_used(body: ColorBody):
    from . import covers

    return {"next": covers.advance_cover_color(body.used)}


# ---------- Claude (Schnittstelle) ----------

class KeyBody(BaseModel):
    key: str


class ChatBody(BaseModel):
    messages: list[dict]
    language: str = "en"


@app.get("/api/einstellungen/claude")
def claude_settings():
    from . import claude

    return {"configured": claude.available(), "masked": claude.masked(), "model": claude.MODEL}


@app.put("/api/einstellungen/claude")
def claude_save_key(body: KeyBody):
    from . import claude

    claude.save_key(body.key)
    return {"configured": True, "masked": claude.masked(), "model": claude.MODEL}


@app.delete("/api/einstellungen/claude")
def claude_delete_key():
    from . import claude

    claude.delete_key()
    return {"configured": False, "masked": "", "model": claude.MODEL}


@app.post("/api/claude/chat")
def claude_chat(body: ChatBody):
    from . import claude

    return {"text": claude.chat(body.messages, claude.chat_system(body.language))}


@app.post("/api/projects/{pid}/reel-texte/claude")
def reel_texts_claude(pid: str, body: ReelIdeaBody):
    from . import captions, claude

    images = _reel_stills(pid)
    prompt, lang = _reel_prompt(pid, body.idea, body.language, bool(images))
    data = captions.parse(claude.ask_json(prompt, claude.REEL_SCHEMA, images=images), lang)
    res = _save_reel(pid, data, "claude", body.idea)
    res["cuts"] = _apply_scenes(pid, data)
    return res


@app.post("/api/projects/{pid}/youtube-texte/claude")
def youtube_texts_claude(pid: str):
    from . import claude, meta

    p = projects.load(pid)
    t, v, sentences = _cut_context(pid)
    prompt = meta.build_prompt(sentences, t.get("language", "de"), v["evaluation"]["new_duration"], p["name"])
    data = meta.parse(claude.ask_json(prompt, claude.YOUTUBE_SCHEMA), v["evaluation"]["new_duration"],
                      t.get("language", "en"))
    data["source"] = "claude"
    _meta_file(pid).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"prompt": prompt, "meta": data, "full_description": meta.full_description(data)}


# ---------- Reels aus YouTube-Videos ----------

class ClipSuggestBody(BaseModel):
    engine: str = "claude"  # claude | ollama
    feedback: str = ""


class ClipEditBody(BaseModel):
    title: str | None = None
    hook_text: str | None = None
    caption: str | None = None
    shorts_title: str | None = None
    hashtags: list[str] | None = None


@app.get("/api/projects/{pid}/clips")
def get_clips(pid: str):
    from . import clips

    return clips.load(pid)


@app.post("/api/projects/{pid}/clips/vorschlagen")
def suggest_clips(pid: str, body: ClipSuggestBody):
    from . import clips

    if body.engine not in ("claude", "ollama"):
        raise UserError("Unknown AI.")
    t = cutstore._transcript(pid)
    v = cutstore.view(pid)
    data = clips.load(pid)
    keep = [c for c in data["clips"] if c.get("status") != "vorschlag"]  # freigegebene/gerenderte bleiben
    previous = [c for c in data["clips"] if c.get("status") == "vorschlag"] if body.feedback.strip() else None
    new = clips.suggest(body.engine, t, v["cutlist"], v["evaluation"]["flags"], body.feedback, previous)
    if body.feedback.strip():
        data.setdefault("feedback", []).append(body.feedback.strip())
    data["clips"] = keep + new
    return clips.save(pid, data)


@app.put("/api/projects/{pid}/clips/{cid}")
def edit_clip(pid: str, cid: str, body: ClipEditBody):
    from . import clips, meta

    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if "hashtags" in fields:
        fields["hashtags"] = meta.fix_hashtags(fields["hashtags"], cutstore._transcript(pid).get("language", "en"), [])
    clips.update_clip(pid, cid, **fields)
    return clips.load(pid)


@app.delete("/api/projects/{pid}/clips/{cid}")
def delete_clip(pid: str, cid: str):
    from . import clips

    with clips._lock:
        data = clips.load(pid)
        data["clips"] = [c for c in data["clips"] if c["id"] != cid]
        clips.save(pid, data)
    return data


@app.post("/api/projects/{pid}/clips/{cid}/render")
def render_clip(pid: str, cid: str):
    from . import clips

    c = clips.get_clip(pid, cid)
    if c.get("status") in ("warteschlange", "arbeitet"):
        raise UserError("This reel is already being rendered.")
    clips.update_clip(pid, cid, status="warteschlange", progress=0.0, message="Waiting …", error=None)
    jobs.enqueue_clip(pid, cid)
    return clips.load(pid)


# ---------- Selbst-Aktualisierung ----------

@app.get("/api/update/status")
def update_status(force: bool = False):
    from . import updater

    return updater.status(force)


@app.post("/api/update")
def update_now():
    from . import updater

    from . import clips as _clips

    clip_busy = any(c.get("status") in ("warteschlange", "arbeitet")
                    for p in projects.list_all() for c in _clips.load(p["id"]).get("clips", []))
    busy = clip_busy or any(p["status"] in ("warteschlange", "arbeitet")
               or (p.get("render") or {}).get("status") in ("warteschlange", "arbeitet") for p in projects.list_all())
    return updater.update_and_restart(busy)


@app.get("/api/version")
def app_version():
    from . import updater

    return {"version": updater.version()}


@app.middleware("http")
async def no_cache_for_page(request: Request, call_next):
    """Die Seite selbst nie zwischenspeichern, damit nach einem Update sofort die neue Oberfläche kommt."""
    response = await call_next(request)
    if not request.url.path.startswith(("/api", "/assets")):
        response.headers["Cache-Control"] = "no-cache"
    return response


# Unbekannte Adresse unter /api: meist läuft noch ein alter Motor mit neuer Oberfläche (nach "Git: Pull")
@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "DELETE"])
def unknown_api(rest: str):
    return JSONResponse({"fehler": "The running engine does not know this function yet. Please click "
                                   "\"Update now\" at the top or restart the app (start.bat)."},
                        status_code=404)


# ---------- Oberfläche ----------

if config.FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="oberflaeche")
else:
    @app.get("/")
    def no_frontend():
        return JSONResponse({"fehler": "The interface is missing (frontend/dist). Please use 'start.bat'."})


def run() -> None:
    import uvicorn

    import socket

    url = f"http://{config.HOST}:{config.PORT}"
    with socket.socket() as sock:
        if sock.connect_ex((config.HOST, config.PORT)) == 0:
            # Läuft schon (z. B. doppelt gestartet): nur den Browser öffnen
            print(f"\n  The app is already running. Open {url}\n")
            webbrowser.open(url)
            return
    print(f"\n  Carina's Video Editor is running:  {url}\n  Close this window to stop it.\n")
    if config.HOST in ("127.0.0.1", "localhost") and not os.environ.get("EDITOR_NO_BROWSER"):
        try:
            webbrowser.open(url)
        except Exception:
            pass
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="warning")


if __name__ == "__main__":
    run()
