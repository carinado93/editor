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
- Keine Bezüge, die ohne Kontext keinen Sinn ergeben ("wie gesagt", "das zweite", "dieser Punkt").
- Schluss mit klarer Aussage oder Mini-Aufgabe.
- Pro Reel: kurzer Hook-Text für die Einblendung ab Sekunde 0, der sofort sagt, worum es geht (max. 8 Wörter,
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
            warnings.append(f"Länge {dur:.1f} s (Ziel 15–20 s).".replace(".", ",", 1))
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
        raise UserError("Es wurden keine passenden Reels gefunden (Länge 15–20 s). Bitte mit einem Wunsch "
                        "nochmal versuchen, z. B. „nimm auch kürzere Aussagen“.")
    return out


def suggest(engine: str, transcript: dict, cutlist: dict, flags: list, feedback: str = "",
            previous: list[dict] | None = None) -> list[dict]:
    words = cuts.flat_words(transcript)
    sent = sentences(words, flags)
    exact_durations(words, flags, sent, transcript.get("duration", 0), cutlist["settings"].get("tempo", "normal"))
    if sum(s["dur"] for s in sent) < MIN_SEC:
        raise UserError("Das Video ist zu kurz für Reels von 15–20 Sekunden.")
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
    raise UserError("Diesen Reel-Vorschlag gibt es nicht mehr.")


def get_clip(pid: str, cid: str) -> dict:
    for c in load(pid)["clips"]:
        if c["id"] == cid:
            return c
    raise UserError("Diesen Reel-Vorschlag gibt es nicht mehr.")


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
