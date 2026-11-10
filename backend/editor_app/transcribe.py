"""Transkript mit Wort-Zeitstempeln (faster-whisper, läuft komplett auf dem PC).

- Grafikkarte (Nvidia/CUDA), wenn vorhanden, sonst Prozessor.
- Lange Videos werden in Stücke von ca. 10 Minuten geteilt (an einer leisen Stelle).
  Jedes fertige Stück wird gespeichert: Bricht etwas ab, geht es beim nächsten Mal dort weiter.
- Füllwörter (äh, ähm, um, uh …) sollen mitgeschrieben werden, damit man sie später schneiden kann.
"""
from __future__ import annotations

import functools
import glob
import json
import os
import sys
import wave
from pathlib import Path
from typing import Callable

import numpy as np

from .config import CHUNK_SECONDS, MODELS_DIR

SR = 16000
CACHE_VERSION = 2  # erhöhen, wenn sich die Einstellungen der Spracherkennung ändern
Progress = Callable[[float, str], None]

# Whisper lässt Füllwörter gern weg. Diese "Hotwords" und der Start-Text bringen es dazu, sie mitzuschreiben.
FILLER_PROMPT = {
    "de": "Ähm, also, äh, ich mein, hm, ja. Ähm, genau, quasi, äh.",
    "en": "Um, uh, so, like, you know, hmm. Uh, I mean, um.",
}
FILLER_HOTWORDS = {
    "de": "ähm äh hm also quasi",
    "en": "um uh hmm like",
}


def _add_cuda_dll_dirs() -> None:
    """Unter Windows liegen die CUDA-Bibliotheken aus pip in site-packages/nvidia/*/bin."""
    if sys.platform != "win32":
        return
    for base in sys.path:
        for d in glob.glob(os.path.join(base, "nvidia", "*", "bin")):
            try:
                os.add_dll_directory(d)
                os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            except OSError:
                pass


@functools.cache
def gpu_available() -> bool:
    _add_cuda_dll_dirs()
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def default_model(use_gpu: bool) -> str:
    # Mit Grafikkarte: großes, schnelles Modell (sehr gut für Deutsch). Ohne: "small" (guter Kompromiss).
    return "large-v3-turbo" if use_gpu else "small"


MODEL_CHOICES = {
    "auto": "Automatic (recommended)",
    "small": "small – fast, good (processor)",
    "medium": "medium – more accurate, slower",
    "large-v3-turbo": "large-v3-turbo – very accurate (graphics card)",
}

_loaded: dict[tuple, object] = {}


def load_model(name: str, use_gpu: bool):
    from faster_whisper import WhisperModel

    key = (name, use_gpu)
    if key not in _loaded:
        _loaded.clear()  # immer nur ein Modell im Speicher
        if use_gpu:
            _loaded[key] = WhisperModel(name, device="cuda", compute_type="int8_float16",
                                        download_root=str(MODELS_DIR))
        else:
            threads = max(1, (os.cpu_count() or 4) - 1)
            _loaded[key] = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=threads,
                                        download_root=str(MODELS_DIR))
    return _loaded[key]


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        assert w.getframerate() == SR and w.getnchannels() == 1
        data = w.readframes(w.getnframes())
    return np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0


def chunk_bounds(audio: np.ndarray, chunk_seconds: int = CHUNK_SECONDS, search: float = 15.0) -> list[tuple[int, int]]:
    """Teilt lange Aufnahmen in Stücke. Geschnitten wird an der leisesten Stelle nahe der Grenze,
    damit kein Wort zerteilt wird."""
    n = len(audio)
    step = chunk_seconds * SR
    if n <= step + search * SR:
        return [(0, n)]
    frame = int(0.05 * SR)
    bounds, start = [], 0
    while n - start > step + search * SR:
        target = start + step
        lo, hi = int(target - search * SR), int(target + search * SR)
        seg = audio[lo:hi]
        frames = seg[: len(seg) // frame * frame].reshape(-1, frame)
        quiet = int(np.argmin(np.sqrt((frames ** 2).mean(axis=1))))
        cut = lo + quiet * frame + frame // 2
        bounds.append((start, cut))
        start = cut
    bounds.append((start, n))
    return bounds


def detect_language(model, audio: np.ndarray) -> str:
    """Erkennt Deutsch/Englisch aus den ersten ~30 s mit Sprache."""
    sample = audio[: 60 * SR]
    try:
        lang, prob, _ = model.detect_language(sample)
    except Exception:
        _, info = model.transcribe(sample[: 30 * SR], beam_size=1)
        lang = info.language
    return lang if lang in ("de", "en") else lang


def _transcribe_chunk(model, audio: np.ndarray, offset: float, lang: str, on_seconds: Callable[[float], None]) -> dict:
    segments, _info = model.transcribe(
        audio,
        language=lang,
        word_timestamps=True,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300, "speech_pad_ms": 200},
        # Mit Vorwissen aus dem vorherigen Satz: richtige Satzzeichen und Großschreibung.
        # Gegen "erfundene" Sätze in langen Pausen schützt hallucination_silence_threshold.
        condition_on_previous_text=True,
        hallucination_silence_threshold=2.0,
        initial_prompt=FILLER_PROMPT.get(lang),
        hotwords=FILLER_HOTWORDS.get(lang),
    )
    out_segments = []
    for seg in segments:
        words = [
            {"w": w.word.strip(), "s": round(w.start + offset, 3), "e": round(w.end + offset, 3),
             "p": round(w.probability, 3)}
            for w in (seg.words or []) if w.word.strip()
        ]
        out_segments.append({"s": round(seg.start + offset, 3), "e": round(seg.end + offset, 3),
                             "text": seg.text.strip(), "words": words})
        on_seconds(seg.end)
    return {"segments": out_segments}


