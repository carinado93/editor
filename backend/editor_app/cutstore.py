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
        raise UserError("The transcript is not ready yet.")
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


def _anim_to_fx(o: dict) -> dict | None:
    """Alte YouTube-Animation (kind "yt") → Effekt (alles liegt jetzt in "Effects")."""
    style = o.get("style", "label")
    base = {"id": "fx-" + str(o.get("id", "")).replace("yt-", ""), "kind": "fx", "on": o.get("on", True),
            "start": o["start"], "end": o["end"], "place": "side", "items": [], "item_t": [], "why": ""}
    if style == "number":
        title = f"{o.get('text', '')}|{o.get('number', '')}"
        return {**base, "type": "number", "title": title, "text": title}
    if style in ("sticker", "check"):
        lst = o.get("list") or [{"text": o.get("text", ""), "t": o["start"]}]
        return {**base, "type": "stickers" if style == "sticker" else "checklist", "title": "",
                "text": o.get("text") or style, "items": [p["text"] for p in lst], "item_t": [p["t"] for p in lst]}
    typ = {"label": "label", "quote": "quotepill", "name": "name"}.get(style, "label")
    return {**base, "type": typ, "title": o.get("text", ""), "text": o.get("text") or typ}


def _buzz_to_fx(b: dict, words: list[dict]) -> dict | None:
    if not (0 <= b["start"] < len(words)):
        return None
    ws = words[b["start"]:b["end"]]
    text = b.get("text") or " ".join(re.sub(r"[.,!?;:…]+$", "", w["w"]) for w in ws)
    s_ = ws[0]["s"]
    return {"id": f"fx-bz-{b['start']}", "kind": "fx", "type": "buzzword", "place": "side", "on": True,
            "title": text, "text": text, "items": [], "item_t": [], "why": "",
            "start": round(s_, 2), "end": round(max(s_ + 1.8, ws[-1]["e"] + 0.8), 2)}


def _migrate_to_effects(pid: str, cl: dict) -> dict:
    """Animationen und Buzzwords sind jetzt Effekte (damit nichts doppelt im Video steht). Einmalig umwandeln."""
    yts = [o for o in cl.get("overlays", []) if o.get("kind") == "yt"]
    bzs = cl.get("buzzwords") or []
    if not yts and not bzs:
        return cl
    words = cuts.flat_words(_transcript(pid))
    new = [x for x in ([_anim_to_fx(o) for o in yts] + [_buzz_to_fx(b, words) for b in bzs]) if x]
    with _lock:
        c = load(pid)
        c["overlays"] = [o for o in c.get("overlays", []) if o.get("kind") != "yt"] + new
        c["overlays"].sort(key=lambda o: o.get("start", 0))
        c["buzzwords"] = []
        _save(pid, c)
        return c


def view(pid: str, cutlist: dict | None = None) -> dict:
    """Schnittliste + Auswertung (welche Wörter fallen weg, welche Zeitbereiche bleiben, neue Länge)."""
    t = _transcript(pid)
    cl = cutlist or load(pid)
    if cutlist is None:
        cl = _migrate_to_effects(pid, cl)
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
            raise UserError("This cut does not exist any more. Please reload the page.")
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
            raise UserError("Pace must be relaxed, normal or tight.")
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
            raise UserError("There is nothing to undo.")
        prev = hist.pop()
        prev["history"] = hist
        _save(pid, prev)
        return view(pid, prev)


def remap_words(pid: str, old_to_new: list[int]) -> None:
    """Nach dem Nachhören sind Wörter dazugekommen: Carinas Änderungen (Wort-Nummern) auf die neuen Nummern umrechnen."""
    if not _file(pid).exists():
        return

    def m(i: int) -> int:
        return old_to_new[i] if 0 <= i < len(old_to_new) else i

    with _lock:
        cl = load(pid)
        man = cl.get("manual", {})
        cl["manual"] = {"cut": [m(i) for i in man.get("cut", [])], "keep": [m(i) for i in man.get("keep", [])]}
        cl["pause_keep"] = [m(i) for i in cl.get("pause_keep", [])]
        cl["buzzwords"] = [dict(b, start=m(b["start"]), end=m(b["end"] - 1) + 1) for b in cl.get("buzzwords", [])]
        cl["overrides"] = {}
        cl["history"] = []
        _save(pid, cl)


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
                    raise UserError("Subtitles: off, srt or burn in.")
                cur[k] = v
        cl["render_options"] = cur
    return _change(pid, fn)


