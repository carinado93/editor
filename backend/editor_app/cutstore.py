"""Speichert die Schnittliste eines Projekts (schnitte.json) mit Rückgängig-Funktion.

Nicht-destruktiv: Das Video wird nie verändert, gespeichert wird nur, welche Wörter/Pausen wegfallen.
"""
from __future__ import annotations

import copy
import json
import re
import threading

from . import cuts, gaze, noises, projects
from .errors import UserError

_lock = threading.RLock()
MAX_UNDO = 50


def _transcript(pid: str) -> dict:
    f = projects.path(pid, "transkript.json")
    if not f.exists():
        raise UserError("Das Transkript ist noch nicht fertig.")
    return json.loads(f.read_text(encoding="utf-8"))


def _gaze_events(pid: str, settings: dict | None = None) -> list[dict]:
    f = projects.path(pid, "blick.json")
    if not f.exists():
        return []
    try:
        return gaze.away_events(json.loads(f.read_text(encoding="utf-8")), (settings or {}).get("gaze"))
    except (OSError, ValueError):
        return []


def _noises(pid: str, t: dict) -> list[dict]:
    try:
        gf = projects.path(pid, "blick.json")
        face = json.loads(gf.read_text(encoding="utf-8")).get("samples") if gf.exists() else None
        return noises.find(projects.path(pid, "ton.wav"), cuts.flat_words(t), face_samples=face)
    except Exception:  # noqa: BLE001 – Zusatz, darf nie stören
        return []


def _file(pid: str):
    return projects.path(pid, "schnitte.json")


def _save(pid: str, cutlist: dict) -> None:
    f = _file(pid)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(cutlist, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)


def _apply_overrides(cutlist: dict) -> None:
    ov = cutlist.get("overrides", {})
    for d in cutlist["detections"]:
        if d["id"] in ov:
            d["active"] = ov[d["id"]]


def _mode(pid: str) -> str:
    try:
        return projects.load(pid).get("mode", "youtube")
    except Exception:  # noqa: BLE001
        return "youtube"


def dur_total(t: dict) -> float:
    words = cuts.flat_words(t)
    return t.get("duration", words[-1]["e"] if words else 0.0)


def default_hook(t: dict) -> list[dict]:
    """Hook-Karte am Anfang: erster Satz, mindestens 4,4 s sichtbar (Lesbarkeit), ein Wort als Akzent markiert."""
    from . import buzz

    words = cuts.flat_words(t)
    if not words:
        return []
    sent = []
    for w in words:
        sent.append(w)
        if re.search(r"[.!?…]$", w["w"]) or len(sent) >= 14:
            break
    # Versprecher/Neuanfänge im Hook weglassen ("I decided to make a, I decided to make a giveaway")
    mini = {"language": t.get("language", "en"), "duration": dur_total(t),
            "segments": [{"s": 0, "e": 0, "text": "", "words": sent}]}
    flags = cuts.evaluate(mini, cuts.build(mini, cuts.default_settings(mini["language"])))["flags"]
    sent = [w for w, f in zip(sent, flags) if not f] or sent
    text_words = [re.sub(r"[.,;:]+$", "", w["w"]) if k == len(sent) - 1 else w["w"] for k, w in enumerate(sent)]
    if text_words:
        text_words[0] = text_words[0][:1].upper() + text_words[0][1:]
    key = next((k for k, w in enumerate(text_words) if cuts.norm(w) in buzz.THEMEN), len(text_words) - 1)
    text_words[key] = f"*{text_words[key]}*"
    dur = t.get("duration", words[-1]["e"])
    return [{"id": "hook", "kind": "hook", "start": 0.2, "end": round(min(dur, max(0.2 + 4.6, sent[-1]["e"] + 0.4)), 2),
             "text": " ".join(text_words), "on": True}]


def create(pid: str, transcript: dict | None = None) -> dict:
    t = transcript or _transcript(pid)
    settings = cuts.default_settings(t.get("language", "de"))
    reel = _mode(pid) == "reel"
    if reel:
        settings["no_cuts"] = True
    cl = cuts.build(t, settings, gaze_events=_gaze_events(pid))
    if reel:
        cl["render_options"] = dict(REEL_RENDER_DEFAULTS)
        cl["overlays"] = default_hook(t)
    cl["overrides"] = {}
    cl["history"] = []
    cl["noises"] = _noises(pid, t)
    cl["noises_v"] = noises.VERSION
    _save(pid, cl)
    return cl


