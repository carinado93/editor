"""Arbeits-Warteschlange: Videos werden nacheinander verarbeitet (auch mehrere hintereinander)."""
from __future__ import annotations

import json
import queue
import threading
import traceback

from . import media, projects, transcribe
from .errors import explain

_queue: "queue.Queue[str]" = queue.Queue()
_started = False

# Anteil der Schritte am Gesamtfortschritt
STEPS = [
    ("pruefen", "Video wird geprüft", 0.01),
    ("ton", "Tonspur wird vorbereitet", 0.04),
    ("vorschau", "Vorschau-Video wird erstellt", 0.25),
    ("transkript", "Transkript wird erstellt", 0.70),
]


def enqueue(pid: str) -> None:
    projects.update(pid, status="warteschlange", message="Wartet auf Verarbeitung …", error=None)
    _queue.put(pid)


def _process(pid: str) -> None:
    p = projects.load(pid)
    src = projects.path(pid, p["original_file"])
    done = 0.0

    def stage(key: str):
        nonlocal done
        label, weight = next((l, w) for k, l, w in STEPS if k == key)
        base = done

        def report(f: float, msg: str | None = None):
            projects.update(pid, status="arbeitet", step=key, progress=round(base + weight * f, 4),
                            message=msg or label)
        report(0.0)
        done += weight
        return report

    rep = stage("pruefen")
    info = media.probe(src)
    thumb = projects.path(pid, "bild.jpg")
    if not thumb.exists():
        media.thumbnail(src, thumb, min(1.0, info["duration"] / 2))
    projects.update(pid, info=info)  # erst jetzt, damit das Vorschaubild schon da ist
    rep(1.0)

    wav = projects.path(pid, "ton.wav")
    rep = stage("ton")
    if not wav.exists():
        media.extract_audio(src, wav, info, lambda f: rep(f))

    # Vorschau-Video und Transkript laufen gleichzeitig (Video-Chip und Spracherkennung stören sich kaum).
    base = done
    w_proxy = next(w for k, _, w in STEPS if k == "vorschau")
    w_trans = next(w for k, _, w in STEPS if k == "transkript")
    state = {"proxy": 0.0, "trans": 0.0, "msg": "Transkript wird vorbereitet …"}
    lock = threading.Lock()

    def push():
        with lock:
            f_p, f_t, msg = state["proxy"], state["trans"], state["msg"]
        extra = f" · Vorschau-Video {f_p:.0%}" if f_p < 1 else ""
        projects.update(pid, status="arbeitet", step="transkript" if f_p >= 1 else "vorschau",
                        progress=round(base + w_proxy * f_p + w_trans * f_t, 4), message=msg + extra)

    def on_proxy(f: float):
        with lock:
            changed = int(f * 100) != int(state["proxy"] * 100)
            state["proxy"] = f
        if changed:
            push()

    def on_trans(f: float, msg: str):
        with lock:
            state["trans"], state["msg"] = f, msg
        push()

    proxy = projects.path(pid, "vorschau.mp4")
    proxy_error: list[BaseException] = []

    def proxy_job():
        try:
            if not proxy.exists():
                media.make_proxy(src, proxy, info, on_proxy)
            on_proxy(1.0)
        except BaseException as exc:  # noqa: BLE001
            proxy_error.append(exc)

    t = threading.Thread(target=proxy_job, daemon=True, name="vorschau")
    t.start()
    settings = p.get("settings", {})
    result = transcribe.transcribe(wav, projects.path(pid, "cache"), settings.get("model", "auto"),
                                   settings.get("language", "auto"), on_trans)
    if t.is_alive():
        on_trans(1.0, "Transkript fertig, Vorschau-Video wird noch erstellt")
    t.join()
    if proxy_error:
        raise proxy_error[0]
    projects.path(pid, "transkript.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    words = sum(len(s["words"]) for s in result["segments"])
    projects.update(pid, status="fertig", step="", progress=1.0, message="Fertig",
                    transcript={"language": result["language"], "model": result["model"],
                                "device": result["device"], "words": words})


def _worker() -> None:
    while True:
        pid = _queue.get()
        try:
            _process(pid)
        except Exception as exc:  # noqa: BLE001 – alles abfangen und verständlich anzeigen
            traceback.print_exc()
            try:
                projects.update(pid, status="fehler", error=explain(exc), message="Fehler")
            except Exception:
                pass
        finally:
            _queue.task_done()


def start() -> None:
    """Startet die Warteschlange und setzt unterbrochene Projekte fort."""
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_worker, daemon=True, name="verarbeitung").start()
    for p in reversed(projects.list_all()):
        if p["status"] in ("warteschlange", "arbeitet"):
            enqueue(p["id"])
