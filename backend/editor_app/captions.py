"""Reel-/Short-Texte: Caption in Carinas Stimme, genau 5 Hashtags, Cover-Text, YouTube-Shorts-Titel.

Wie bei den YouTube-Texten: Ollama (automatisch) oder Kopieren & Einfügen mit claude.ai, danach Prüfung.
Aufbau der Caption nach ihren Beispielen (docs/KARUSSELL_STIL.md, Abschnitt Caption).
"""
from __future__ import annotations

import json
import re

from . import meta
from .errors import UserError

SCHEMA = """{
  "caption": "Caption (mehrere kurze Absätze, mit Zeilenumbrüchen \\n)",
  "hashtags": ["#a", "#b", "#c", "#d", "#e"],
  "cover_text": "Cover-Text, 2–4 kurze Zeilen",
  "shorts_title": "YouTube-Shorts-Titel"
}"""


def build_prompt(transcript_text: str, language: str, hook: str = "") -> str:
    lang = "Deutsch" if language == "de" else "Englisch"
    account = "@carinadorca.coach" if language == "de" else "@carina.dorca"
    bank = ", ".join(meta.hashtag_bank(language)[:30])
    return f"""Du schreibst für Carina Dorca (Instagram {account}, YouTube Shorts), Stress- und Burnout-Prävention.
Hier ist, was sie im Reel sagt (Sprache: {lang}):

{transcript_text}
{f'Text auf der Hook-Karte im Video: {hook}' if hook else ''}

{meta.GUARDRAILS}

Schreibe auf {lang}:
1. Caption in Carinas Stimme, genau in diesem Aufbau:
   - erste Zeile = Hook (greift die Aussage des Reels auf) + 🤍
   - 2–3 sehr kurze Absätze (konkret, persönlich, keine Floskeln)
   - eine kleine Aufgabe für diese Woche ("This week: …" / "Diese Woche: …")
   - "📌 Save this for …" und "💌 Share it with someone who …" (auf Deutsch sinngemäß)
   - "Follow {account} for more about anxiety, stress & burnout prevention" (auf Deutsch sinngemäß)
   - letzte Zeile: "Educational and my own experience, not a diagnosis or therapy." (auf Deutsch sinngemäß)
   - KEINE Hashtags in der Caption selbst
2. GENAU 5 Hashtags, bevorzugt aus dieser Sammlung: {bank}
3. Cover-Text: 2–4 kurze Zeilen, polarisierend und konkret (kein "in case no one told you").
4. YouTube-Shorts-Titel: max. 70 Zeichen, neugierig machend.

Antworte NUR mit JSON in genau diesem Format:
{SCHEMA}
"""


def parse(text_or_obj, language: str) -> dict:
    if isinstance(text_or_obj, str):
        m = re.search(r"\{.*\}", text_or_obj, re.S)
        if not m:
            raise UserError("In der eingefügten Antwort wurde kein JSON gefunden. Bitte die komplette Antwort kopieren.")
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError as exc:
            raise UserError("Die eingefügte Antwort ist kein gültiges JSON. Bitte nochmal komplett kopieren.") from exc
    else:
        data = text_or_obj
    warnings: list[str] = []
    caption = str(data.get("caption", "")).strip()
    # Hashtags, die doch in der Caption stehen, herausnehmen und mitzählen
    inline = re.findall(r"#[\wäöüß]+", caption)
    caption = re.sub(r"(\s*#[\wäöüß]+)+\s*$", "", caption).strip()
    hashtags = meta.fix_hashtags(list(data.get("hashtags", [])) + inline, language, warnings)
    cover = str(data.get("cover_text", "")).strip()
    title = str(data.get("shorts_title", "")).strip()
    if len(title) > 100:
        warnings.append("Shorts-Titel ist länger als 100 Zeichen.")
    if not caption:
        warnings.append("Die Caption fehlt.")
    low = " ".join([caption, cover, title]).lower()
    for pat in meta.FORBIDDEN:
        m = re.search(pat, low)
        if m:
            warnings.append(f"Achtung, möglicherweise Heilversprechen/heikle Aussage: „{m.group(0)}“ – bitte umformulieren.")
    if "diagnos" not in low and "therap" not in low:
        warnings.append("Hinweis „keine Diagnose oder Therapie“ fehlt in der Caption.")
    return {"caption": caption, "hashtags": hashtags, "cover_text": cover, "shorts_title": title, "warnings": warnings}


def full_caption(d: dict) -> str:
    return (d.get("caption", "").strip() + "\n\n" + " ".join(d.get("hashtags", []))).strip()


def from_ollama(prompt: str, language: str) -> dict:
    from . import llm

    data = llm.ask_json(prompt, "Du antwortest ausschließlich mit gültigem JSON.", timeout=600)
    if not isinstance(data, dict):
        raise UserError("Die lokale KI hat kein passendes Ergebnis geliefert. Bitte nochmal versuchen "
                        "oder den Weg über claude.ai nehmen.")
    return parse(data, language)
