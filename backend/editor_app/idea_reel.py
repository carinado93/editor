"""Reel aus einer Idee (ohne Filmen): Carinas Fotos – oder ihr Lavendel-Hintergrund – werden zu einem ruhigen
9:16-Video (langsamer Zoom pro Foto, weiche Übergänge). Danach läuft alles wie bei "Reel veredeln":
Claude schreibt aus der Idee die Texte, dazu Effekte, Rendern, Herunterladen."""
from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from PIL import Image, ImageOps

from . import fx, media, projects
from .config import ROOT
from .errors import UserError

W, H, FPS = 1080, 1920, 30
DRAFTS = ROOT / "daten" / "idee"


def _draft(did: str) -> Path:
    if not re.fullmatch(r"[\w-]+", did or ""):
        raise UserError("Unknown draft.")
    return DRAFTS / did


def new_draft() -> str:
    did = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
    (DRAFTS / did).mkdir(parents=True, exist_ok=True)
    return did


def add_photo(did: str, k: int, data: bytes) -> None:
    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except Exception:
        raise UserError("This file is not an image the app can read (please use JPG or PNG).")
    # auf 9:16 zuschneiden (etwas größer, damit der Zoom Platz hat)
    img = ImageOps.fit(img, (int(W * 1.12), int(H * 1.12)), Image.LANCZOS, centering=(0.5, 0.4))
    img.save(_draft(did) / f"foto_{k:02d}.jpg", "JPEG", quality=94)


def _segment(img: Path, seconds: float, out: Path, zoom_in: bool) -> None:
    n = max(1, int(round(seconds * FPS)))
    z = f"min(1+0.10*on/{n},1.10)" if zoom_in else f"max(1.10-0.10*on/{n},1.0)"
    vf = (f"scale={int(W * 1.12)}:{int(H * 1.12)},zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
          f"d={n}:s={W}x{H}:fps={FPS},fade=t=in:st=0:d=0.35,fade=t=out:st={max(0.0, seconds - 0.35):.2f}:d=0.35,"
          f"format=yuv420p")
    r = subprocess.run([media.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-i", str(img),
                        "-vf", vf, "-frames:v", str(n), "-r", str(FPS), *media.h264_encoder(), str(out)],
                       capture_output=True, text=True, creationflags=media._NO_WINDOW)
    if r.returncode != 0:
        raise UserError("The photo video could not be made: " + r.stderr[-300:])


def build(did: str, name: str, idea: str, seconds: float, language: str) -> dict:
    """Video bauen, als neues "Reel veredeln"-Projekt anlegen und verarbeiten lassen."""
    from . import jobs

    d = _draft(did)
    photos = sorted(d.glob("foto_*.jpg"))
    seconds = max(1.5, min(8.0, float(seconds or 3)))
    if not photos:  # ohne Fotos: Carinas Lavendel-Muster als ruhiger Hintergrund (ca. 12 s)
        # ruhiger Lavendel-Verlauf mit feinen Pflanzen-Linien (Carinas Stil) – die Texte stehen im Vordergrund
        from . import covers
        bg = fx.lavender_bg(int(W * 1.12), int(H * 1.12)).convert("RGBA")
        small = covers.botanical((bg.width // 2, bg.height // 2), (150, 125, 195), seed=7, alpha=80, layout="corner")
        deco = small.resize(bg.size, Image.LANCZOS)  # doppelt so groß gezeichnet – passend zum hohen Reel
        bg.alpha_composite(deco)
        bg = bg.convert("RGB")
        bg.save(d / "foto_00.jpg", "JPEG", quality=94)
        photos = [d / "foto_00.jpg"]
        seconds = 12.0
    parts = []
    for k, ph in enumerate(photos):
        seg = d / f"teil_{k:02d}.mp4"
        _segment(ph, seconds, seg, zoom_in=k % 2 == 0)
        parts.append(seg)
    lst = d / "liste.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    video = d / "idee.mp4"
    r = subprocess.run([media.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                        "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(video)],
                       capture_output=True, text=True, creationflags=media._NO_WINDOW, cwd=str(d))
    if r.returncode != 0:
        raise UserError("The photo video could not be put together: " + r.stderr[-300:])
    p = projects.create(name.strip() or "Reel from an idea", "reel", "idee.mp4", video.stat().st_size,
                        {"model": "auto", "language": language if language in ("de", "en") else "en"})
    pid = p["id"]
    shutil.move(str(video), projects.path(pid, p["original_file"]))
    projects.update(pid, uploaded=p["size"], from_idea=True)
    # die Idee steht gleich im Reel-Paket (Claude macht daraus die Texte)
    projects.path(pid, "reel_texte.json").write_text(json.dumps({"idea": idea.strip()}, ensure_ascii=False),
                                                     encoding="utf-8")
    shutil.rmtree(d, ignore_errors=True)
    jobs.enqueue(pid)
    return projects.load(pid)


AUTO_FX = ["statement", "quote", "label", "quotepill", "typewriter", "headline", "pill", "repeat", "wordswap"]


def auto_texts(pid: str, report=None) -> str:
    """Gleich nach dem Vorbereiten: Claude schreibt aus der Idee die Texte (Hook + Szenen-Texte ins Video,
    Caption, 5 Hashtags) und plant passende Text-Effekte. Gibt einen Hinweis zurück ("" = alles gut)."""
    from . import captions, claude, cutstore

    if not claude.available():
        return ("Claude is not set up yet, so the texts were not written automatically. Add your Claude key in "
                "Settings, then press “Write with Claude” in the reel package below.")
    rf = projects.path(pid, "reel_texte.json")
    try:
        idea = json.loads(rf.read_text(encoding="utf-8")).get("idea", "")
    except (OSError, ValueError):
        idea = ""
    p = projects.load(pid)
    dur = (p.get("info") or {}).get("duration", 10)
    lang = cutstore._transcript(pid).get("language", "en")
    proxy = projects.path(pid, "vorschau.mp4")
    images = media.stills_base64(proxy if proxy.exists() else projects.path(pid, p["original_file"]), dur, n=5)
    if report:
        report("Claude writes the texts from your idea …")
    data = captions.parse(claude.ask_json(captions.build_idea_prompt(idea, lang, dur, "", bool(images)),
                                          claude.REEL_SCHEMA, images=images), lang)
    data.update(source="claude", idea=idea)
    rf.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    if data.get("scenes"):
        overlays, _ = captions.distribute_scenes(data["scenes"], dur)
        cutstore.set_overlays(pid, overlays)
    if report:
        report("Claude adds text effects …")
    try:
        cutstore.suggest_effects(pid, "claude", AUTO_FX, "calm, few effects, the texts of the idea are the star")
    except Exception:  # noqa: BLE001 – Effekte sind ein Zusatz, die Texte sind schon da
        import traceback
        traceback.print_exc()
    return ""
