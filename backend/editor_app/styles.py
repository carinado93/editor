"""Gespeicherte Effekt-Stile ("meine YouTube-Art"): welche Effekte Claude nutzen darf, Wunsch-Text, Größen pro
Effekt-Typ, Outro ja/nein und Render-Einstellungen. Gespeichert auf Carinas PC in daten/stile.json."""
from __future__ import annotations

import json
import re
import threading
import time

from . import fx
from .config import ROOT
from .errors import UserError

FILE = ROOT / "daten" / "stile.json"
_lock = threading.Lock()
RENDER_KEYS = ("zoom", "loudness", "denoise", "declick", "subtitles", "karaoke")


def _load() -> list[dict]:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save(items: list[dict]) -> None:
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")


def list_all() -> list[dict]:
    return _load()


def clean(body: dict) -> dict:
    name = str(body.get("name", "")).strip()[:60]
    if not name:
        raise UserError("Please give the style a name, e.g. \"My YouTube style\".")
    sizes = {}
    for k, v in (body.get("sizes") or {}).items():
        if k in fx.TYPES:
            try:
                sizes[k] = round(max(0.4, min(2.5, float(v))), 2)
            except (TypeError, ValueError):
                pass
    render = {k: body["render"][k] for k in RENDER_KEYS if isinstance(body.get("render"), dict) and k in body["render"]}
    if "subtitles" in render and render["subtitles"] not in ("aus", "srt", "einbrennen"):
        render.pop("subtitles")
    return {
        "name": name,
        "allowed": [t for t in body.get("allowed") or [] if t in fx.TYPES],
        "wish": str(body.get("wish", "")).strip()[:1000],
        "sizes": sizes,
        "outro": bool(body.get("outro")),
        "render": render,
    }


def save(body: dict) -> list[dict]:
    st = clean(body)
    with _lock:
        items = [s for s in _load() if s["name"].lower() != st["name"].lower()]  # gleicher Name = überschreiben
        st["id"] = re.sub(r"[^a-z0-9]+", "-", st["name"].lower()).strip("-") + f"-{int(time.time()) % 100000}"
        items.append(st)
        _save(items)
    return items


def delete(sid: str) -> list[dict]:
    with _lock:
        items = [s for s in _load() if s.get("id") != sid]
        _save(items)
    return items
