"""Projekte: jedes Video bekommt einen eigenen Ordner in `projekte/`.

projekte/<id>/
  project.json     Infos und Status
  original.mp4     Kopie deines Videos (dein Original auf dem PC bleibt, wo es ist)
  vorschau.mp4     kleines Vorschau-Video
  ton.wav          Tonspur für die Spracherkennung
  transkript.json  Transkript mit Wort-Zeitstempeln
  cache/           Zwischenergebnisse (damit nach Abbruch nichts neu gerechnet werden muss)
"""
from __future__ import annotations

import json
import re
import shutil
import threading
import time
import uuid
from pathlib import Path

from .config import MODES, PROJECTS_DIR
from .errors import UserError

_lock = threading.RLock()

STATUS_TEXT = {
    "hochladen": "Uploading",
    "warteschlange": "Waiting",
    "arbeitet": "Processing",
    "fertig": "Done",
    "fehler": "Error",
}


def _dir(pid: str) -> Path:
    if not re.fullmatch(r"[a-z0-9-]{6,64}", pid):
        raise UserError("Unknown project.")
    return PROJECTS_DIR / pid


def path(pid: str, name: str = "") -> Path:
    return _dir(pid) / name if name else _dir(pid)


def load(pid: str) -> dict:
    f = _dir(pid) / "project.json"
    if not f.exists():
        raise UserError("This project does not exist (any more).")
    with _lock:
        return json.loads(f.read_text(encoding="utf-8"))


def save(project: dict) -> dict:
    with _lock:
        d = _dir(project["id"])
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "project.json.tmp"
        tmp.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(d / "project.json")
    return project


def update(pid: str, **fields) -> dict:
    with _lock:
        p = load(pid)
        p.update(fields)
        return save(p)


def create(name: str, mode: str, filename: str, size: int, settings: dict | None = None) -> dict:
    if mode not in MODES:
        raise UserError("Unknown mode.")
    ext = Path(filename).suffix.lower() or ".mp4"
    if ext not in {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm", ".mts"}:
        raise UserError(f"File type '{ext}' is not supported. Please upload a video (e.g. MP4 or MOV).")
    free = shutil.disk_usage(PROJECTS_DIR).free
    if size * 1.3 > free:
        raise UserError(f"Not enough space on the hard drive: the video needs about {size * 1.3 / 1e9:.1f} GB, "
                        f"{free / 1e9:.1f} GB are free.")
    pid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    project = {
        "id": pid,
        "name": name.strip() or Path(filename).stem,
        "mode": mode,
        "created": time.time(),
        "original_name": filename,
        "original_file": "original" + ext,
        "size": size,
        "uploaded": 0,
        "status": "hochladen",
        "step": "",
        "progress": 0.0,
        "message": "",
        "error": None,
        "info": None,
        "settings": {"model": "auto", "language": "auto", **(settings or {})},
        "transcript": None,
    }
    return save(project)


def list_all() -> list[dict]:
    out = []
    for f in sorted(PROJECTS_DIR.glob("*/project.json"), reverse=True):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def write_chunk(pid: str, offset: int, data: bytes) -> int:
    p = load(pid)
    if p["status"] != "hochladen":
        raise UserError("This video has already been uploaded.")
    f = _dir(pid) / p["original_file"]
    current = f.stat().st_size if f.exists() else 0
    if offset != current:
        return current  # Browser macht an der richtigen Stelle weiter
    with open(f, "ab") as fh:
        fh.write(data)
    new = current + len(data)
    update(pid, uploaded=new, progress=new / max(1, p["size"]), message="Uploading …")
    return new


def delete(pid: str) -> None:
    d = _dir(pid)
    if d.exists():
        shutil.rmtree(d)
