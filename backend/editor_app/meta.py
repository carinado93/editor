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


def lang_rule(language: str) -> str:
    """Klare Ansage, in welcher Sprache die Texte sein müssen. Die Anweisungen sind deutsch geschrieben –
    ohne diese Zeile antwortet Claude sonst auch bei englischen Videos auf Deutsch."""
    if language == "de":
        return ("SPRACHE DER ANTWORT: Alle Texte, die im Video oder beim Posten erscheinen (Hook, Einblendungen, "
                "Effekt-Texte, Caption, Titel, Hashtags), auf DEUTSCH.")
    return ("OUTPUT LANGUAGE: The video is in ENGLISH. Write EVERY text in your answer in ENGLISH – titles, hook "
            "text, on-screen texts, effect texts, captions, Shorts title, chapters, descriptions, notes and "
            "explanations ('why'). Hashtags in English. These instructions are written in German, but your "
            "answer must not contain German.")

FORBIDDEN = [r"\bheil(en|ung|t)\b", r"nie wieder", r"besieg", r"\bbeat (your )?burnout\b", r"\bcure[sd]?\b",
             r"\bheal(s|ed|ing)?\b", r"garantiert", r"guaranteed", r"opfermentalität", r"victim mentality",
             r"emotionen im körper gespeichert", r"stored in (the|your) body", r"das eine geheimnis", r"the one secret"]

SCHEMA = """{
  "seo_keyword": "der Suchbegriff, den Leute bei YouTube eintippen (2–4 Wörter)",
  "titles": ["Titel 1", "Titel 2", "Titel 3", "Titel 4", "Titel 5"],
  "thumb_hooks": ["kurzer Thumbnail-Text mit *Schlüsselwort*", "…", "…", "…", "…"],
  "chapters": [{"time": "0:00", "title": "Einleitung"}, {"time": "1:23", "title": "…"}],
  "description": "Beschreibung (mehrere Absätze, ohne Kapitel – die fügt die App an)",
  "tags": ["tag1", "tag2", "…"],
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"]
}"""


def _fmt(t: float) -> str:
    s = int(max(0, t))
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def timed_text(sentences: list[tuple[float, str]]) -> str:
    return "\n".join(f"[{_fmt(t)}] {s}" for t, s in sentences)


HASHTAG_COUNT = 5


def _learned_file():
    from .config import ROOT
    return ROOT / "daten" / "hashtags_gelernt.json"


def hashtag_bank(language: str) -> list[str]:
    """Carinas Grund-Sammlung (vorlagen/hashtags.json) + automatisch gelernte (daten/, nur auf ihrem PC)."""
    from .config import ROOT
    out: list[str] = []
    for f in (ROOT / "vorlagen" / "hashtags.json", _learned_file()):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for h in data.get(language) or []:
            if h.lower() not in {x.lower() for x in out}:
                out.append(h)
    return out


def learn_hashtags(tags: list[str], language: str, limit: int = 300) -> None:
    """Neue Hashtags automatisch in die Sammlung aufnehmen (Carina muss nichts von Hand pflegen).
    Gespeichert in daten/hashtags_gelernt.json (nicht im Git, damit "Git: Pull" nie hängen bleibt)."""
    known = {b.lower() for b in hashtag_bank(language)}
    added = [t for t in tags if t.lower() not in known and re.fullmatch(r"#[\wäöüß]{3,40}", t)]
    if not added:
        return
    f = _learned_file()
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data[language] = (list(data.get(language, [])) + added)[-limit:]
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def fix_hashtags(tags: list[str], language: str, warnings: list[str]) -> list[str]:
    """Immer genau 5 Hashtags: zu viele → kürzen, zu wenige → aus Carinas Sammlung auffüllen.
    Neue, gute Hashtags lernt die Sammlung automatisch dazu."""
    out: list[str] = []
    for t in tags:
        h = "#" + str(t).strip().lstrip("#").replace(" ", "").lower()
        if len(h) > 1 and h not in out:
            out.append(h)
    learn_hashtags(out[:HASHTAG_COUNT], language)
    if len(out) > HASHTAG_COUNT:
        out = out[:HASHTAG_COUNT]
    if len(out) < HASHTAG_COUNT:
        for h in hashtag_bank(language):
            if len(out) >= HASHTAG_COUNT:
                break
            if h.lower() not in out:
                out.append(h.lower())
        warnings.append("Hashtags filled up to exactly 5 (from your collection).")
    return out