def load(pid: str) -> dict:
    f = _file(pid)
    if not f.exists():
        return create(pid)
    cl = json.loads(f.read_text(encoding="utf-8"))
    if cl.get("noises_v") != noises.VERSION:  # ältere Projekte: Laute (neu) suchen
        cl["noises"] = _noises(pid, _transcript(pid))
        cl["noises_v"] = noises.VERSION
        _save(pid, cl)
    return cl


def view(pid: str, cutlist: dict | None = None) -> dict:
    """Schnittliste + Auswertung (welche Wörter fallen weg, welche Zeitbereiche bleiben, neue Länge)."""
    t = _transcript(pid)
    cl = cutlist or load(pid)
    ev = cuts.evaluate(t, cl)
    public = {k: v for k, v in cl.items() if k != "history"}
    public.setdefault("buzzwords", [])
    public.setdefault("overlays", [])
    defaults = REEL_RENDER_DEFAULTS if cl["settings"].get("no_cuts") else RENDER_DEFAULTS
    public["render_options"] = {**defaults, **cl.get("render_options", {})}
    return {"cutlist": public, "evaluation": ev, "can_undo": bool(cl.get("history"))}


def _change(pid: str, fn) -> dict:
    with _lock:
        cl = load(pid)
        snapshot = {k: copy.deepcopy(v) for k, v in cl.items() if k != "history"}
        fn(cl)
        cl.setdefault("history", []).append(snapshot)
        cl["history"] = cl["history"][-MAX_UNDO:]
        _save(pid, cl)
        return view(pid, cl)


def toggle_detection(pid: str, det_id: str, active: bool) -> dict:
    def fn(cl):
        found = False
        for d in cl["detections"]:
            if d["id"] == det_id:
                d["active"] = active
                found = True
                # Manuelle Einzelwort-Änderungen in diesem Bereich aufheben, damit der Klick sichtbar wirkt
                rng = set(range(d["start"], d["end"]))
                cl["manual"]["keep"] = [k for k in cl["manual"]["keep"] if k not in rng]
                cl["manual"]["cut"] = [k for k in cl["manual"]["cut"] if k not in rng]
        if not found:
            raise UserError("Diesen Schnitt gibt es nicht mehr. Bitte Seite neu laden.")
        cl.setdefault("overrides", {})[det_id] = active
    return _change(pid, fn)


def set_words(pid: str, indices: list[int], cut: bool) -> dict:
    """Wörter von Hand schneiden (cut=True) oder wiederherstellen (cut=False)."""
    def fn(cl):
        keep, man_cut = set(cl["manual"]["keep"]), set(cl["manual"]["cut"])
        for k in indices:
            if cut:
                man_cut.add(k)
                keep.discard(k)
            else:
                man_cut.discard(k)
                keep.add(k)
        cl["manual"] = {"keep": sorted(keep), "cut": sorted(man_cut)}
    return _change(pid, fn)


def set_pause(pid: str, after: int, keep: bool) -> dict:
    def fn(cl):
        pk = set(cl.get("pause_keep", []))
        (pk.add if keep else pk.discard)(after)
        cl["pause_keep"] = sorted(pk)
    return _change(pid, fn)


def update_settings(pid: str, settings: dict) -> dict:
    t = _transcript(pid)

    def fn(cl):
        new = {**cl["settings"], **settings}
        if new.get("tempo") not in cuts.TEMPO:
            raise UserError("Tempo muss locker, normal oder straff sein.")
        new["max_gap"] = max(1.0, min(15.0, float(new.get("max_gap", 5.0))))
        new["signal_words"] = [w.strip() for w in new.get("signal_words", []) if w.strip()]
        rebuilt = cuts.build(t, new, cl["manual"], cl.get("pause_keep"), _gaze_events(pid, new))
        cl["settings"] = new
        cl["detections"] = rebuilt["detections"]
        _apply_overrides(cl)
    return _change(pid, fn)


def reset(pid: str) -> dict:
    t = _transcript(pid)

    def fn(cl):
        fresh = cuts.build(t, cl["settings"], gaze_events=_gaze_events(pid, cl["settings"]))
        cl.update({"detections": fresh["detections"], "manual": {"cut": [], "keep": []}, "pause_keep": [],
                   "overrides": {}})
    return _change(pid, fn)


def undo(pid: str) -> dict:
    with _lock:
        cl = load(pid)
        hist = cl.get("history", [])
        if not hist:
            raise UserError("Es gibt nichts zum Rückgängigmachen.")
        prev = hist.pop()
        prev["history"] = hist
        _save(pid, prev)
        return view(pid, prev)


