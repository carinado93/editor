"""Arbeits-Warteschlange: Videos werden nacheinander verarbeitet (auch mehrere hintereinander)."""
from __future__ import annotations

import json
import queue
import threading
import traceback

import time

from . import cutstore, gaze, media, projects, render, transcribe
from .errors import UserError, explain

_queue: "queue.Queue[tuple[str, str, dict]]" = queue.Queue()
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
    _queue.put((pid, "vorbereiten", {}))


def enqueue_render(pid: str, quality: str) -> None:
    p = projects.load(pid)
    if p["status"] != "fertig":
        raise UserError("Das Video wird noch vorbereitet. Bitte warte, bis es fertig ist.")
    if (p.get("render") or {}).get("status") in ("warteschlange", "arbeitet"):
        raise UserError("Das Video wird schon gerendert.")
    if quality not in render.QUALITIES:
        raise UserError("Unbekannte Qualität.")
    projects.update(pid, render={"status": "warteschlange", "progress": 0.0, "message": "Wartet …",
                                 "error": None, "quality": quality})
    _queue.put((pid, "rendern", {"quality": quality}))


def enqueue_clip(pid: str, cid: str) -> None:
    _queue.put((pid, "clip", {"cid": cid}))


def _render_clip(pid: str, cid: str) -> None:
    from . import clips, config, cuts, gaze

    p = projects.load(pid)
    c = clips.get_clip(pid, cid)

    def rep(f: float, msg: str):
        clips.update_clip(pid, cid, status="arbeitet", progress=round(f, 3), message=msg)

    rep(0.0, "Startet …")
    t = json.loads(projects.path(pid, "transkript.json").read_text(encoding="utf-8"))
    v = cutstore.view(pid)
    gf = projects.path(pid, "blick.json")
    face = gaze.face_box(json.loads(gf.read_text(encoding="utf-8"))) if gf.exists() else None
    name = render.safe_name(c.get("title") or p["name"])
    out = projects.path(pid, "export") / f"reel_{name}_{time.strftime('%H%M%S')}.mp4"
    res = render.render_clip(projects.path(pid, p["original_file"]), p["info"], c["segments"], out,
                             projects.path(pid, "cache"), cuts.flat_words(t), v["evaluation"]["flags"],
                             c.get("hook_text", ""), face, str(config.ROOT / "assets" / "fonts"), rep,
                             c.get("texts", []))
    clips.update_clip(pid, cid, status="fertig", progress=1.0, message="Fertig", file=res["file"],
                      size=res["size"], srt=res["srt"])


