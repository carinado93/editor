"""Carina sagt in eigenen Worten, was am Video anders sein soll ("mach eine Checkliste, wenn ich die 3 Zeichen
nenne", "schneide die ersten 3 Sekunden weg", "Like & Subscribe am Ende", "Zeitlupe bei 0:42") –
Claude übersetzt das in Änderungen, die die App direkt ausführt (Effekte, Zeit-Schnitte, Tempo, Render)."""
from __future__ import annotations

from . import cuts, cutstore, effects, fx, projects
from .errors import UserError

_NULLSTR = {"type": ["string", "null"]}
_NULLNUM = {"type": ["number", "null"]}
EFFECT = {"type": "object", "properties": {
    "type": {"type": "string"}, "start": {"type": "number"}, "end": {"type": "number"},
    "title": {"type": "string"}, "items": {"type": "array", "items": {"type": "string"}},
    "place": {"type": "string", "enum": ["side", "scene"]},
    "pos_x": {"type": "string", "enum": ["auto", "left", "center", "right"]},
    "pos_y": {"type": "string", "enum": ["auto", "top", "middle", "bottom"]},
    "scale": {"type": "number"}},
    "required": ["type", "start", "end", "title", "items", "place", "pos_x", "pos_y", "scale"],
    "additionalProperties": False}
UPDATE = {"type": "object", "properties": {
    "id": {"type": "string"}, "remove": {"type": "boolean"}, "start": _NULLNUM, "end": _NULLNUM,
    "title": _NULLSTR, "items": {"type": ["array", "null"], "items": {"type": "string"}},
    "pos_x": _NULLSTR, "pos_y": _NULLSTR, "scale": _NULLNUM, "type": _NULLSTR},
    "required": ["id", "remove", "start", "end", "title", "items", "pos_x", "pos_y", "scale", "type"],
    "additionalProperties": False}
RANGE = {"type": "array", "items": {"type": "number"}}
SCHEMA = {"type": "object", "properties": {
    "add_effects": {"type": "array", "items": EFFECT},
    "change_effects": {"type": "array", "items": UPDATE},
    "cut_times": {"type": "array", "items": RANGE},
    "uncut_times": {"type": "array", "items": RANGE},
    "speed": {"type": "array", "items": {"type": "object", "properties": {
        "start": {"type": "number"}, "end": {"type": "number"}, "factor": {"type": "number"}},
        "required": ["start", "end", "factor"], "additionalProperties": False}},
    "message": {"type": "string"}},
    "required": ["add_effects", "change_effects", "cut_times", "uncut_times", "speed", "message"],
    "additionalProperties": False}


def _context(pid: str) -> str:
    p = projects.load(pid)
    v = cutstore.view(pid)
    t = cutstore._transcript(pid)
    words = cuts.flat_words(t)
    flags = v["evaluation"]["flags"]
    # Sätze mit Zeiten im ORIGINAL (so arbeiten Effekte und Zeit-Schnitte)
    lines, cur, t0 = [], [], None
    for k, w in enumerate(words):
        if flags[k]:
            continue
        if t0 is None:
            t0 = w["s"]
        cur.append(w["w"])
        if w["w"].rstrip().endswith((".", "!", "?", "…")) or len(cur) > 25:
            lines.append(f"[{t0:.1f}–{w['e']:.1f}] {' '.join(cur)}")
            cur, t0 = [], None
    if cur:
        lines.append(f"[{t0:.1f}–{words[-1]['e']:.1f}] {' '.join(cur)}")
    fxs = [o for o in v["cutlist"].get("overlays", []) if o.get("kind") == "fx"]
    fx_lines = [f"- id={o['id']} {o.get('type')} {o['start']:.1f}–{o['end']:.1f} title=\"{o.get('title', '')}\" "
                f"items={o.get('items', [])} pos={o.get('pos_x', 'auto')}/{o.get('pos_y', 'auto')} on={o.get('on', True)}"
                for o in fxs]
    menu = "\n".join(f"- {k} ({fx.TYPES[k][1]}): {effects.DESCRIBE.get(k, '')}" for k in fx.TYPES
                     if k not in ("vanish", "flash"))
    clips = p.get("clip_starts") or []
    dur = (p.get("info") or {}).get("duration", 0)
    return f"""Projekt: "{p['name']}" ({'Reel' if p['mode'] == 'reel' else 'YouTube'}), Länge im Original {dur:.1f} s,
nach den Schnitten {v['evaluation']['new_duration']:.1f} s. {'Verbundene Clips beginnen bei: ' + ', '.join(f"Video {c['n']} {c['t']:.1f}s" for c in clips) if clips else ''}
Bereits selbst geschnittene Zeitbereiche: {v['cutlist'].get('time_cuts', [])}

Was gesagt wird (Zeiten in Sekunden im Original):
{chr(10).join(lines) or '(niemand spricht – stummer Clip)'}

Vorhandene Effekte:
{chr(10).join(fx_lines) or '(keine)'}

Verfügbare Effekt-Typen:
{menu}
"""


