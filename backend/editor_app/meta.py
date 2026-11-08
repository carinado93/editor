"""YouTube-Texte: Kapitel, 3 Titel, Beschreibung, Tags.

Zwei Wege, beide kostenlos:
1. Ollama auf Carinas PC (automatisch).
2. Kopieren & Einfügen: Die App erstellt den fertigen Auftrag, Carina fügt ihn in claude.ai ein und kopiert die
   Antwort zurück. Die App prüft die Antwort (Format, Kapitel-Regeln, keine Heilversprechen).
"""
from __future__ import annotations

import json
import re

from .errors import UserError

GUARDRAILS = """Inhaltliche Leitplanken (immer einhalten):
- Carina Dorca ist Stress- und Burnout-Coachin: nur PRÄVENTION, keine Heilversprechen. Nicht: "Burnout besiegen",
  "nie wieder Angst", "Heilung", "heilen", "beat burnout", "cure". Besser: "vorbeugen", "Wohlbefinden", "Gewohnheiten".
- Wissenschaftlich vorsichtig: keine umstrittenen kausalen Behauptungen (z. B. "Emotionen im Körper gespeichert"),
  kein Schuldzuweisen ("Opfermentalität"), keine "ein Geheimnis für alles"-Versprechen.
- Bei sensiblen Themen in die Beschreibung: "Hinweis: Dieses Video ersetzt keine Diagnose oder Therapie."
  Bei Symptomen: "Bitte ärztlich abklären lassen." (auf Englisch entsprechend: "This video is not a diagnosis or therapy.")
- Konkrete, leicht polarisierende Titel statt generischer ("in case no one told you…" funktioniert nicht).
  Zielgruppe Gen Z und Boomer, professionell. Am Ende der Beschreibung klar sagen, was Carina anbietet.
- In Carinas Stimme: warm, klar, direkt, "du"-Ansprache auf Deutsch."""

FORBIDDEN = [r"\bheil(en|ung|t)\b", r"nie wieder", r"besieg", r"\bbeat (your )?burnout\b", r"\bcure[sd]?\b",
             r"\bheal(s|ed|ing)?\b", r"garantiert", r"guaranteed", r"opfermentalität", r"victim mentality",
             r"emotionen im körper gespeichert", r"stored in (the|your) body", r"das eine geheimnis", r"the one secret"]

SCHEMA = """{
  "titles": ["Titel 1", "Titel 2", "Titel 3"],
  "chapters": [{"time": "0:00", "title": "Einleitung"}, {"time": "1:23", "title": "…"}],
  "description": "Beschreibung (mehrere Absätze, ohne Kapitel – die fügt die App an)",
  "tags": ["tag1", "tag2", "…"],
  "hashtags": ["#tag1", "#tag2", "#tag3"]
}"""


def _fmt(t: float) -> str:
    s = int(max(0, t))
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def timed_text(sentences: list[tuple[float, str]]) -> str:
    return "\n".join(f"[{_fmt(t)}] {s}" for t, s in sentences)


def build_prompt(sentences: list[tuple[float, str]], language: str, duration: float, title_hint: str = "") -> str:
    lang = "Deutsch" if language == "de" else "Englisch"
    n_chapters = max(3, min(12, round(duration / 90)))
    return f"""Du bist YouTube-Strategin für Carina Dorca (Kanal @Cary-redet, Stress- und Burnout-Prävention).
Hier ist das Transkript ihres fertig geschnittenen Videos (Sprache: {lang}, Länge {_fmt(duration)}).
Die Zeitangaben in eckigen Klammern sind die Zeiten im fertigen Video.

{GUARDRAILS}

Aufgabe (alles auf {lang}):
1. Genau 3 Titelvorschläge (max. 70 Zeichen, konkret, neugierig machend, keine Clickbait-Lügen).
2. Etwa {n_chapters} Kapitel. Das erste MUSS bei 0:00 beginnen, mindestens 10 Sekunden Abstand, Zeiten aus dem
   Transkript, kurze Kapitelnamen.
3. Beschreibung: 2–4 kurze Absätze in Carinas Stimme, erster Satz = Hook, am Ende ihr Angebot / Call-to-Action.
4. 10–15 Tags (Suchbegriffe), 3 Hashtags.
{f'Arbeitstitel von Carina: {title_hint}' if title_hint else ''}

Antworte NUR mit JSON in genau diesem Format, ohne weiteren Text:
{SCHEMA}

Transkript:
{timed_text(sentences)}
"""


