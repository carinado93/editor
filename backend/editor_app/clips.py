"""Reels aus langen YouTube-Videos: Claude (oder Ollama) sucht starke 15–20-Sekunden-Clips.

- Grundlage ist das bereinigte Transkript (ohne Retakes, Füllwörter, lange Pausen).
- Ein Clip besteht aus einem oder mehreren Stücken ("parts"), jedes Stück = aufeinanderfolgende Sätze.
  Stücke dürfen aus verschiedenen Stellen des Videos kommen und in beliebiger Reihenfolge stehen:
  Das erste Stück ist immer der Hook (Sekunde 0).
- Carina kann Wünsche zur Verfeinerung mitgeben; die App fragt dann neu.
"""
from __future__ import annotations

import json
import re
import time

from . import cuts, meta
from .errors import UserError

MIN_SEC, MAX_SEC = 15.0, 20.0
HARD_MIN, HARD_MAX = 10.0, 26.0


def sentences(words: list[dict], flags: list) -> list[dict]:
    """Behaltene Wörter zu Sätzen gruppieren: [{id, start, end (Wortindizes, end exkl.), text, dur}]."""
    out, cur = [], []
    for k, (w, f) in enumerate(zip(words, flags)):
        if f:
            continue
        cur.append(k)
        if re.search(r"[.!?…]$", w["w"]) or len(cur) >= 30:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    res = []
    for i, idx in enumerate(out):
        text = " ".join(words[k]["w"] for k in idx)
        dur = sum(words[k]["e"] - words[k]["s"] for k in idx) + 0.15 * (len(idx) - 1)
        res.append({"id": i + 1, "words": idx, "text": text, "dur": round(dur, 1), "t": words[idx[0]]["s"]})
    return res


def exact_durations(words: list[dict], flags: list, sent: list[dict], duration: float, tempo: str = "normal") -> None:
    """Satzlängen genau so berechnen, wie sie im Clip wirklich laufen (gleiche Pausen-Kürzung)."""
    for s_ in sent:
        segs = part_segments(words, flags, sent, [s_["id"]], duration, tempo)
        s_["dur"] = round(sum(e - a for a, e in segs), 1)


def no_overlap(segs: list[list[float]]) -> list[list[float]]:
    """Kein Moment darf doppelt laufen (z. B. wenn zwei Stücke im Original direkt aufeinander folgen)."""
    out: list[list[float]] = []
    for a, b in segs:
        for pa, pb in out:
            if a < pb and b > pa:  # überlappt einen schon benutzten Bereich
                if a >= pa:
                    a = pb
                elif b <= pb:
                    b = pa
        if b - a > 0.05:
            out.append([a, b])
    return out


def part_segments(words: list[dict], flags: list, sent: list[dict], ids: list[int], duration: float,
                  tempo: str = "normal") -> list[list[float]]:
    """Zeitbereiche eines Stücks (Sätze `ids`), mit den gleichen Schnitten wie im Rohschnitt (Pausen gekürzt)."""
    keep_idx = {k for s in sent if s["id"] in ids for k in s["words"]}
    part_flags = [None if (k in keep_idx and not flags[k]) else "aus" for k in range(len(words))]
    if not keep_idx:
        return []
    tl = cuts.timeline(words, part_flags, duration, tempo)
    return tl["keep"]


