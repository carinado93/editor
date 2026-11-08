"""Blick-Erkennung: Wann schaut Carina nicht in die Kamera (Script/Handy lesen)?

MediaPipe Face Landmarker (läuft lokal, schnell auch ohne Grafikkarte) liefert pro Bild:
- Kopfhaltung (Neigung/Drehung) aus der Transformationsmatrix,
- Augen-Werte ("Blendshapes"): Blick nach unten/oben/seitlich, Augen zu, Lächeln.

Kalibrierung pro Video: Die häufigste Haltung ist "Blick in die Kamera". Gemessen wird die Abweichung davon.
Erst wenn der Blick länger als `min_seconds` weg ist, wird die Stelle markiert (kurzes Nachdenken bleibt).
Nebenbei wird die Gesichtsposition gespeichert (für Zoom-Ausschnitt und Text-Platzierung).
"""
from __future__ import annotations

import math
import urllib.request
from pathlib import Path
from typing import Callable

import numpy as np

from .config import MODELS_DIR
from .errors import UserError

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/"
             "face_landmarker.task")
SAMPLE_FPS = 5.0
VERSION = 2  # erhöhen, wenn neue Werte gespeichert werden (ältere Analysen werden dann neu gemacht)

DEFAULTS = {
    "min_seconds": 1.5,   # so lange muss der Blick weg sein
    "pitch_deg": 12.0,    # Kopf nach unten/oben gegenüber der Kamera-Haltung
    "yaw_deg": 20.0,      # Kopf zur Seite
    "eyes_down": 0.25,    # Augen nach unten (0..1, zusätzlich zur normalen Haltung)
    "eyes_side": 0.35,    # Augen zur Seite
}


def model_path() -> Path:
    p = MODELS_DIR / "face_landmarker.task"
    if not p.exists():
        try:
            tmp = p.with_suffix(".tmp")
            urllib.request.urlretrieve(MODEL_URL, tmp)
            tmp.replace(p)
        except Exception as exc:
            raise UserError("Das Gesichts-Modell für die Blick-Erkennung konnte nicht geladen werden. "
                            "Bitte Internet prüfen (nur beim ersten Mal nötig).") from exc
    return p


def _angles(m: np.ndarray) -> tuple[float, float]:
    """Neigung (pitch) und Drehung (yaw) in Grad aus der 4x4-Transformationsmatrix."""
    r = m[:3, :3]
    pitch = math.degrees(math.atan2(r[2, 1], r[2, 2]))
    yaw = math.degrees(math.asin(max(-1.0, min(1.0, -r[2, 0]))))
    return pitch, yaw


def analyze(video: Path, progress: Callable[[float], None] | None = None) -> dict:
    """Liest das (kleine) Vorschau-Video mit 5 Bildern pro Sekunde und misst Gesicht und Blick."""
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise UserError("Das Vorschau-Video konnte für die Blick-Erkennung nicht geöffnet werden.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(1, round(fps / SAMPLE_FPS))
    opts = vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path())),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=True,
    )
    samples = []
    with vision.FaceLandmarker.create_from_options(opts) as lm:
        idx = 0
        while True:
            ok = cap.grab()
            if not ok:
                break
            if idx % step == 0:
                ok, frame = cap.retrieve()
                if not ok:
                    break
                t = idx / fps
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                res = lm.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), int(t * 1000))
                s = {"t": round(t, 3), "face": False}
                if res.face_landmarks:
                    pts = np.array([(p.x, p.y) for p in res.face_landmarks[0]])
                    x0, y0 = pts.min(axis=0)
                    x1, y1 = pts.max(axis=0)
                    bs = {c.category_name: c.score for c in res.face_blendshapes[0]}
                    pitch, yaw = _angles(np.array(res.facial_transformation_matrixes[0]))
                    s.update({
                        "face": True,
                        "box": [round(float(x0), 4), round(float(y0), 4), round(float(x1), 4), round(float(y1), 4)],
                        "pitch": round(pitch, 2), "yaw": round(yaw, 2),
                        "down": round((bs.get("eyeLookDownLeft", 0) + bs.get("eyeLookDownRight", 0)) / 2, 3),
                        "up": round((bs.get("eyeLookUpLeft", 0) + bs.get("eyeLookUpRight", 0)) / 2, 3),
                        "side": round(max(bs.get("eyeLookOutLeft", 0) + bs.get("eyeLookInRight", 0),
                                          bs.get("eyeLookInLeft", 0) + bs.get("eyeLookOutRight", 0)) / 2, 3),
                        "blink": round((bs.get("eyeBlinkLeft", 0) + bs.get("eyeBlinkRight", 0)) / 2, 3),
                        "smile": round((bs.get("mouthSmileLeft", 0) + bs.get("mouthSmileRight", 0)) / 2, 3),
                        "tongue": round(bs.get("tongueOut", 0), 3),
                        "jaw": round(bs.get("jawOpen", 0), 3),
                        "grimace": round(max(bs.get("mouthFunnel", 0), bs.get("mouthPucker", 0),
                                             (bs.get("noseSneerLeft", 0) + bs.get("noseSneerRight", 0)) / 2), 3),
                    })
                samples.append(s)
                if progress and total:
                    progress(min(1.0, idx / total))
            idx += 1
    cap.release()
    if progress:
        progress(1.0)
    return {"version": VERSION, "sample_fps": SAMPLE_FPS, "samples": samples}