def _render(pid: str, quality: str) -> None:
    p = projects.load(pid)

    def rep(f: float, msg: str):
        projects.update(pid, render={**(projects.load(pid).get("render") or {}), "status": "arbeitet",
                                     "progress": round(f, 4), "message": msg})

    rep(0.0, "Rendern startet …")
    v = cutstore.view(pid)
    segments = v["evaluation"]["keep"]
    name = render.safe_name(p["name"])
    suffix = "reel" if p["mode"] == "reel" else "schnitt"
    out = projects.path(pid, "export") / f"{name}_{suffix}_{time.strftime('%Y%m%d-%H%M%S')}.mp4"
    tf = projects.path(pid, "transkript.json")
    gf = projects.path(pid, "blick.json")
    from . import config, cuts
    options = {
        **v["cutlist"]["render_options"],
        "words": cuts.flat_words(json.loads(tf.read_text(encoding="utf-8"))),
        "flags": v["evaluation"]["flags"],
        "buzzwords": v["cutlist"].get("buzzwords", []),
        "overlays": [o for o in v["cutlist"].get("overlays", []) if o.get("on", True)],
        "gaze": json.loads(gf.read_text(encoding="utf-8")) if gf.exists() else None,
        "fonts_dir": str(config.ROOT / "assets" / "fonts"),
    }
    result = render.render(projects.path(pid, p["original_file"]), p["info"], segments, out,
                           projects.path(pid, "cache"), quality, rep, options)
    # Schnittliste zum fertigen Video dazulegen (zum Nachvollziehen)
    (out.with_suffix(".schnitte.json")).write_text(
        json.dumps({"keep": segments, "settings": v["cutlist"]["settings"]}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    exports = (projects.load(pid).get("exports") or []) + [{**result, "created": time.time()}]
    projects.update(pid, exports=exports,
                    render={"status": "fertig", "progress": 1.0, "message": "Fertig", "error": None,
                            "quality": quality, "file": result["file"]})


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
    silent = not info["has_audio"]
    if silent and p["mode"] == "youtube":
        raise UserError("Das Video hat keine Tonspur. Für den YouTube-Rohschnitt braucht die App deine Stimme. "
                        "Für stumme Clips bitte den Modus „Reel veredeln“ wählen.")
    if not silent and not wav.exists():
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
    if silent:  # stummer Clip (Reel): kein Transkript, Texte kommen aus Carinas Idee/Prompt
        lang = settings.get("language", "auto")
        result = {"language": lang if lang in ("de", "en") else "en", "model": "-", "device": "-",
                  "duration": info["duration"], "segments": [], "silent": True}
        on_trans(1.0, "Kein Ton – Texte kommen aus deiner Idee")
    else:
        result = transcribe.transcribe(wav, projects.path(pid, "cache"), settings.get("model", "auto"),
                                       settings.get("language", "auto"), on_trans)
    if t.is_alive():
        on_trans(1.0, "Transkript fertig, Vorschau-Video wird noch erstellt")
    t.join()
    if proxy_error:
        raise proxy_error[0]
    projects.path(pid, "transkript.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    words = sum(len(s["words"]) for s in result["segments"])
    if p["mode"] in ("youtube", "reel"):
        cutstore.create(pid, result)  # Schnittvorschläge (Reel: Texte, ohne Schnitte) gleich mit berechnen
        projects.update(pid, status="arbeitet", step="blick", progress=0.97, message="Blick-Erkennung …")
        _gaze(pid)
        projects.update(pid, message="Buzzwords werden ausgesucht …", progress=0.99)
        _buzz(pid)
    projects.update(pid, status="fertig", step="", progress=1.0, message="Fertig",
                    transcript={"language": result["language"], "model": result["model"],
                                "device": result["device"], "words": words})


def _gaze(pid: str) -> None:
    """Blick-Erkennung auf dem Vorschau-Video. Fehler hier stoppen nichts (ist nur ein Zusatz)."""
    out = projects.path(pid, "blick.json")
    if out.exists():
        try:
            if json.loads(out.read_text(encoding="utf-8")).get("version") == gaze.VERSION:
                return
        except ValueError:
            pass
    try:
        def rep(f: float):
            p = projects.load(pid)
            if p["status"] == "arbeitet":
                projects.update(pid, message=f"Blick-Erkennung ({f:.0%})")
        data = gaze.analyze(projects.path(pid, "vorschau.mp4"), rep)
        out.write_text(json.dumps(data), encoding="utf-8")
        cutstore.refresh(pid)
    except Exception:  # noqa: BLE001
        traceback.print_exc()


def _gaze_current(pid: str) -> bool:
    f = projects.path(pid, "blick.json")
    try:
        return f.exists() and json.loads(f.read_text(encoding="utf-8")).get("version") == gaze.VERSION
    except ValueError:
        return False


def _buzz(pid: str) -> None:
    try:
        cutstore.auto_buzzwords(pid)
    except Exception:  # noqa: BLE001 – Zusatzfunktion, darf nichts stoppen
        traceback.print_exc()


def _worker() -> None:
    while True:
        pid, kind, opts = _queue.get()
        try:
            if kind == "rendern":
                _render(pid, opts["quality"])
            elif kind == "clip":
                _render_clip(pid, opts["cid"])
            elif kind == "blick":
                _gaze(pid)
                _buzz(pid)
            elif kind == "buzz":
                _buzz(pid)
            else:
                _process(pid)
        except Exception as exc:  # noqa: BLE001 – alles abfangen und verständlich anzeigen
            traceback.print_exc()
            try:
                if kind == "clip":
                    from . import clips
                    clips.update_clip(pid, opts["cid"], status="fehler", error=explain(exc), message="Fehler")
                elif kind == "rendern":
                    r = projects.load(pid).get("render") or {}
                    projects.update(pid, render={**r, "status": "fehler", "error": explain(exc), "message": "Fehler"})
                else:
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
        elif p["status"] == "fertig" and p["mode"] in ("youtube", "reel") and not _gaze_current(p["id"]):
            _queue.put((p["id"], "blick", {}))  # ältere Projekte bekommen die Blick-Erkennung nachträglich
        elif p["status"] == "fertig" and p["mode"] in ("youtube", "reel"):
            _queue.put((p["id"], "buzz", {}))  # einmalig automatische Buzzwords (macht nichts, wenn schon erledigt)
        elif (p.get("render") or {}).get("status") in ("warteschlange", "arbeitet"):
            projects.update(p["id"], render={**p["render"], "status": "fehler",
                                             "error": "Das Rendern wurde unterbrochen (App beendet). Bitte nochmal starten."})