def build_prompt(sent: list[dict], language: str, feedback: str = "", previous: list[dict] | None = None) -> str:
    lang = "Deutsch" if language == "de" else "Englisch"
    listing = "\n".join(f"[S{s['id']}] ({s['dur']:.1f}s, bei {int(s['t'] // 60)}:{int(s['t'] % 60):02d}) {s['text']}"
                        for s in sent)
    prev = ""
    if previous:
        prev = "\nBisherige Vorschläge (zur Orientierung, Carina möchte Änderungen):\n" + "\n".join(
            f"- {c.get('title', '')}: Hook „{c.get('hook_text', '')}“, Stücke {c.get('parts')}" for c in previous)
    return f"""Du bist Short-Form-Editorin für Carina Dorca (Stress- und Burnout-Prävention, Instagram/YouTube Shorts).
Aus ihrem langen YouTube-Video (Sprache: {lang}) sollst du so viele STARKE Reels finden, wie es wirklich gibt
(lieber 3 sehr gute als 8 mittelmäßige, höchstens 8).

Regeln für jedes Reel:
- Länge {MIN_SEC:.0f}–{MAX_SEC:.0f} Sekunden (Summe der Satzlängen in Klammern).
- Sekunde 0 = Hook: Das erste Stück ist der stärkste, polarisierendste, konkreteste Satz – er darf von irgendwo
  aus dem Video kommen.
- Danach Stücke, die zusammen eine runde, verständliche Aussage ergeben. Stücke dürfen aus verschiedenen Stellen
  kommen und neu angeordnet werden (z. B. Hook aus Minute 3, dann Erklärung aus Minute 1).
- Jedes Stück besteht aus aufeinanderfolgenden ganzen Sätzen (Liste von Satz-Nummern, z. B. [12, 13]).
- DAS WAS ZUERST: Wer das lange Video nie gesehen hat, muss in den ersten 3 Sekunden verstehen, WORUM es geht
  (Thema + Spannung). Das erste Stück und der Hook-Text nennen das Thema ausdrücklich (z. B. Burnout, Stress,
  Angst, Coaching, Grenzen) – kein Satz, der erst mit Vorwissen Sinn ergibt ("Kein Coach bei Burnout?" ist zu
  knapp; besser: "Darf ein *Coach* bei Burnout helfen?").
- Das Reel muss ganz für sich allein stehen: Thema → Problem/Frage → Antwort/Erkenntnis. Fehlt der Zusammenhang,
  nimm ein Stück von einer anderen Stelle dazu, das ihn liefert, oder lass das Reel weg.
- Keine Bezüge, die ohne Kontext keinen Sinn ergeben ("wie gesagt", "das zweite", "dieser Punkt", "er", "das da").
- Schluss mit klarer Aussage oder Mini-Aufgabe.
- Pro Reel: kurzer Hook-Text für die Einblendung ab Sekunde 0, der sofort sagt, worum es geht – mit dem Thema
  im Text (max. 9 Wörter,
  *ein Wort in Sternchen* wird lila), dazu 2–3 weitere kurze Einblendungen ("texts", je max. 8 Wörter), die die
  Kernaussage verstärken und nacheinander gezeigt werden,
  Caption in Carinas Stimme (Hook + 🤍, 2 kurze Absätze, "📌 Save this…", "Follow …", letzte Zeile
  "Educational and my own experience, not a diagnosis or therapy." – auf Deutsch sinngemäß),
  GENAU 5 Hashtags (bevorzugt aus: {", ".join(meta.hashtag_bank(language)[:25])}), YouTube-Shorts-Titel.

{meta.GUARDRAILS}
{prev}
{f'WÜNSCHE VON CARINA (unbedingt umsetzen): {feedback.strip()}' if feedback.strip() else ''}

Sätze des Videos:
{listing}

{meta.lang_rule(language)}
Antworte NUR mit JSON:
{{"clips": [{{"title": "kurzer Arbeitstitel", "hook_text": "…", "texts": ["…", "…"], "parts": [[12], [3, 4, 5]], "why": "warum stark",
  "caption": "…", "hashtags": ["#a", "#b", "#c", "#d", "#e"], "shorts_title": "…"}}]}}
"""


CLIP_SCHEMA = {
    "type": "object",
    "properties": {"clips": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "title": {"type": "string"}, "hook_text": {"type": "string"},
            "texts": {"type": "array", "items": {"type": "string"}},
            "parts": {"type": "array", "items": {"type": "array", "items": {"type": "integer"}}},
            "why": {"type": "string"}, "caption": {"type": "string"},
            "hashtags": {"type": "array", "items": {"type": "string"}}, "shorts_title": {"type": "string"},
        },
        "required": ["title", "hook_text", "texts", "parts", "why", "caption", "hashtags", "shorts_title"],
        "additionalProperties": False,
    }}},
    "required": ["clips"],
    "additionalProperties": False,
}