def set_buzzword(pid: str, start: int, end: int, on: bool) -> dict:
    """★ Buzzword im Transkript: legt einen Buzzword-Effekt an (oder entfernt ihn)."""
    words = cuts.flat_words(_transcript(pid))

    def fn(cl):
        s_, e_ = words[start]["s"], words[end - 1]["e"]
        keep = [o for o in cl.get("overlays", []) if not (o.get("kind") == "fx" and o.get("type") == "buzzword"
                                                       and o["start"] < e_ + 0.5 and o["end"] > s_)]
        if on:
            item = _buzz_to_fx({"start": start, "end": end}, words)
            if item:
                keep.append(item)
        cl["overlays"] = sorted(keep, key=lambda o: o.get("start", 0))
        cl["buzzwords"] = []
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
        raise UserError("The local AI did not find suitable buzzwords.")

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


def set_animations(pid: str, items: list[dict]) -> dict:
    """YouTube-Animationen ersetzen (andere Texte bleiben)."""
    others = [o for o in load(pid).get("overlays", []) if o.get("kind") != "yt"]
    return set_overlays(pid, others + items)


def suggest_animations(pid: str, engine: str) -> dict:
    from . import animations
    t = _transcript(pid)
    flags = cuts.evaluate(t, load(pid))["flags"]
    items = animations.suggest_claude(t, flags) if engine == "claude" else animations.suggest_ollama(t, flags)
    fx_items = [x for x in (_anim_to_fx(o) for o in items) if x]  # alles als Effekte
    view_ = set_effects(pid, [o for o in load(pid).get("overlays", []) if o.get("kind") == "fx"] + fx_items)
    with _lock:
        c = load(pid)
        c["anim_auto"] = engine
        _save(pid, c)
    return view_


def auto_animations(pid: str) -> None:
    """Einmal pro YouTube-Projekt automatisch Animationen setzen: mit Claude, wenn der Schlüssel da ist,
    sonst kostenlos mit Ollama. Klappt beides nicht, bleibt es leer (Knopf im YouTube-Paket)."""
    from . import claude
    cl = load(pid)
    if cl.get("anim_auto") or cl["settings"].get("no_cuts"):
        return
    if cl.get("buzz_auto") == "ollama":
        # Die alten automatischen Buzzwords der lokalen KI waren unbrauchbar (nur am Videoende) → weg damit
        with _lock:
            c = load(pid)
            c["buzzwords"] = []
            c["buzz_auto"] = "ersetzt"
            _save(pid, c)
    for engine in (["claude"] if claude.available() else []) + ["ollama"]:
        try:
            suggest_animations(pid, engine)
            return
        except UserError:
            continue
    with _lock:
        c = load(pid)
        c["anim_auto"] = "fehlgeschlagen"
        _save(pid, c)


def set_effects(pid: str, items: list[dict]) -> dict:
    """Große Effekte ersetzen (andere Texte und Animationen bleiben)."""
    others = [o for o in load(pid).get("overlays", []) if o.get("kind") != "fx"]
    return set_overlays(pid, others + items)


