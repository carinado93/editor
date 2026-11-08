"""Selbst-Aktualisierung: neue Version von GitHub holen und die App neu starten (ein Klick in der App).

Ablauf: "git fetch" prüft, ob es Neues gibt. Beim Klick auf "Jetzt aktualisieren": "git pull --ff-only",
dann beendet sich der Motor mit Code 3. start.bat erkennt den Code, aktualisiert die Bausteine (uv sync)
und startet die App neu. Die Seite im Browser lädt sich danach von selbst neu.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time

from .config import ROOT
from .errors import UserError

RESTART_CODE = 3
_cache: dict = {"t": 0.0, "data": None}
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _git(*args: str, timeout: float = 30) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace", creationflags=_NO_WINDOW)


def version() -> str:
    try:
        r = _git("rev-parse", "--short", "HEAD", timeout=10)
        return r.stdout.strip() if r.returncode == 0 else "?"
    except (OSError, subprocess.SubprocessError):
        return "?"


def status(force: bool = False) -> dict:
    if not force and _cache["data"] and time.time() - _cache["t"] < 600:
        return _cache["data"]
    data = {"current": version(), "available": False, "behind": 0, "can_update": False, "reason": ""}
    if not shutil.which("git"):
        data["reason"] = "Git ist nicht installiert."
    elif not (ROOT / ".git").exists():
        data["reason"] = "Die App wurde als ZIP geladen. Für Updates bitte einmal über VS Code „Git: Clone“ holen."
    else:
        try:
            f = _git("fetch", "--quiet", "origin", timeout=40)
            if f.returncode != 0:
                data["reason"] = "Keine Verbindung zu GitHub (Internet?)."
            else:
                r = _git("rev-list", "--count", "HEAD..@{u}")
                behind = int(r.stdout.strip() or 0) if r.returncode == 0 else 0
                data.update(behind=behind, available=behind > 0, can_update=True)
        except (OSError, subprocess.SubprocessError, ValueError):
            data["reason"] = "Update-Prüfung hat nicht geklappt."
    _cache.update(t=time.time(), data=data)
    return data


def update_and_restart(busy: bool) -> dict:
    if busy:
        raise UserError("Gerade wird ein Video verarbeitet oder gerendert. Bitte warte, bis es fertig ist, "
                        "dann aktualisieren.")
    st = status(force=True)
    if not st["can_update"]:
        raise UserError(st["reason"] or "Aktualisieren ist gerade nicht möglich.")
    dirty = _git("status", "--porcelain", "--untracked-files=no")
    if dirty.stdout.strip():
        # Geänderte Dateien (z. B. aus Versehen bearbeitet) würden das Update blockieren → sichern statt verlieren
        _git("stash", "push", "-m", "vor automatischem Update")
    r = _git("pull", "--ff-only", timeout=120)
    if r.returncode != 0:
        raise UserError("Das Update konnte nicht geladen werden: " + (r.stderr or r.stdout)[-300:])
    new = version()
    _cache.update(t=0.0, data=None)

    def restart():
        time.sleep(1.0)  # Antwort an den Browser noch rausschicken
        os._exit(RESTART_CODE)

    threading.Thread(target=restart, daemon=True).start()
    return {"ok": True, "version": new}