def validate(raw: dict, words: list[dict], flags: list, sent: list[dict], duration: float, language: str,
             tempo: str = "normal") -> list[dict]:
    """KI-Vorschläge prüfen: gültige Sätze, Länge, genau 5 Hashtags; Zeitbereiche berechnen."""
    known = {s["id"] for s in sent}
    out = []
    for n, c in enumerate(raw.get("clips", []) if isinstance(raw, dict) else []):
        parts = []
        for p in c.get("parts", []):
            ids = sorted({int(x) for x in p if str(x).lstrip("S").isdigit() and int(str(x).lstrip("S")) in known}) \
                if isinstance(p, list) else []
            if ids:
                parts.append(ids)
        if not parts:
            continue
        segs = []
        for ids in parts:
            segs.extend(part_segments(words, flags, sent, ids, duration, tempo))
        segs = no_overlap(segs)
        dur = round(sum(e - s for s, e in segs), 2)
        if not (HARD_MIN <= dur <= HARD_MAX):
            continue
        warnings: list[str] = []
        if not (MIN_SEC - 1 <= dur <= MAX_SEC + 1):
            warnings.append(f"Length {dur:.1f} s (target 15–20 s).")
        hashtags = meta.fix_hashtags(list(c.get("hashtags", [])), language, [])  # Auffüllen ist normal, keine Warnung
        out.append({
            "id": f"clip-{int(time.time() * 1000) % 10_000_000}-{n}",
            "title": str(c.get("title", f"Reel {n + 1}")).strip()[:80],
            "hook_text": str(c.get("hook_text", "")).strip(),
            "texts": [str(x).strip() for x in c.get("texts", []) if str(x).strip()][:3],
            "parts": parts,
            "segments": [[round(s, 3), round(e, 3)] for s, e in segs],
            "duration": dur,
            "why": str(c.get("why", "")).strip(),
            "caption": str(c.get("caption", "")).strip(),
            "hashtags": hashtags,
            "shorts_title": str(c.get("shorts_title", "")).strip(),
            "text": " … ".join(" ".join(s["text"] for s in sent if s["id"] in ids) for ids in parts),
            "warnings": warnings,
            "status": "vorschlag",
        })
    if not out:
        raise UserError("No suitable reels were found (length 15–20 s). Please try again with a wish, "
                        "e.g. \"also take shorter statements\".")
    return out


def suggest(engine: str, transcript: dict, cutlist: dict, flags: list, feedback: str = "",
            previous: list[dict] | None = None) -> list[dict]:
    words = cuts.flat_words(transcript)
    sent = sentences(words, flags)
    exact_durations(words, flags, sent, transcript.get("duration", 0), cutlist["settings"].get("tempo", "normal"))
    if sum(s["dur"] for s in sent) < MIN_SEC:
        raise UserError("The video is too short for reels of 15–20 seconds.")
    lang = transcript.get("language", "en")
    prompt = build_prompt(sent, lang, feedback, previous)
    if engine == "claude":
        from . import claude
        raw = claude.ask_json(prompt, CLIP_SCHEMA, effort="high")
    else:
        from . import llm
        raw = llm.ask_json(prompt, "Du antwortest ausschließlich mit gültigem JSON.", timeout=900)
    return validate(raw, words, flags, sent, transcript.get("duration", 0), lang,
                    cutlist["settings"].get("tempo", "normal"))


def context(transcript: dict, cutlist: dict, flags: list) -> tuple[list[dict], list[dict], float, str]:
    """Wörter, Sätze (mit echten Längen), Videolänge und Tempo – für das Bearbeiten eines einzelnen Reels."""
    words = cuts.flat_words(transcript)
    sent = sentences(words, flags)
    tempo = cutlist["settings"].get("tempo", "normal")
    exact_durations(words, flags, sent, transcript.get("duration", 0), tempo)
    return words, sent, transcript.get("duration", 0), tempo


