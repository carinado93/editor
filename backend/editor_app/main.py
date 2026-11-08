"""Die Web-Schnittstelle zwischen Oberfläche (Browser) und Motor."""
from __future__ import annotations

import json
import shutil
import webbrowser
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, jobs, media, projects, transcribe
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
        "video_encoder": "Grafikkarte (NVENC)" if encoder == "h264_nvenc" else "Prozessor",
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
        raise UserError("Unbekanntes Modell.")
    if body.language not in ("auto", "de", "en"):
        raise UserError("Sprache muss automatisch, Deutsch oder Englisch sein.")
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
        raise UserError(f"Das Video ist noch nicht vollständig angekommen ({have / max(1, p['size']):.0%}).")
    jobs.enqueue(pid)
    return projects.load(pid)


@app.post("/api/projects/{pid}/retry")
def retry(pid: str):
    p = projects.load(pid)
    if p["status"] not in ("fehler", "fertig"):
        raise UserError("Das Projekt wird gerade noch verarbeitet.")
    jobs.enqueue(pid)
    return projects.load(pid)


@app.delete("/api/projects/{pid}")
def delete_project(pid: str):
    p = projects.load(pid)
    if p["status"] == "arbeitet":
        raise UserError("Das Projekt wird gerade verarbeitet. Bitte warte, bis es fertig ist.")
    projects.delete(pid)
    return {"ok": True}


@app.get("/api/projects/{pid}/transcript")
def get_transcript(pid: str):
    f = projects.path(pid, "transkript.json")
    if not f.exists():
        raise HTTPException(404, "Noch kein Transkript.")
    return json.loads(f.read_text(encoding="utf-8"))


@app.get("/api/projects/{pid}/vorschau.mp4")
def get_proxy(pid: str):
    f = projects.path(pid, "vorschau.mp4")
    if not f.exists():
        raise HTTPException(404, "Vorschau-Video noch nicht fertig.")
    return FileResponse(f, media_type="video/mp4")


@app.get("/api/projects/{pid}/bild.jpg")
def get_thumb(pid: str):
    f = projects.path(pid, "bild.jpg")
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(f, media_type="image/jpeg")


# ---------- Oberfläche ----------

if config.FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="oberflaeche")
else:
    @app.get("/")
    def no_frontend():
        return JSONResponse({"fehler": "Die Oberfläche fehlt (frontend/dist). Bitte 'start.bat' benutzen."})


def run() -> None:
    import uvicorn

    import socket

    url = f"http://{config.HOST}:{config.PORT}"
    with socket.socket() as sock:
        if sock.connect_ex((config.HOST, config.PORT)) == 0:
            # Läuft schon (z. B. doppelt gestartet): nur den Browser öffnen
            print(f"\n  Die App läuft schon. Öffne {url}\n")
            webbrowser.open(url)
            return
    print(f"\n  Carinas Video-Editor läuft:  {url}\n  Zum Beenden dieses Fenster schließen.\n")
    if config.HOST in ("127.0.0.1", "localhost"):
        try:
            webbrowser.open(url)
        except Exception:
            pass
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="warning")


if __name__ == "__main__":
    run()
