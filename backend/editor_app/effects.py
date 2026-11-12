"""Effekt-Vorschläge: Claude (oder Ollama) sucht passende Momente für die Effekte, die Carina erlaubt hat.

Gespeichert wird jeder Effekt in der Schnittliste unter "overlays" (kind "fx"), Zeiten in Original-Zeit.
"""
from __future__ import annotations

import time

from . import animations, cuts, fx, meta
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
    "clothesline": "Wäscheleine oben, 2–5 Karten hängen an Klammern (items = Kartentexte, je 1–3 Wörter; title optional als großes Wort darunter) – Dinge, die sie nutzt/zeigt, Beispiele",
    "lighttrail": "Leuchtspur läuft um Carinas Umriss (title leer) – Aha-Moment, Betonung",
    "sticker": "Sticker-Köpfe: Carinas Kopf zweimal als Sticker auf Lavendel, das gesprochene Wort groß in der Mitte (title leer) – lustiger, lockerer Moment, 2–4 s",
    "counter": "große Zahl zählt hinter Carina hoch (title = 'Zahl|Wort', z. B. '120|Tage') – wenn sie eine Zahl nennt",
    "typewriter": "Text tippt sich Buchstabe für Buchstabe oben ein (title, max. 8 Wörter) – Frage, Einstieg",
    "ghost": "durchsichtige Kopien von Carina folgen ihrer Bewegung (title leer) – nur wenn sie sich deutlich bewegt",
    "whip": "Zoom-Blur-Übergang (title leer, 0,6 s) – genau an einem Themenwechsel",
    "label": "lila Kasten mit weißen Großbuchstaben auf Brusthöhe (title, max. 5 Wörter) – Kernaussage, SEO-Wort wie BURNOUT, STRESS, ANGST",
    "quotepill": "cremefarbene Pille mit Merksatz, ein *Wort* lila-kursiv (title, max. 7 Wörter) – ruhige Erkenntnis",
    "number": "Wort + große Zahl neben ihr (title = 'Wort|Zahl', z. B. 'Burnout|×3') – Zahlen, Wiederholungen",
    "name": "Bauchbinde mit Name und Titel (title = 'Carina Dorca|Stress- & Burnout-Coach') – nur einmal, wenn sie sich vorstellt",
    "stickers": "Handschrift-Zettel erscheinen nacheinander (items = Punkte, je 1–4 Wörter) – Aufzählungen",
    "buzzword": "ein Schlüsselwort poppt neben ihrem Gesicht auf (title = 1–2 Wörter) – wichtige Begriffe, oft",
    "outro": "Schluss eines YouTube-Videos: 'Thank you for watching' + Like- und Abo-Knopf (title leer lassen, items leer) – genau einmal, die letzten 5–7 Sekunden",
    "statement": "Statement-Karte: ganzer Bildschirm weicher Lila-Verlauf, eine kurze Zeile in kleinen fetten Großbuchstaben (title, max. 6 Wörter, z. B. 'ABER DU HAST ES NICHT GETAN.') – im Wechsel mit Clips, 1,5–2 s",
    "quote": "Zitat auf dem Clip in kursiver Serifenschrift (title, max. 12 Wörter, in Anführungszeichen) – Gedanke, innere Stimme",
    "repeat": "Satz oben, darunter wiederholt sich eine Wendung Zeile für Zeile (title = Satz, items = [Wendung, z. B. '& nochmal']) – Durchhalten, Wiederholung",
    "wordswap": "fester Satz, das letzte Wort wechselt (title = fester Teil, items = 4–6 wechselnde Wörter) – Gefühle, Zustände",
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


def clean(o: dict, duration: float | None = None) -> dict | None:
    """Einen Effekt aus dem Formular prüfen und aufräumen (gleich für Video und Reel)."""
    typ = o.get("type")
    if typ not in fx.TYPES:
        return None
    s_ = max(0.0, float(o.get("start", 0)))
    e_ = max(s_ + 0.8, float(o.get("end", s_ + 4)))
    if duration:
        e_ = min(e_, duration)
        if e_ - s_ < 0.5:
            return None
    places = fx.TYPES[typ][2]
    title = str(o.get("title") or "").strip()[:80]
    return {"id": str(o.get("id") or f"fx-{int(time.time() * 1000)}"), "kind": "fx", "type": typ,
            "place": o.get("place") if o.get("place") in places else places[0], "on": bool(o.get("on", True)),
            "title": title, "text": title or typ, "items": [str(x).strip()[:60] for x in o.get("items") or []
                                                           if str(x).strip()][:6],
            "item_t": [round(float(x), 2) for x in o.get("item_t") or []][:6], "start": round(s_, 2),
            "end": round(e_, 2), "why": str(o.get("why") or "")[:160],
            "bg_t": round(float(o["bg_t"]), 2) if o.get("bg_t") is not None else None,
            "pose_t": [round(float(x), 2) for x in o.get("pose_t") or []][:8],
            "mode": "appear" if o.get("mode") == "appear" else "vanish",
            "scale": round(max(0.4, min(2.5, float(o.get("scale") or 1))), 2)}