def apply_parts(clip: dict, parts: list[list[int]], words: list[dict], flags: list, sent: list[dict],
                duration: float, tempo: str) -> dict:
    """Andere Sätze für ein Reel: Zeitbereiche, Länge und Text neu berechnen."""
    known = {s["id"] for s in sent}
    parts = [sorted({int(x) for x in p if int(x) in known}) for p in parts]
    parts = [p for p in parts if p]
    if not parts:
        raise UserError("A reel needs at least one sentence.")
    segs: list = []
    for ids in parts:
        segs.extend(part_segments(words, flags, sent, ids, duration, tempo))
    segs = no_overlap(segs)
    dur = round(sum(e - s for s, e in segs), 2)
    warnings = [] if MIN_SEC - 1 <= dur <= MAX_SEC + 1 else [f"Length {dur:.1f} s (target 15–20 s)."]
    return {**clip, "parts": parts, "segments": [[round(s, 3), round(e, 3)] for s, e in segs], "duration": dur,
            "text": " … ".join(" ".join(s["text"] for s in sent if s["id"] in ids) for ids in parts),
            "warnings": warnings}


def refine_one(engine: str, transcript: dict, cutlist: dict, flags: list, clip: dict, wish: str) -> dict:
    """Ein einzelnes Reel nach Carinas Wunsch überarbeiten (Hook, Texte, Stücke, Caption). Effekte bleiben."""
    words, sent, duration, tempo = context(transcript, cutlist, flags)
    lang = transcript.get("language", "en")
    prompt = build_prompt(sent, lang, "Überarbeite NUR dieses EINE Reel (genau 1 Reel in der Antwort) nach "
                          f"Carinas Wunsch: {wish.strip()}", [clip])
    if engine == "claude":
        from . import claude
        raw = claude.ask_json(prompt, CLIP_SCHEMA, effort="medium")
    else:
        from . import llm
        raw = llm.ask_json(prompt, "Du antwortest ausschließlich mit gültigem JSON.", timeout=900)
    new = validate(raw, words, flags, sent, duration, lang, tempo)[0]
    keep = {k: clip[k] for k in ("id", "fx", "subs") if k in clip}
    return {**new, **keep, "status": "vorschlag", "file": None}


def parts_text(parts: list[list[int]], sent: list[dict]) -> str:
    return json.dumps(parts)


# ---------- Speicherung pro Projekt (clips.json) ----------

import threading as _threading

_lock = _threading.RLock()


def _file(pid: str):
    from . import projects
    return projects.path(pid, "clips.json")


def load(pid: str) -> dict:
    f = _file(pid)
    with _lock:
        if not f.exists():
            return {"clips": [], "feedback": []}
        return json.loads(f.read_text(encoding="utf-8"))


def save(pid: str, data: dict) -> dict:
    with _lock:
        f = _file(pid)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(f)
    return data


def update_clip(pid: str, cid: str, **fields) -> dict:
    with _lock:
        data = load(pid)
        for c in data["clips"]:
            if c["id"] == cid:
                c.update(fields)
                save(pid, data)
                return c
    raise UserError("This reel suggestion does not exist any more.")


def get_clip(pid: str, cid: str) -> dict:
    for c in load(pid)["clips"]:
        if c["id"] == cid:
            return c
    raise UserError("This reel suggestion does not exist any more.")


def overlay_plan(hook_text: str, texts: list[str], total: float) -> list[dict]:
    """Hook ab Sekunde 0 (Pop), danach die weiteren Texte gleichmäßig verteilt mit wechselnden Animationen."""
    plan = []
    hook_end = min(total, 4.6)
    if hook_text.strip():
        plan.append({"s": 0.0, "e": hook_end, "text": hook_text, "anim": "pop"})
    rest = [t for t in texts if t.strip()]
    if rest and total - hook_end > 2.5:
        slot = (total - hook_end) / len(rest)
        for i, t in enumerate(rest):
            plan.append({"s": round(hook_end + i * slot + 0.15, 2), "e": round(hook_end + (i + 1) * slot - 0.1, 2),
                         "text": t, "anim": ["karte", "wort", "slide"][i % 3]})
    return plan


# ---------- Reel aus einer Stelle, die Carina selbst markiert ----------

