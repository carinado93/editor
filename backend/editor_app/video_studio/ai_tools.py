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
    "enhance": {"status": "ready", "engine": "ffmpeg CAS + denoise (Real-ESRGAN upscale later)", "license": "LGPL"},
    "remove_object": {"status": "ready", "engine": "OpenCV inpainting in a box (small/static objects); "
                      "SAM2 + LaMa later", "license": "Apache-2.0"},
    "matting": {"status": "ready", "engine": "MediaPipe person segmentation: blur or colour background",
                "license": "Apache-2.0"},
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


def needs_frames(ai: dict | None) -> bool:
    return bool(ai) and (ai.get("bg") in ("blur", "color") or bool(ai.get("remove")))


def process_segment(seg: "Path", out: "Path", ai: dict, fps: float) -> None:
    """Bild-für-Bild-Werkzeuge auf einer gerenderten Aufnahme:
    bg = blur|color (Person freistellen, Hintergrund weich bzw. einfarbig), remove = [x, y, w, h] (0..1, Inpainting)."""
    import subprocess

    import cv2
    import numpy as np
    from PIL import Image

    from .. import fx, media
    from .render import encoder
    info = media.probe(seg)
    W, H = info["width"], info["height"]
    rd = subprocess.Popen([media.ffmpeg(), "-v", "error", "-i", str(seg), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                          stdout=subprocess.PIPE)
    wr = subprocess.Popen([media.ffmpeg(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", f"{fps:g}", "-i", "-", *encoder("intermediate"), "-pix_fmt", "yuv420p", str(out)],
                          stdin=subprocess.PIPE)
    seg_model = fx.Segmenter() if ai.get("bg") in ("blur", "color") else None
    box = None
    if ai.get("remove"):
        x, y, w, h = [float(v) for v in ai["remove"]]
        box = np.zeros((H, W), np.uint8)
        box[int(y * H):int((y + h) * H), int(x * W):int((x + w) * W)] = 255
        box = cv2.dilate(box, np.ones((9, 9), np.uint8))
    col = tuple(int(v) for v in (ai.get("color") or [201, 179, 236]))
    try:
        n = W * H * 3
        while True:
            buf = rd.stdout.read(n)
            if len(buf) < n:
                break
            fr = np.frombuffer(buf, np.uint8).reshape(H, W, 3).copy()
            if box is not None:
                fr = cv2.inpaint(fr, box, 7, cv2.INPAINT_TELEA)
            if seg_model is not None:
                m = np.asarray(seg_model.mask(Image.fromarray(fr))).astype(np.float32)[..., None] / 255
                if ai["bg"] == "blur":
                    bgf = cv2.GaussianBlur(fr, (0, 0), max(6, W / 60))
                else:
                    bgf = np.empty_like(fr)
                    bgf[:] = col
                fr = (fr * m + bgf * (1 - m)).astype(np.uint8)
            wr.stdin.write(fr.tobytes())
    finally:
        if seg_model is not None:
            seg_model.close()
        wr.stdin.close()
        wr.wait()
        rd.wait()
