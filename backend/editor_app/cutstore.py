"""Speichert die Schnittliste eines Projekts (schnitte.json) mit Rückgängig-Funktion.

Nicht-destruktiv: Das Video wird nie verändert, gespeichert wird nur, welche Wörter/Pausen wegfallen.
"""
from __future__ import annotations

import copy
import json
import threading

from . import cuts, projects
from .errors import UserError

_lock = threading.RLock()
MAX_UNDO = 50


def _transcript(pid: str) -> dict:
    f = projects.path(pid, "transkript.json")
    if not f.exists():
        raise UserError("Das Transkript ist noch nicht fertig.")
    return json.loads(f.read_text(encoding="utf-8"))


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


def create(pid: str, transcript: dict | None = None) -> dict:
    t = transcript or _transcript(pid)
    cl = cuts.build(t, cuts.default_settings(t.get("language", "de")))
    cl["overrides"] = {}
    cl["history"] = []
    _save(pid, cl)
    return cl


def load(pid: str) -> dict:
    f = _file(pid)
    if not f.exists():
        return create(pid)
    return json.loads(f.read_text(encoding="utf-8"))


def view(pid: str, cutlist: dict | None = None) -> dict:
    """Schnittliste + Auswertung (welche Wörter fallen weg, welche Zeitbereiche bleiben, neue Länge)."""
    t = _transcript(pid)
    cl = cutlist or load(pid)
    ev = cuts.evaluate(t, cl)
    public = {k: v for k, v in cl.items() if k != "history"}
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
        rebuilt = cuts.build(t, new, cl["manual"], cl.get("pause_keep"))
        cl["settings"] = new
        cl["detections"] = rebuilt["detections"]
        _apply_overrides(cl)
    return _change(pid, fn)


def reset(pid: str) -> dict:
    t = _transcript(pid)

    def fn(cl):
        fresh = cuts.build(t, cl["settings"])
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