def run(pid: str, wish: str, engine: str = "claude") -> dict:
    if not wish.strip():
        raise UserError("Please write what should change.")
    prompt = f"""Du bist Carinas Video-Editorin in ihrer App. Sie sagt dir, was am Video anders sein soll; du antwortest
mit Änderungen, die die App direkt ausführt.

{_context(pid)}
Carinas Wunsch: "{wish.strip()}"

Regeln:
- add_effects: neue Effekte (type aus der Liste; start/end in Sekunden im Original; title/items = ihr Text –
  ihre Worte genau übernehmen, wenn sie welche nennt; place "side" (über dem Video) oder "scene" (ganzer Bildschirm);
  pos_x/pos_y nur, wenn sie eine Position nennt, sonst "auto"; scale 1.0 = normal).
  Zeitpunkt passend zu dem, was gesagt wird (Effekt erst, wenn sie das Wort sagt).
- change_effects: vorhandene Effekte ändern oder entfernen (id von oben, remove=true zum Löschen; Felder, die
  gleich bleiben, = null).
- cut_times: Zeitbereiche [Start, Ende] (Original-Sekunden), die herausgeschnitten werden sollen;
  uncut_times: geschnittene Bereiche zurückholen.
- speed: Zeitraffer (factor 2/4/8) oder Zeitlupe (0.5/0.25) für [start, end].
- Verschwinden/Erscheinen geht realistisch nur mit zwei Aufnahmen vom Stativ (leerer Raum + sie) beim
  "Join several videos" mit dem Übergang "Appear / disappear in smoke". In einem einzelnen Video: Effekt "poof"
  (Rauchwolke) an der Stelle anbieten und das in message erklären.
- message: 1–3 kurze Sätze auf Englisch: was du geändert hast (mit Zeiten) – oder was sie dafür filmen muss.
- Nichts erfinden, was sie nicht wollte. Leere Listen, wenn nichts zu tun ist.
Antworte NUR mit JSON nach dem Schema."""
    if engine == "claude":
        from . import claude
        raw = claude.ask_json(prompt, SCHEMA, effort="medium")
    else:
        from . import llm
        raw = llm.ask_json(prompt, "Du antwortest ausschließlich mit gültigem JSON.", timeout=600)
    return apply(pid, raw if isinstance(raw, dict) else {})


def apply(pid: str, raw: dict) -> dict:
    """Die Änderungen ausführen. Gibt {view, message, done:[…]} zurück."""
    v = cutstore.view(pid)
    dur = (projects.load(pid).get("info") or {}).get("duration", 0) or 1e9
    overlays = list(v["cutlist"].get("overlays", []))
    done: list[str] = []
    changed_fx = False
    by_id = {o.get("id"): o for o in overlays}
    for ch in raw.get("change_effects") or []:
        o = by_id.get(ch.get("id"))
        if not o:
            continue
        changed_fx = True
        if ch.get("remove"):
            overlays = [x for x in overlays if x is not o]
            done.append(f"removed {o.get('type')}")
            continue
        for k in ("start", "end", "title", "items", "pos_x", "pos_y", "scale", "type"):
            if ch.get(k) is not None:
                o[k] = ch[k]
        done.append(f"changed {o.get('type')}")
    import time
    for n, e in enumerate(raw.get("add_effects") or []):
        if e.get("type") not in fx.TYPES:
            continue
        s, en = max(0.0, float(e.get("start", 0))), min(dur, float(e.get("end", 0)))
        if en - s < 0.4:
            en = min(dur, s + 3.0)
        title = str(e.get("title") or "")
        overlays.append({"id": f"fx-a{int(time.time() * 1000) % 10_000_000}{n}", "kind": "fx", "type": e["type"],
                         "place": e.get("place", "side"), "on": True, "text": title or e["type"], "title": title,
                         "items": [str(x) for x in e.get("items") or []], "item_t": [], "start": round(s, 2),
                         "end": round(en, 2), "why": "your wish", "bg_t": None, "pose_t": [], "mode": "vanish",
                         "scale": float(e.get("scale") or 1), "pos_x": e.get("pos_x", "auto"),
                         "pos_y": e.get("pos_y", "auto")})
        changed_fx = True
        done.append(f"added {fx.TYPES[e['type']][1]} at {s:.1f}s")
    view = v
    if changed_fx:
        view = cutstore.set_overlays(pid, overlays)
    tc = [list(r) for r in v["cutlist"].get("time_cuts", [])]
    adds = [[float(r[0]), float(r[1])] for r in raw.get("cut_times") or [] if len(r) == 2 and r[1] > r[0]]
    rems = [[float(r[0]), float(r[1])] for r in raw.get("uncut_times") or [] if len(r) == 2]
    if adds or rems:
        if v["cutlist"]["settings"].get("no_cuts"):
            done.append("(cutting is off in “Enhance a reel” – nothing was cut)")
        else:
            tc = [r for r in tc if not any(abs(r[0] - a) < 0.3 and abs(r[1] - b) < 0.3 for a, b in rems)] + adds
            view = cutstore.set_time_cuts(pid, tc)
            done += [f"cut {a:.1f}–{b:.1f}s" for a, b in adds] + [f"brought back {a:.1f}–{b:.1f}s" for a, b in rems]
    sp = [r for r in raw.get("speed") or [] if r.get("end", 0) > r.get("start", 0) and r.get("factor") in (0.25, 0.5, 2, 4, 8)]
    if sp:
        cur = list(v["cutlist"].get("speed", []))
        view = cutstore.set_speed(pid, cur + [{"start": r["start"], "end": r["end"], "factor": r["factor"],
                                               "mute": r["factor"] > 2} for r in sp])
        done += [f"speed ×{r['factor']} {r['start']:.1f}–{r['end']:.1f}s" for r in sp]
    return {"view": view, "message": str(raw.get("message", "")).strip(), "done": done}