def refresh(pid: str) -> None:
    """Erkennung neu laufen lassen (z. B. wenn die Blick-Erkennung fertig ist), Änderungen bleiben erhalten."""
    if not _file(pid).exists():
        create(pid)
        return
    t = _transcript(pid)
    with _lock:
        cl = load(pid)
        rebuilt = cuts.build(t, cl["settings"], cl["manual"], cl.get("pause_keep"), _gaze_events(pid, cl["settings"]))
        cl["detections"] = rebuilt["detections"]
        cl["noises"] = _noises(pid, t)  # nach neuer Blick-Analyse: Grimassen mit einbeziehen
        cl["noises_v"] = noises.VERSION
        _apply_overrides(cl)
        _save(pid, cl)


RENDER_DEFAULTS = {"zoom": True, "loudness": True, "denoise": False, "subtitles": "srt", "karaoke": False}
# Reel veredeln: Format, Länge, Tempo, Ton bleiben exakt – kein Zoom, keine Lautstärke-Änderung
REEL_RENDER_DEFAULTS = {"zoom": False, "loudness": False, "denoise": False, "subtitles": "aus", "karaoke": False,
                        "audio_copy": True, "reel": True}


def set_render_options(pid: str, options: dict) -> dict:
    def fn(cl):
        base = REEL_RENDER_DEFAULTS if cl["settings"].get("no_cuts") else RENDER_DEFAULTS
        cur = {**base, **cl.get("render_options", {})}
        for k, v in options.items():
            if k in ("zoom", "loudness", "denoise", "karaoke"):
                cur[k] = bool(v)
            elif k == "subtitles":
                if v not in ("aus", "srt", "einbrennen"):
                    raise UserError("Untertitel: aus, srt oder einbrennen.")
                cur[k] = v
        cl["render_options"] = cur
    return _change(pid, fn)


def set_buzzword(pid: str, start: int, end: int, on: bool) -> dict:
    def fn(cl):
        items = [b for b in cl.get("buzzwords", []) if b["end"] <= start or b["start"] >= end]
        if on:
            items.append({"start": start, "end": end})
        cl["buzzwords"] = sorted(items, key=lambda b: b["start"])
    return _change(pid, fn)


def suggest_buzzwords(pid: str) -> dict:
    from . import llm

    t = _transcript(pid)
    cl = load(pid)
    words = cuts.flat_words(t)
    flags = cuts.evaluate(t, cl)["flags"]
    numbered = " ".join(f"[{k}]{w['w']}" for k, (w, f) in enumerate(zip(words, flags)) if not f)
    minutes = max(1.0, cuts.evaluate(t, cl)["new_duration"] / 60)
    count = max(3, min(40, round(minutes * 4)))  # ca. alle 15 Sekunden eins
    found = [b for b in llm.suggest_buzzwords(numbered, t.get("language", "de"), count)
             if b["end"] <= len(words) and not any(flags[k] for k in range(b["start"], b["end"]))]
    if not found:
        raise UserError("Die lokale KI hat keine passenden Buzzwords gefunden.")

    def fn(c):
        c["buzzwords"] = sorted(found, key=lambda b: b["start"])
    return _change(pid, fn)


def auto_buzzwords(pid: str) -> None:
    """Einmal pro Projekt automatisch Buzzwords setzen: lokale KI (Ollama), sonst eingebaute Regeln."""
    from . import buzz
    from .errors import UserError as _UE

    cl = load(pid)
    if cl.get("buzz_auto"):
        return
    if cl.get("buzzwords"):  # schon von Hand gesetzt: nichts überschreiben
        with _lock:
            c = load(pid)
            c["buzz_auto"] = "manuell"
            _save(pid, c)
        return
    source = "ollama"
    try:
        suggest_buzzwords(pid)
    except _UE:
        source = "regeln"
        t = _transcript(pid)
        found = buzz.suggest(cuts.flat_words(t), cuts.evaluate(t, load(pid))["flags"])
        with _lock:
            c = load(pid)
            c["buzzwords"] = found
            _save(pid, c)
    with _lock:
        c = load(pid)
        c["buzz_auto"] = source
        _save(pid, c)


def set_overlays(pid: str, overlays: list[dict]) -> dict:
    t = _transcript(pid)
    dur = t.get("duration", 0)

    def fn(cl):
        clean = []
        for o in overlays:
            text = str(o.get("text", "")).strip()
            if not text:
                continue
            s_, e_ = max(0.0, float(o.get("start", 0))), float(o.get("end", 0))
            e_ = min(dur, max(s_ + 1.0, e_)) if dur else max(s_ + 1.0, e_)
            clean.append({"id": str(o.get("id") or f"text-{len(clean)}"), "kind": o.get("kind", "hook"),
                          "start": round(s_, 2), "end": round(e_, 2), "text": text, "on": bool(o.get("on", True))})
        cl["overlays"] = clean
    return _change(pid, fn)
