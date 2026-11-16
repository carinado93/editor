"""Language version of a finished edit: all on-screen texts (effects, hook, animations) → another language.

Carina's rule: first a translation table she approves, then the texts are swapped (the original stays saved and
can be restored). Same timing, same effects – only the words change."""
from __future__ import annotations

import copy

from . import cutstore
from .errors import UserError

LANGS = {"de": "Deutsch", "en": "English"}

SCHEMA = {"type": "object", "properties": {"rows": {"type": "array", "items": {
    "type": "object", "properties": {"key": {"type": "string"}, "text": {"type": "string"}},
    "required": ["key", "text"], "additionalProperties": False}}},
    "required": ["rows"], "additionalProperties": False}


def _rows(overlays: list[dict]) -> list[dict]:
    rows = []
    for k, o in enumerate(overlays):
        if o.get("kind") == "fx":
            if str(o.get("title") or "").strip():
                rows.append({"key": f"{k}:title", "src": o["title"]})
            for j, it in enumerate(o.get("items") or []):
                if str(it).strip():
                    rows.append({"key": f"{k}:item:{j}", "src": it})
        elif str(o.get("text") or "").strip():
            rows.append({"key": f"{k}:text", "src": o["text"]})
        for j, p in enumerate(o.get("list") or []):
            if str(p.get("text") or "").strip():
                rows.append({"key": f"{k}:list:{j}", "src": p["text"]})
    return rows


def propose(pid: str, lang: str, engine: str = "claude") -> dict:
    if lang not in LANGS:
        raise UserError("Unknown language.")
    cl = cutstore.load(pid)
    overlays = cl.get("texts_original") or cl.get("overlays") or []
    rows = _rows(overlays)
    if not rows:
        raise UserError("There are no texts in this video yet.")
    listing = "\n".join(f'{r["key"]}\t{r["src"]}' for r in rows)
    prompt = f"""Übersetze diese Bildschirm-Texte aus Carinas Video ins {LANGS[lang]}.
Carina ist Stress- & Burnout-Präventions-Coach. Ihr Ton: Ich-Form, ehrlich, locker, ein bisschen selbstironisch.
Regeln: so kurz wie das Original (Texte stehen im Bild), Trennzeichen | und *Sternchen* genau so behalten,
Uhrzeiten/Zahlen/Code-Zeilen nicht übersetzen (nur Kommentare in Code), Trend-Sätze wie "I'm just a girl" auf
Englisch lassen, keine Heilversprechen. Bei Deutsch: "du", natürliche Umgangssprache, Anglizismen wie
"Corporate Job", "Content", "Calls" sind ok.
Jede Zeile: Schlüssel TAB Text. Gib jeden Schlüssel genau einmal zurück.

{listing}"""
    if engine == "claude":
        from . import claude
        raw = claude.ask_json(prompt, SCHEMA, effort="medium")
    else:
        from . import llm
        raw = llm.ask_json(prompt + '\n\nAntworte als JSON: {"rows":[{"key":"…","text":"…"}]}',
                           "Du antwortest ausschließlich mit gültigem JSON.")
    got = {str(r.get("key")): str(r.get("text", "")).strip() for r in (raw.get("rows") or []) if isinstance(r, dict)}
    for r in rows:
        r["dst"] = got.get(r["key"]) or r["src"]
    return {"lang": lang, "rows": rows}


def apply(pid: str, lang: str, rows: list[dict]) -> dict:
    new = {str(r.get("key")): str(r.get("dst", "")).strip() for r in rows}

    def fn(cl):
        if not cl.get("texts_original"):
            cl["texts_original"] = copy.deepcopy(cl.get("overlays") or [])
        ov = copy.deepcopy(cl["texts_original"])
        for key, txt in new.items():
            if not txt:
                continue
            parts = key.split(":")
            try:
                o = ov[int(parts[0])]
            except (ValueError, IndexError):
                continue
            if parts[1] == "title":
                o["title"] = txt
            elif parts[1] == "text":
                o["text"] = txt
            elif parts[1] == "item" and len(parts) > 2 and int(parts[2]) < len(o.get("items") or []):
                o["items"][int(parts[2])] = txt
            elif parts[1] == "list" and len(parts) > 2 and int(parts[2]) < len(o.get("list") or []):
                o["list"][int(parts[2])]["text"] = txt
        cl["overlays"] = ov
        cl["text_language"] = lang
    return cutstore._change(pid, fn)


def restore(pid: str) -> dict:
    def fn(cl):
        if cl.get("texts_original"):
            cl["overlays"] = cl.pop("texts_original")
        cl.pop("text_language", None)
    return cutstore._change(pid, fn)