def build_prompt(sentences: list[tuple[float, str]], language: str, duration: float, title_hint: str = "") -> str:
    lang = "Deutsch" if language == "de" else "Englisch"
    bank = ", ".join(hashtag_bank(language)[:25])
    n_chapters = max(3, min(12, round(duration / 90)))
    return f"""Du bist YouTube-Strategin für Carina Dorca (Kanal @Cary-redet, Stress- und Burnout-Prävention).
Hier ist das Transkript ihres fertig geschnittenen Videos (Sprache: {lang}, Länge {_fmt(duration)}).
Die Zeitangaben in eckigen Klammern sind die Zeiten im fertigen Video.

{GUARDRAILS}

Aufgabe (alles auf {lang}):
0. SEO zuerst: Finde den EINEN Suchbegriff (seo_keyword, 2–4 Wörter), den Carinas Zielgruppe zu diesem Thema
   wirklich bei YouTube eintippt (z. B. "burnout recovery", "burnout symptoms", "Burnout Anzeichen").
1. Genau 5 Titelvorschläge. Jeder Titel: enthält den Suchbegriff (oder eine sehr nahe Variante) möglichst in den
   ersten 40 Zeichen, max. 60 Zeichen (sonst schneidet YouTube ab), konkret, neugierig machend, keine
   Clickbait-Lügen. 5 verschiedene Winkel: persönlich ("I …"), Zahl/Liste, Mythos/Widerspruch, Frage, Nutzen.
   Prüfe jeden Titel vor der Antwort: Suchbegriff drin? ≤ 60 Zeichen? Würde man darauf klicken? Sonst verbessern.
1b. Genau 5 Thumbnail-Hooks (thumb_hooks): max. 5 Wörter, GROSS lesbar, ergänzen den Titel statt ihn zu
   wiederholen, emotional/konkret, genau ein *Schlüsselwort* in Sternchen (wird farbig), z. B.
   "REST DIDN'T FIX MY *BURNOUT*". Ebenfalls vor der Antwort prüfen (kurz genug, Thema sofort klar).
2. Etwa {n_chapters} Kapitel. Das erste MUSS bei 0:00 beginnen, mindestens 10 Sekunden Abstand, Zeiten aus dem
   Transkript, kurze Kapitelnamen.
3. Beschreibung: 2–4 kurze Absätze in Carinas Stimme, erster Satz = Hook, am Ende ihr Angebot / Call-to-Action.
4. 10–15 Tags (Suchbegriffe) und GENAU 5 Hashtags (bevorzugt aus dieser Sammlung: {bank}).
{f'Arbeitstitel von Carina: {title_hint}' if title_hint else ''}

{lang_rule(language)}
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


def parse(text_or_obj, duration: float, language: str = "en") -> dict:
    """Prüft eine KI-Antwort und gibt {titles, chapters, description, tags, hashtags, warnings} zurück."""
    if isinstance(text_or_obj, str):
        m = re.search(r"\{.*\}", text_or_obj, re.S)
        if not m:
            raise UserError("No JSON was found in the pasted answer. Please copy the complete answer "
                            "(it starts with '{').")
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError as exc:
            raise UserError("The pasted answer is not valid JSON. Please copy it again completely.") from exc
    else:
        data = text_or_obj
    warnings = []
    titles = [str(t).strip() for t in data.get("titles", []) if str(t).strip()][:5]
    if len(titles) < 5:
        warnings.append(f"Only {len(titles)} titles instead of 5.")
    keyword = str(data.get("seo_keyword", "")).strip()
    thumb_hooks = [str(t).strip() for t in data.get("thumb_hooks", []) if str(t).strip()][:5]
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
        warnings.append("YouTube only shows chapters when there are at least 3.")
    tags = [str(t).strip().lstrip("#") for t in data.get("tags", []) if str(t).strip()][:20]
    hashtags = fix_hashtags(data.get("hashtags", []), language, warnings)
    description = str(data.get("description", "")).strip()
    all_text = " ".join(titles + [description] + [c["title"] for c in chapters]).lower()
    for pat in FORBIDDEN:
        m = re.search(pat, all_text)
        if m:
            warnings.append(f"Careful, possibly a healing promise / risky claim: \"{m.group(0)}\" – please rephrase.")
    return {"titles": titles, "chapters": chapters, "description": description, "tags": tags,
            "hashtags": hashtags, "warnings": warnings, "seo_keyword": keyword, "thumb_hooks": thumb_hooks,
            "title_seo": [seo_check(t, keyword) for t in titles],
            "hook_seo": [hook_check(h) for h in thumb_hooks]}


def _norm(s: str) -> str:
    return re.sub(r"[^\w ]", " ", s.lower())


def seo_check(title: str, keyword: str) -> list[str]:
    """Kurze SEO-Hinweise zu einem Titel. Leere Liste = alles gut."""
    notes = []
    if len(title) > 60:
        notes.append(f"{len(title)} characters – YouTube cuts after ~60")
    if keyword:
        kw = [w for w in _norm(keyword).split() if len(w) > 2]
        tl = _norm(title)
        if kw and not all(w in tl for w in kw):
            notes.append(f'search term "{keyword}" missing')
        elif kw and tl.find(kw[0]) > 40:
            notes.append("search term comes late – move it to the front")
    return notes


def hook_check(hook: str) -> list[str]:
    notes = []
    n = len(hook.replace("*", "").split())
    if n > 5:
        notes.append(f"{n} words – thumbnails read best with ≤ 5")
    if "*" not in hook:
        notes.append("no *keyword* marked")
    return notes


def full_description(meta: dict) -> str:
    """Beschreibung + Kapitel + Hashtags, fertig zum Einfügen bei YouTube."""
    parts = [meta.get("description", "").strip()]
    if meta.get("chapters"):
        parts.append("\n".join(f"{c['time']} {c['title']}" for c in meta["chapters"]))
    if meta.get("hashtags"):
        parts.append(" ".join(meta["hashtags"]))
    return "\n\n".join(p for p in parts if p)


def from_ollama(prompt: str, duration: float, language: str = "en") -> dict:
    from . import llm

    data = llm.ask_json(prompt, "Du antwortest ausschließlich mit gültigem JSON.", timeout=600)
    if not isinstance(data, dict):
        raise UserError("The local AI did not give a suitable result. Please try again "
                        "or use \"Create with Claude\".")
    return parse(data, duration, language)
