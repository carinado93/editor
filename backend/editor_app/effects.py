"""Effekt-Vorschläge: Claude (oder Ollama) sucht passende Momente für die Effekte, die Carina erlaubt hat.

Gespeichert wird jeder Effekt in der Schnittliste unter "overlays" (kind "fx"), Zeiten in Original-Zeit.
"""
from __future__ import annotations

import time

from . import animations, cuts, fx
from .errors import UserError

DESCRIBE = {
    "steps": "Schritt-Kästen untereinander mit Linie (2–4 Schritte, je max. 4 Wörter) – wenn sie einen Ablauf erklärt",
    "cards": "2–4 weiße Karten um die Mitte (Text 'Titel|Unterzeile', je 1–2 Wörter) – wenn sie Möglichkeiten/Bereiche nennt",
    "tags": "3–5 kleine Etiketten fliegen herein (je 1–2 Wörter) – Symptome, Stichworte, Beispiele",
    "scores": "2–3 Bewertungs-Karten 'Text|Zahl 1–10' – Vergleiche, Mythen vs. Fakten, wie sehr etwas hilft",
    "headline": "Treppen-Überschrift in 2–5 kurzen Zeilen (Zeilen mit | trennen, ein *Wort* Gold-kursiv) – Hook, große Frage, Wendepunkt",
    "checklist": "Checkliste mit Haken (2–5 Punkte, je max. 4 Wörter) – Tipps, Dos/Don'ts, Grenzen",
    "endcard": "Schluss-Karte: title = kurze Frage/Zeile, items = [Aufforderung wie 'Kommentiere RUHE'] – nur ganz am Ende",
    "bigwords": "große Wort-für-Wort-Untertitel für eine starke Passage (items = 1–3 Schlüsselwörter, die lila werden)",
    "pill": "kleine Pille oben (title max. 4 Wörter, z. B. '+ Atemübung') – kurzer Hinweis",
    "behind": "ein großes Wort HINTER Carina (title = 1 Wort, z. B. BURNOUT) – Kernbegriff, sehr wirkungsvoll",
    "glow": "leuchtender Umriss um Carina (title optional als Pille) – emotionaler Moment",
    "background": "neuer Lavendel-Hintergrund hinter Carina (title optional als Überschrift) – Themenwechsel",
    "card": "Video als Karte auf Lavendel mit Treppen-Überschrift darüber (title, Zeilen mit |) – Einstieg/Kapitel",
    "poof": "Puff-Wolke (Verschwinden/Auftauchen) – nur genau an einem Schnitt, an dem sie den Ort wechselt",
}

SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": list(fx.TYPES)},
            "place": {"type": "string", "enum": ["scene", "side"]},
            "word": {"type": "integer"}, "end_word": {"type": "integer"},
            "title": {"type": "string"},
            "items": {"type": "array", "items": {"type": "string"}},
            "item_words": {"type": "array", "items": {"type": "integer"}},
            "why": {"type": "string"},
        },
        "required": ["type", "place", "word", "end_word", "title", "items", "item_words", "why"],
        "additionalProperties": False,
    }}},
    "required": ["items"],
    "additionalProperties": False,
}


def build_prompt(words: list[dict], flags: list, language: str, allowed: list[str], reel: bool, wish: str = "") -> str:
    lang = "Deutsch" if language == "de" else "Englisch"
    menu = "\n".join(f"- {k} ({fx.TYPES[k][1]}): {DESCRIBE[k]}" for k in allowed)
    how_often = ("Reel: 2–5 Effekte insgesamt, der erste in den ersten 2 Sekunden (Hook)." if reel else
                 "YouTube: ungefähr alle 30–60 Sekunden ein Effekt, dort wo er den Inhalt wirklich zeigt.")
    return f"""Du bist Video-Editorin für Carina Dorca (Stress- und Burnout-Prävention). Plane große Effekte im Stil
moderner Creator-Reels (Kästen, Karten, Checklisten, Text hinter der Person) für ihr Video. Sprache der Texte: {lang}.

Erlaubte Effekte (nur diese!):
{menu}

Regeln:
- {how_often}
- "word" = Nummer des Worts, bei dem der Effekt beginnt; "end_word" = Nummer des Worts, mit dem er endet
  (Szenen 2,5–6 s, Effekte neben ihr 2–8 s, Puff ca. 1 s).
- Bei Listen (steps, cards, tags, scores, checklist): "item_words" = für jeden Punkt die Nummer des Worts, mit dem sie
  ihn fertig gesagt hat (der Punkt erscheint erst dann). Sonst leer.
- "place": "scene" = ganzer Bildschirm auf Lavendel (ihre Stimme läuft weiter) – für Erklärungen, Listen, Hook;
  "side" = neben ihr über dem Video – wenn ihr Gesicht/ihre Emotion wichtig ist. Wähle passend zum Moment.
- Texte kurz, in ihren Worten, keine Heilversprechen, keine Diagnosen.
- Nie zwei Effekte gleichzeitig.
{f'- WUNSCH VON CARINA: {wish.strip()}' if wish.strip() else ''}

Transkript (Zeit, [Nummer] vor jedem Wort):
{animations.numbered_sentences(words, flags)}

Antworte NUR mit JSON nach dem Schema."""