def clip_transcript(transcript: dict, flags: list, segments: list[list[float]]) -> dict:
    """Die Wörter eines Reels in Reel-Zeit (Stücke können aus verschiedenen Stellen kommen)."""
    words = cuts.flat_words(transcript)
    out, offset = [], 0.0
    for a, b in segments:
        for k, w in enumerate(words):
            if not (flags and flags[k]) and a <= (w["s"] + w["e"]) / 2 <= b:
                out.append({"w": w["w"], "s": round(offset + max(0.0, w["s"] - a), 3),
                            "e": round(offset + min(b, w["e"]) - a, 3), "p": w.get("p", 1)})
        offset += b - a
    return {"language": transcript.get("language", "de"), "segments": [{"s": 0, "e": offset, "text": "", "words": out}]}


def clip_to_orig(segments: list[list[float]], t: float) -> float:
    """Reel-Zeit → Zeit im langen Video."""
    off = 0.0
    for a, b in segments:
        if t <= off + (b - a):
            return a + (t - off)
        off += b - a
    return segments[-1][1] if segments else t


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

{meta.lang_rule(language)}
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


SILENT_SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": list(fx.TYPES)},
            "place": {"type": "string", "enum": ["scene", "side"]},
            "start": {"type": "number"}, "end": {"type": "number"},
            "title": {"type": "string"},
            "items": {"type": "array", "items": {"type": "string"}},
            "why": {"type": "string"},
        },
        "required": ["type", "place", "start", "end", "title", "items", "why"],
        "additionalProperties": False,
    }}},
    "required": ["items"],
    "additionalProperties": False,
}


def suggest_silent(stills: list[str], duration: float, language: str, allowed: list[str], engine: str,
                   wish: str = "", idea: str = "") -> list[dict]:
    """Clip ohne Sprechen: Claude schaut sich Standbilder an und plant Effekte mit Texten nach Sekunden."""
    allowed = [a for a in allowed if a in fx.TYPES and a not in ("bigwords", "sticker") and a not in fx.NO_AUTO_FILL
               and a in DESCRIBE] or ["headline", "pill"]
    lang = "Deutsch" if language == "de" else "Englisch"
    times = ", ".join(f"Bild {k + 1} ≈ {duration * (k + 0.5) / len(stills):.1f} s" for k in range(len(stills)))
    menu = "\n".join(f"- {k} ({fx.TYPES[k][1]}): {DESCRIBE[k]}" for k in allowed)
    prompt = f"""Du bist Video-Editorin für Carina Dorca (Stress- und Burnout-Prävention). Ihr Reel ist {duration:.1f} s
lang und sie spricht darin NICHT – die Texte im Video erzählen die Botschaft. Angehängt sind Standbilder ({times}).
Texte auf {lang}.
{f'Ihre Idee / Anweisung: {idea.strip()}' if idea.strip() else 'Leite das Thema aus den Bildern ab.'}
{f'Wunsch: {wish.strip()}' if wish.strip() else ''}

Erlaubte Effekte:
{menu}

Regeln:
- Der erste Effekt beginnt bei 0 s und ist der Hook (sagt sofort, worum es geht, polarisierend und konkret).
- Danach 1–4 weitere Effekte, die die Botschaft Schritt für Schritt erzählen; jeder 2,5–6 s lang, nie gleichzeitig.
- "start"/"end" in Sekunden (0 bis {duration:.1f}). Texte kurz, in Carinas warmer, direkter Stimme, keine Heilversprechen.
- Bei Listen-Effekten stehen die Punkte in "items", sonst leer.
{meta.lang_rule(language)}
Antworte NUR mit JSON nach dem Schema."""
    if engine == "claude":
        from . import claude
        data = claude.ask_json(prompt, SILENT_SCHEMA, effort="medium", images=stills)
    else:
        from . import llm
        data = llm.ask_json(prompt.replace("Antworte NUR mit JSON nach dem Schema.",
                                           'Antworte NUR mit JSON: {"items": [{"type": "headline", "place": "scene", '
                                           '"start": 0, "end": 4, "title": "...", "items": [], "why": "..."}]}'),
                            "Du antwortest ausschließlich mit gültigem JSON.", timeout=600, images=stills)
    out = []
    for i, it in enumerate((data or {}).get("items") or []):
        o = clean(dict(it, id=f"fx-{int(time.time() * 1000) % 10_000_000}-{i}"), duration)
        if o and o["type"] in allowed:
            out.append(o)
    out.sort(key=lambda x: x["start"])
    clean_list = []
    for o in out:
        if clean_list and o["start"] < clean_list[-1]["end"]:
            clean_list[-1]["end"] = round(max(clean_list[-1]["start"] + 1.0, o["start"] - 0.1), 2)
        clean_list.append(o)
    if not clean_list:
        raise UserError("No effects were suggested. Please write a short idea into the wish box and try again.")
    return clean_list


def suggest(transcript: dict, flags: list, allowed: list[str], engine: str, reel: bool, wish: str = "") -> list[dict]:
    words = cuts.flat_words(transcript)
    if not words:
        raise UserError("There is no transcript yet. For a clip without speech, add effects by hand.")
    allowed = [a for a in allowed if a in fx.TYPES and a not in fx.NO_AUTO_FILL and a in DESCRIBE] or ["headline"]
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