def transcribe(wav: Path, cache_dir: Path, model_name: str = "auto", language: str = "auto",
               progress: Progress | None = None) -> dict:
    """Erstellt das Transkript. Gibt {language, model, device, segments:[{s,e,text,words:[{w,s,e,p}]}]} zurück."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    report = progress or (lambda f, m: None)
    use_gpu = gpu_available()
    name = default_model(use_gpu) if model_name == "auto" else model_name
    report(0.0, "Loading speech recognition model (downloaded the first time) …")
    try:
        model = load_model(name, use_gpu)
    except Exception:
        if not use_gpu:
            raise
        use_gpu = False  # Grafikkarte klappt nicht → Prozessor
        name = default_model(False) if model_name in ("auto", "large-v3-turbo") else model_name
        model = load_model(name, False)

    audio = read_wav(wav)
    total = len(audio) / SR
    lang = language
    if lang == "auto":
        report(0.0, "Detecting language …")
        lang = detect_language(model, audio)

    bounds = chunk_bounds(audio)
    segments: list[dict] = []
    done_seconds = 0.0
    for i, (a, b) in enumerate(bounds):
        cache = cache_dir / f"stueck_v{CACHE_VERSION}_{i:03d}_{name}_{lang}_{a}_{b}.json"
        if cache.exists():
            part = json.loads(cache.read_text(encoding="utf-8"))
        else:
            label = f"Transcript: part {i + 1} of {len(bounds)}" if len(bounds) > 1 else "Creating transcript"
            base = done_seconds

            def on_seconds(sec: float, base=base, label=label):
                report(min(0.999, (base + sec) / total), label)

            def run_chunk(m):
                return _transcribe_chunk(m, audio[a:b], a / SR, lang, on_seconds)

            try:
                part = run_chunk(model)
            except Exception as exc:
                if not use_gpu or "cuda" not in str(exc).lower() and "cudnn" not in str(exc).lower() \
                        and "cublas" not in str(exc).lower():
                    raise
                # Grafikkarten-Bibliothek fehlt → automatisch mit dem Prozessor weiter
                report(base / total, "Graphics card not usable, continuing with the processor …")
                use_gpu = False
                name = default_model(False) if model_name in ("auto", "large-v3-turbo") else model_name
                model = load_model(name, False)
                part = run_chunk(model)
            cache.write_text(json.dumps(part, ensure_ascii=False), encoding="utf-8")
        segments.extend(part["segments"])
        done_seconds = b / SR
        report(min(0.999, done_seconds / total), f"Part {i + 1} of {len(bounds)} done")

    result = {"language": lang, "model": name, "device": "GPU" if use_gpu else "CPU",
              "duration": total, "segments": segments}
    from . import relisten
    try:
        relisten.apply(result, audio, model, report)
    except Exception:  # noqa: BLE001 – Nachhören ist ein Zusatz, das Transkript gibt es auch ohne
        import traceback
        traceback.print_exc()
    report(1.0, "Transcript done")
    return result


def relisten_existing(wav: Path, transcript: dict, progress: Progress | None = None) -> int:
    """Nachhören für ein schon fertiges Transkript (ältere Projekte)."""
    from . import relisten
    use_gpu = gpu_available()
    name = transcript.get("model") if transcript.get("model") not in (None, "-") else default_model(use_gpu)
    try:
        model = load_model(name, use_gpu)
    except Exception:
        if not use_gpu:
            raise
        model = load_model(default_model(False), False)
    return relisten.apply(transcript, read_wav(wav), model, progress)