def suggest_effects(pid: str, engine: str, allowed: list[str], wish: str = "") -> dict:
    from . import effects
    t = _transcript(pid)
    cl = load(pid)
    flags = cuts.evaluate(t, cl)["flags"]
    if not cuts.flat_words(t):  # Clip ohne Sprechen: Claude schaut sich Standbilder an
        from . import media
        p = projects.load(pid)
        proxy = projects.path(pid, "vorschau.mp4")
        src = proxy if proxy.exists() else projects.path(pid, p["original_file"])
        dur = (p.get("info") or {}).get("duration", 10)
        stills = media.stills_base64(src, dur, n=6)
        idea = ""
        rt = projects.path(pid, "reel_texte.json")
        if rt.exists():
            try:
                idea = json.loads(rt.read_text(encoding="utf-8")).get("idea", "")
            except ValueError:
                pass
        items = effects.suggest_silent(stills, dur, t.get("language", "de"), allowed, engine, wish, idea)
    else:
        items = effects.suggest(t, flags, allowed, engine, bool(cl["settings"].get("no_cuts")), wish)
    view_ = set_effects(pid, items)
    with _lock:
        c = load(pid)
        c["fx_allowed"] = list(allowed)
        _save(pid, c)
    view_["cutlist"]["fx_allowed"] = list(allowed)
    return view_


def set_speed(pid: str, ranges: list[dict]) -> dict:
    """Zeitraffer/Zeitlupe: [{start, end, factor, mute}] in Original-Zeit."""
    from .fxrender import SPEEDS

    def fn(cl):
        clean = []
        for r in ranges:
            f = float(r.get("factor", 1))
            s_, e_ = float(r.get("start", 0)), float(r.get("end", 0))
            if f in SPEEDS and e_ - s_ >= 0.3:
                clean.append({"start": round(s_, 2), "end": round(e_, 2), "factor": f,
                              "mute": bool(r.get("mute", f > 2))})
        clean.sort(key=lambda r: r["start"])
        cl["speed"] = clean
    return _change(pid, fn)


def set_overlays(pid: str, overlays: list[dict]) -> dict:
    t = _transcript(pid)
    dur = t.get("duration", 0)

    def fn(cl):
        clean = []
        for o in overlays:
            text = str(o.get("text", "")).strip() or (o.get("type", "") if o.get("kind") == "fx" else "")
            if not text:
                continue
            s_, e_ = max(0.0, float(o.get("start", 0))), float(o.get("end", 0))
            e_ = min(dur, max(s_ + 1.0, e_)) if dur else max(s_ + 1.0, e_)
            anim = o.get("anim") if o.get("anim") in ("pop", "karte", "wort", "slide") else "karte"
            item = {"id": str(o.get("id") or f"text-{len(clean)}"), "kind": o.get("kind", "hook"),
                    "start": round(s_, 2), "end": round(e_, 2), "text": text, "on": bool(o.get("on", True)),
                    "anim": anim}
            if item["kind"] == "yt":  # YouTube-Animation: Stil, Zahl und Listenpunkte behalten
                from . import animations
                item["style"] = o.get("style") if o.get("style") in animations.STYLES else "label"
                item["number"] = str(o.get("number") or "")[:12]
                item["list"] = [{"text": str(p.get("text", "")).strip()[:48], "t": round(float(p.get("t", s_)), 2)}
                                for p in o.get("list") or [] if str(p.get("text", "")).strip()]
            if item["kind"] == "fx":  # große Effekte: Typ, Platz, Texte, Punkt-Zeiten behalten
                from . import fx
                item["type"] = o.get("type") if o.get("type") in fx.TYPES else "headline"
                places = fx.TYPES[item["type"]][2]
                item["place"] = o.get("place") if o.get("place") in places else places[0]
                item["title"] = str(o.get("title") or "").strip()[:80]
                item["items"] = [str(x).strip()[:60] for x in o.get("items") or [] if str(x).strip()][:6]
                item["item_t"] = [round(float(x), 2) for x in o.get("item_t") or []][:6]
                item["why"] = str(o.get("why") or "")[:160]
                item["bg_t"] = round(float(o["bg_t"]), 2) if o.get("bg_t") is not None else None
                item["pose_t"] = [round(float(x), 2) for x in o.get("pose_t") or []][:8]
                item["mode"] = "appear" if o.get("mode") == "appear" else "vanish"
                try:
                    item["scale"] = round(max(0.4, min(2.5, float(o.get("scale") or 1))), 2)
                except (TypeError, ValueError):
                    item["scale"] = 1.0
            clean.append(item)
        cl["overlays"] = clean
    return _change(pid, fn)
