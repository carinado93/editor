"""Pfade und Grundeinstellungen. Alles liegt im App-Ordner, nichts woanders auf dem PC."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECTS_DIR = Path(os.environ.get("EDITOR_PROJECTS_DIR", ROOT / "projekte"))
MODELS_DIR = Path(os.environ.get("EDITOR_MODELS_DIR", ROOT / "modelle"))
FRONTEND_DIST = ROOT / "frontend" / "dist"
TOOLS_DIR = ROOT / "tools"

HOST = os.environ.get("EDITOR_HOST", "127.0.0.1")
PORT = int(os.environ.get("EDITOR_PORT", "8000"))

# Vorschau-Video ("Proxy"): klein und schnell, nur zum Anschauen im Browser
PROXY_HEIGHT = 540
# Lange Videos werden in Stücke dieser Länge (Sekunden) transkribiert und zwischengespeichert
CHUNK_SECONDS = 600

MODES = {
    "youtube": "YouTube (langes Video, Rohschnitt)",
    "reel": "Reel/Short veredeln",
    "idee": "Reel aus Idee",
}

for d in (PROJECTS_DIR, MODELS_DIR):
    d.mkdir(parents=True, exist_ok=True)