TEXT_SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string"}, "hook_text": {"type": "string"},
                   "texts": {"type": "array", "items": {"type": "string"}}, "why": {"type": "string"},
                   "caption": {"type": "string"}, "hashtags": {"type": "array", "items": {"type": "string"}},
                   "shorts_title": {"type": "string"}},
    "required": ["title", "hook_text", "texts", "why", "caption", "hashtags", "shorts_title"],
    "additionalProperties": False,
}


def from_selection(transcript: dict, cutlist: dict, flags: list, i0: int, i1: int) -> dict:
    """Reel genau aus der markierten Stelle (Wort i0 bis i1), auf ganze Sätze gerundet – nie mitten im Satz."""
    words, sent, duration, tempo = context(transcript, cutlist, flags)
    ids = [s["id"] for s in sent if s["words"] and s["words"][-1] >= i0 and s["words"][0] <= i1]
    if not ids:
        raise UserError("The selected words are all cut. Please select words that stay in the video.")
    base = {"id": f"clip-{int(time.time() * 1000) % 10_000_000}-m", "title": "My reel", "hook_text": "",
            "texts": [], "why": "Your own choice", "caption": "", "hashtags": meta.fix_hashtags([], transcript.get(
                "language", "en"), []), "shorts_title": "", "status": "vorschlag", "own": True}
    c = apply_parts(base, [ids], words, flags, sent, duration, tempo)
    first = re.sub(r"[.!?…,;:]+$", "", " ".join(c["text"].split()[:7]))
    c["hook_text"] = first[:1].upper() + first[1:]  # Platzhalter, bis Claude (oder Carina) den Hook schreibt
    return c


def write_texts(engine: str, transcript: dict, clip: dict) -> dict:
    """Hook, Einblendungen, Caption, 5 Hashtags für ein Reel, dessen Inhalt Carina selbst gewählt hat
    (das Gesagte bleibt genau so)."""
    lang = transcript.get("language", "en")
    prompt = f"""Du bist Short-Form-Editorin für Carina Dorca (Stress- und Burnout-Prävention, Instagram/YouTube Shorts).
Carina hat diese Stelle aus ihrem Video selbst als Reel ausgewählt ({clip.get('duration', 0):.0f} Sekunden). Das Gesagte
bleibt GENAU so – du schreibst nur die Texte dazu:

„{clip.get('text', '')}“

- title: kurzer Arbeitstitel.
- hook_text: Einblendung ab Sekunde 0, max. 9 Wörter, nennt sofort das Thema (Burnout, Stress, Angst …),
  *ein Wort in Sternchen* wird lila. Wer das lange Video nie gesehen hat, versteht sofort, worum es geht.
- texts: 2–3 kurze Einblendungen (je max. 8 Wörter), die die Kernaussage verstärken.
- why: ein Satz, warum die Stelle als Reel funktioniert.
- caption: in Carinas Stimme (Hook + 🤍, 2 kurze Absätze, "📌 Save this…", "Follow …", letzte Zeile
  "Educational and my own experience, not a diagnosis or therapy." – sinngemäß in der Sprache des Videos).
- hashtags: GENAU 5 (bevorzugt aus: {", ".join(meta.hashtag_bank(lang)[:25])}).
- shorts_title: YouTube-Shorts-Titel.

{meta.GUARDRAILS}

{meta.lang_rule(lang)}
Antworte NUR mit JSON nach dem Schema."""
    if engine == "claude":
        from . import claude
        raw = claude.ask_json(prompt, TEXT_SCHEMA, effort="low")
    else:
        from . import llm
        raw = llm.ask_json(prompt, "Du antwortest ausschließlich mit gültigem JSON.", timeout=600)
    if not isinstance(raw, dict):
        return clip
    return {**clip,
            "title": str(raw.get("title") or clip["title"]).strip()[:80],
            "hook_text": str(raw.get("hook_text", "")).strip(),
            "texts": [str(x).strip() for x in raw.get("texts", []) if str(x).strip()][:3],
            "why": str(raw.get("why") or clip.get("why", "")).strip(),
            "caption": str(raw.get("caption", "")).strip(),
            "hashtags": meta.fix_hashtags(list(raw.get("hashtags", [])), lang, []),
            "shorts_title": str(raw.get("shorts_title", "")).strip()}
