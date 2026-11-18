"""Pro-Werkzeuge (Schritt 9): welche es gibt, wie sie laufen und welche noch fehlen.

Alle generativen Werkzeuge laufen über eine austauschbare Schicht ("provider"): lokal (eigene Modelle auf
Carinas Grafikkarte) oder über eine externe API – die Oberfläche bleibt dieselbe.

Stand 18.11.2026:
  fertig, lokal (ffmpeg/OpenCV, kostenlos):
    stabilize      vidstab, 2 Durchgänge (minimal / recommended / most)        → Effekte-Tab, Stil
    denoise        hqdn3d bzw. nlmeans                                          → Effekte-Tab, Stil
    deflicker      ffmpeg deflicker                                             → Effekte-Tab
    optical_flow   Zeitlupe mit Zwischenbildern (minterpolate, im Final)       → Stil
    auto_reframe   Hochkant-Ausschnitt nach Bildinhalt (Kanten + Farbe)        → automatisch, Crop & zoom
    sharpen        Schärfe/Klarheit (unsharp), "Drone crisp"                    → Effekte, Stil
    auto_grade     Belichtung der Aufnahmen angleichen                          → Stil
    loudness       −14 LUFS                                                     → Stil
  noch nicht eingebaut (brauchen große Modelle oder eine API – Lizenzen beachten):
    enhance        Real-ESRGAN (BSD) über realesrgan-ncnn-vulkan
    remove_object  SAM2 (Apache-2.0) + LaMa (Apache-2.0); ProPainter ist NICHT kommerziell nutzbar
    matting        RVM (GPL-3.0) oder MediaPipe (schon in der App, für Personen)
    extend/remix/stylize/relight/lip_sync/eye_contact  → externe API (z. B. Higgsfield) oder später
  Gesichter (Face swap, Frisur, Mimik): nur mit Einwilligungs-Häkchen und "AI generated" in den Metadaten.
"""
from __future__ import annotations

TOOLS = {
    "stabilize": {"status": "ready", "engine": "ffmpeg vidstab"},
    "denoise": {"status": "ready", "engine": "ffmpeg hqdn3d/nlmeans"},
    "deflicker": {"status": "ready", "engine": "ffmpeg deflicker"},
    "optical_flow": {"status": "ready", "engine": "ffmpeg minterpolate"},
    "auto_reframe": {"status": "ready", "engine": "OpenCV saliency"},
    "sharpen": {"status": "ready", "engine": "ffmpeg unsharp"},
    "auto_grade": {"status": "ready", "engine": "brightness matching"},
    "loudness": {"status": "ready", "engine": "ffmpeg loudnorm"},
    "enhance": {"status": "planned", "engine": "Real-ESRGAN (ncnn-vulkan)", "license": "BSD-3"},
    "remove_object": {"status": "planned", "engine": "SAM2 + LaMa", "license": "Apache-2.0"},
    "matting": {"status": "planned", "engine": "RVM / MediaPipe", "license": "GPL-3.0 / Apache-2.0"},
    "extend": {"status": "provider", "engine": "external API"},
    "remix": {"status": "provider", "engine": "external API"},
    "stylize": {"status": "provider", "engine": "external API", "consent": True},
    "relight": {"status": "planned", "engine": "Depth-Anything-V2-Small", "license": "Apache-2.0"},
    "lip_sync": {"status": "later", "engine": "external API", "consent": True},
    "eye_contact": {"status": "later", "engine": "external API", "consent": True},
}


class Provider:
    """Schnittstelle für generative Werkzeuge. Neue Anbieter erben hiervon und registrieren sich in PROVIDERS."""
    name = "none"

    def run(self, tool: str, frames_dir: str, params: dict) -> str:   # pragma: no cover – noch kein Anbieter
        raise NotImplementedError(f"{tool} needs an AI provider – not installed yet.")


PROVIDERS: dict[str, Provider] = {"none": Provider()}


def status() -> dict:
    return TOOLS