def parse(data: dict, words: list[dict], flags: list, allowed: list[str]) -> list[dict]:
    n = len(words)

    def ok(k) -> bool:
        return isinstance(k, int) and 0 <= k < n and not (flags and flags[k])

    stamp = int(time.time() * 1000) % 10_000_000
    out = []
    for i, it in enumerate(data.get("items") or []):
        typ = it.get("type")
        if typ not in allowed or typ not in fx.TYPES or not ok(it.get("word")):
            continue
        start = words[it["word"]]["s"]
        end_k = it.get("end_word")
        end = words[end_k]["e"] if ok(end_k) and end_k >= it["word"] else start + 4
        places = fx.TYPES[typ][2]
        place = it.get("place") if it.get("place") in places else places[0]
        dur_min, dur_max = (0.8, 1.4) if typ == "poof" else (2.5, 8.0)
        end = min(max(end, start + dur_min), start + dur_max)
        if typ == "poof":
            start = max(0.0, start - 0.25)  # die Wolke ist am dichtesten genau am Schnitt
        item_t = [round(words[k]["e"] - 0.1, 2) for k in it.get("item_words") or [] if ok(k)]
        items = [str(x).strip()[:60] for x in it.get("items") or [] if str(x).strip()][:6]
        if item_t:
            end = max(end, min(start + 10, item_t[-1] + 2.0))
        out.append({"id": f"fx-{stamp}-{i}", "kind": "fx", "type": typ, "place": place, "on": True,
                    "title": str(it.get("title") or "").strip()[:80], "text": str(it.get("title") or typ)[:80],
                    "items": items, "item_t": item_t, "start": round(start, 2), "end": round(end, 2),
                    "why": str(it.get("why") or "")[:160]})
    out.sort(key=lambda x: x["start"])
    clean = []
    for o in out:
        if clean and o["start"] < clean[-1]["end"]:
            if o["start"] - clean[-1]["start"] < 1.5:
                continue
            clean[-1]["end"] = round(o["start"] - 0.1, 2)
        clean.append(o)
    return clean


def suggest(transcript: dict, flags: list, allowed: list[str], engine: str, reel: bool, wish: str = "") -> list[dict]:
    words = cuts.flat_words(transcript)
    if not words:
        raise UserError("There is no transcript yet. For a clip without speech, add effects by hand.")
    allowed = [a for a in allowed if a in fx.TYPES] or list(fx.TYPES)
    prompt = build_prompt(words, flags, transcript.get("language", "de"), allowed, reel, wish)
    if engine == "claude":
        from . import claude
        data = claude.ask_json(prompt, SCHEMA, effort="medium")
    else:
        from . import llm
        data = llm.ask_json(prompt.replace("Antworte NUR mit JSON nach dem Schema.",
                                           'Antworte NUR mit JSON: {"items": [{"type": "...", "place": "scene", '
                                           '"word": 12, "end_word": 30, "title": "...", "items": [], '
                                           '"item_words": [], "why": "..."}]}'),
                            "Du antwortest ausschließlich mit gültigem JSON.", timeout=900)
    items = parse(data if isinstance(data, dict) else {}, words, flags, allowed)
    if not items:
        raise UserError("No suitable moments were found for these effects. Allow more effects or try again.")
    return items