def _seconds(text: str) -> float | None:
    m = re.fullmatch(r"\s*(?:(\d+):)?(\d{1,2}):(\d{2})\s*", str(text))
    if not m:
        return None
    h, mi, s = int(m.group(1) or 0), int(m.group(2)), int(m.group(3))
    return h * 3600 + mi * 60 + s


def parse(text_or_obj, duration: float) -> dict:
    """Prüft eine KI-Antwort und gibt {titles, chapters, description, tags, hashtags, warnings} zurück."""
    if isinstance(text_or_obj, str):
        m = re.search(r"\{.*\}", text_or_obj, re.S)
        if not m:
            raise UserError("In der eingefügten Antwort wurde kein JSON gefunden. Bitte die komplette Antwort von "
                            "claude.ai kopieren (sie beginnt mit '{').")
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError as exc:
            raise UserError("Die eingefügte Antwort ist kein gültiges JSON. Bitte nochmal komplett kopieren.") from exc
    else:
        data = text_or_obj
    warnings = []
    titles = [str(t).strip() for t in data.get("titles", []) if str(t).strip()][:3]
    if len(titles) < 3:
        warnings.append(f"Nur {len(titles)} Titel statt 3.")
    chapters = []
    for c in data.get("chapters", []):
        t = _seconds(c.get("time", "")) if isinstance(c, dict) else None
        if t is None or t > duration:
            continue
        if chapters and t - chapters[-1]["t"] < 10:
            continue  # YouTube: mindestens 10 s Abstand
        chapters.append({"t": t, "time": _fmt(t), "title": str(c.get("title", "")).strip()})
    if chapters and chapters[0]["t"] != 0:
        if chapters[0]["t"] < 10:  # knapp nach 0:00 → auf 0:00 vorziehen
            chapters[0].update({"t": 0, "time": "0:00"})
        else:
            chapters.insert(0, {"t": 0, "time": "0:00", "title": "Intro"})
    if len(chapters) < 3:
        warnings.append("YouTube zeigt Kapitel erst ab 3 Stück an.")
    tags = [str(t).strip().lstrip("#") for t in data.get("tags", []) if str(t).strip()][:20]
    hashtags = ["#" + str(t).strip().lstrip("#").replace(" ", "") for t in data.get("hashtags", []) if str(t).strip()][:3]
    description = str(data.get("description", "")).strip()
    all_text = " ".join(titles + [description] + [c["title"] for c in chapters]).lower()
    for pat in FORBIDDEN:
        m = re.search(pat, all_text)
        if m:
            warnings.append(f"Achtung, möglicherweise Heilversprechen/heikle Aussage: „{m.group(0)}“ – bitte umformulieren.")
    return {"titles": titles, "chapters": chapters, "description": description, "tags": tags,
            "hashtags": hashtags, "warnings": warnings}


def full_description(meta: dict) -> str:
    """Beschreibung + Kapitel + Hashtags, fertig zum Einfügen bei YouTube."""
    parts = [meta.get("description", "").strip()]
    if meta.get("chapters"):
        parts.append("\n".join(f"{c['time']} {c['title']}" for c in meta["chapters"]))
    if meta.get("hashtags"):
        parts.append(" ".join(meta["hashtags"]))
    return "\n\n".join(p for p in parts if p)


def from_ollama(prompt: str, duration: float) -> dict:
    from . import llm

    data = llm.ask_json(prompt, "Du antwortest ausschließlich mit gültigem JSON.", timeout=600)
    if not isinstance(data, dict):
        raise UserError("Die lokale KI hat kein passendes Ergebnis geliefert. Bitte nochmal versuchen "
                        "oder den Weg über claude.ai nehmen.")
    return parse(data, duration)