def baseline(samples: list[dict]) -> dict:
    faces = [s for s in samples if s["face"]]
    if not faces:
        return {}
    return {k: float(np.median([s[k] for s in faces])) for k in ("pitch", "yaw", "down", "side")}


def away_events(data: dict, settings: dict | None = None) -> list[dict]:
    """Zeitbereiche, in denen der Blick länger als min_seconds nicht in der Kamera ist."""
    cfg = {**DEFAULTS, **(settings or {})}
    samples = data.get("samples", [])
    base = baseline(samples)
    if not base:
        return []
    dt = 1.0 / data.get("sample_fps", SAMPLE_FPS)

    def why(s: dict) -> str | None:
        if not s["face"]:
            return "Gesicht nicht zu sehen"
        if abs(s["pitch"] - base["pitch"]) > cfg["pitch_deg"]:
            return "Kopf geneigt"
        if abs(s["yaw"] - base["yaw"]) > cfg["yaw_deg"]:
            return "Kopf zur Seite"
        if s["down"] - base["down"] > cfg["eyes_down"] and s["blink"] < 0.5:
            return "Augen nach unten"
        if s["side"] - base["side"] > cfg["eyes_side"]:
            return "Augen zur Seite"
        return None

    events, cur = [], None
    for s in samples:
        r = why(s)
        if r:
            if cur is None:
                cur = {"start": s["t"], "end": s["t"] + dt, "reasons": {}}
            cur["end"] = s["t"] + dt
            cur["reasons"][r] = cur["reasons"].get(r, 0) + 1
        elif cur is not None:
            events.append(cur)
            cur = None
    if cur:
        events.append(cur)
    out = []
    for e in events:
        length = e["end"] - e["start"]
        if length >= cfg["min_seconds"]:
            main = max(e["reasons"], key=e["reasons"].get)
            out.append({"start": round(e["start"], 2), "end": round(e["end"], 2), "length": round(length, 2),
                        "reason": main})
    return out


def face_center(data: dict, start: float, end: float) -> tuple[float, float] | None:
    """Mittlere Gesichtsposition (0..1) in einem Zeitbereich, für den Zoom-Ausschnitt."""
    pts = [((s["box"][0] + s["box"][2]) / 2, (s["box"][1] + s["box"][3]) / 2)
           for s in data.get("samples", []) if s["face"] and start <= s["t"] <= end]
    if not pts:
        return None
    a = np.median(np.array(pts), axis=0)
    return float(a[0]), float(a[1])


def face_box(data: dict) -> list[float] | None:
    """Bereich, in dem das Gesicht fast immer ist (für "Text nie übers Gesicht")."""
    boxes = np.array([s["box"] for s in data.get("samples", []) if s["face"]])
    if not len(boxes):
        return None
    return [float(np.percentile(boxes[:, 0], 5)), float(np.percentile(boxes[:, 1], 5)),
            float(np.percentile(boxes[:, 2], 95)), float(np.percentile(boxes[:, 3], 95))]
