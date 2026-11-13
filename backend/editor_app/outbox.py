"""Alle fertigen Sachen landen zusätzlich auf Carinas Desktop:

    Desktop/SOCIAL MEDIA APP/
        Thumbnails/
        YouTube videos/
        Reels/
        Carousels/

Die App behält ihre eigene Kopie (für Vorschau und erneutes Herunterladen). Auf derselben Festplatte wird
ein "harter Link" angelegt – das kostet keinen zusätzlichen Platz, auch bei großen Videos.
Anderer Ort: Umgebungsvariable SOCIAL_MEDIA_FOLDER (z. B. in der Datei .env).
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

FOLDER_NAME = "SOCIAL MEDIA APP"
KINDS = {"thumbnails": "Thumbnails", "youtube": "YouTube videos", "reels": "Reels", "carousels": "Carousels"}


def _desktop() -> Path:
    home = Path.home()
    if sys.platform == "win32":
        try:  # echter Desktop-Ordner (auch wenn er in OneDrive liegt oder umbenannt ist)
            import ctypes
            from ctypes import wintypes

            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf) == 0 and buf.value:
                return Path(buf.value)
        except Exception:  # noqa: BLE001
            pass
        for p in (home / "OneDrive" / "Desktop", home / "OneDrive" / "Schreibtisch", home / "Desktop"):
            if p.is_dir():
                return p
    return home / "Desktop"


def root() -> Path:
    custom = os.environ.get("SOCIAL_MEDIA_FOLDER", "")
    if not custom:
        try:
            from . import publish
            custom = publish.env("SOCIAL_MEDIA_FOLDER")
        except Exception:  # noqa: BLE001
            custom = ""
    base = Path(custom) if custom else _desktop() / FOLDER_NAME
    for sub in KINDS.values():
        (base / sub).mkdir(parents=True, exist_ok=True)
    return base


def safe(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip().strip(".")
    return re.sub(r"\s+", " ", name)[:90] or "file"


def save(kind: str, src: Path, name: str | None = None, sub: str | None = None) -> Path | None:
    """Datei in den passenden Desktop-Ordner legen. Fehler hier stoppen nie das Rendern."""
    try:
        target_dir = root() / KINDS[kind]
        if sub:
            target_dir = target_dir / safe(sub)
            target_dir.mkdir(parents=True, exist_ok=True)
        dst = target_dir / (safe(name) if name else src.name)
        if dst.exists():
            dst.unlink()
        try:
            os.link(src, dst)  # gleiche Festplatte: kein zusätzlicher Platz
        except OSError:
            shutil.copy2(src, dst)
        return dst
    except Exception:  # noqa: BLE001 – Desktop nicht erreichbar o. ä.: App läuft trotzdem weiter
        import traceback
        traceback.print_exc()
        return None


def open_folder(kind: str | None = None) -> Path:
    import subprocess

    folder = root() / KINDS[kind] if kind in KINDS else root()
    if sys.platform == "win32":
        os.startfile(folder)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(folder)])
    else:
        subprocess.Popen(["xdg-open", str(folder)])
    return folder
