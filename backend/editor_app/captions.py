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


SCENE_SCHEMA = """{
  "scenes": ["Text Szene 1 (Hook)", "Text Szene 2", "…"],
  "caption": "Caption (mehrere kurze Absätze, mit Zeilenumbrüchen \\n)",
  "hashtags": ["#a", "#b", "#c", "#d", "#e"],
  "cover_text": "Cover-Text, 2–4 kurze Zeilen",
  "shorts_title": "YouTube-Shorts-Titel"
}"""

READ_SECONDS = 4.4  # so lange muss eine Aussage stehen (Carinas Erfahrung)


ANIMS = ["pop", "karte", "wort", "slide"]


def build_idea_prompt(idea: str, language: str, duration: float, transcript_text: str = "",
                      with_images: bool = False) -> str:
    """Für Reels, in denen Carina nicht (oder nur wenig) spricht: aus ihrer Idee Szenen-Texte + Caption machen."""
    lang = "Deutsch" if language == "de" else "Englisch"
    account = "@carinadorca.coach" if language == "de" else "@carina.dorca"
    bank = ", ".join(meta.hashtag_bank(language)[:30])
    max_scenes = max(1, int(duration // READ_SECONDS)) if duration else 6
    n = max(1, min(max_scenes, 6))
    return f"""Du schreibst für Carina Dorca (Instagram {account}, YouTube Shorts), Stress- und Burnout-Prävention.
Sie hat einen Clip von {duration:.0f} Sekunden gefilmt{', in dem sie nicht spricht' if not transcript_text else ''}.
{'Angehängt sind Standbilder aus dem Clip (in zeitlicher Reihenfolge): Schau genau hin, worum es geht.' if with_images else ''}
Ihre Idee / Anweisung für das Reel:
>>> {idea.strip() or '(keine – leite das Thema aus dem Clip ab)'} <<<
{f'Was im Clip gesagt wird: {transcript_text}' if transcript_text else ''}

{meta.GUARDRAILS}

Schreibe auf {lang}:
1. Texte, die nacheinander im Video eingeblendet werden: höchstens {n} Szenen (jede steht ca. {READ_SECONDS} s).
   Szene 1 = Hook ab Sekunde 0: sagt sofort, worum es im Reel geht, polarisierend und konkret
   (kein "in case no one told you"). Kurze Sätze (max. 12 Wörter),
   die letzte Szene sagt klar, was Carina anbietet oder was die Zuschauerin tun soll.
   Ein Schlüsselwort pro Szene in *Sternchen* (wird lila-kursiv).
2. Caption in Carinas Stimme: erste Zeile Hook + 🤍, 2–3 sehr kurze Absätze, eine kleine Aufgabe für diese Woche,
   "📌 Save this for …", "💌 Share it with someone who …", "Follow {account} for more about anxiety, stress & burnout
   prevention", letzte Zeile "Educational and my own experience, not a diagnosis or therapy." (auf Deutsch sinngemäß).
   KEINE Hashtags in der Caption.
3. GENAU 5 Hashtags, bevorzugt aus: {bank}
4. Cover-Text (2–4 kurze Zeilen) und YouTube-Shorts-Titel (max. 70 Zeichen).

Antworte NUR mit JSON in genau diesem Format:
{SCENE_SCHEMA}
"""


def distribute_scenes(scenes: list[str], duration: float) -> tuple[list[dict], list[str]]:
    """Szenen gleichmäßig über den Clip verteilen; jede mindestens 4,4 s, wenn es die Länge erlaubt."""
    warnings = []
    scenes = [str(x).strip() for x in scenes if str(x).strip()]
    if not scenes or duration <= 0:
        return [], warnings
    slot = duration / len(scenes)
    if slot < READ_SECONDS:
        keep = max(1, int(duration // READ_SECONDS))
        warnings.append(f"The clip is too short for {len(scenes)} texts of {READ_SECONDS:.1f} s each – "
                        f"only the first {keep} are shown.")
        scenes = scenes[:keep]
        slot = duration / len(scenes)
    out = []
    show = max(READ_SECONDS, min(6.0, slot - 0.2))  # jeder Text 4,4–6 s sichtbar, nie ewig lange
    for i, text in enumerate(scenes):
        start = round(i * slot + (0.2 if i == 0 else 0.1), 2)
        end = round(min(duration, start + show, (i + 1) * slot - 0.05), 2)
        anim = "pop" if i == 0 else ["karte", "wort", "slide"][(i - 1) % 3]  # Animationen wechseln sich ab
        out.append({"id": f"szene-{i + 1}", "kind": "hook" if i == 0 else "szene", "start": start, "end": end,
                    "text": text, "on": True, "anim": anim})
    return out, warnings


def parse(text_or_obj, language: str) -> dict:
    if isinstance(text_or_obj, str):
        m = re.search(r"\{.*\}", text_or_obj, re.S)
        if not m:
            raise UserError("No JSON was found in the pasted answer. Please copy the complete answer.")
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError as exc:
            raise UserError("The pasted answer is not valid JSON. Please copy it again completely.") from exc
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
        warnings.append("The Shorts title is longer than 100 characters.")
    if not caption:
        warnings.append("The caption is missing.")
    low = " ".join([caption, cover, title]).lower()
    for pat in meta.FORBIDDEN:
        m = re.search(pat, low)
        if m:
            warnings.append(f"Careful, possibly a healing promise / risky claim: \"{m.group(0)}\" – please rephrase.")
    if "diagnos" not in low and "therap" not in low:
        warnings.append("The note \"not a diagnosis or therapy\" is missing in the caption.")
    scenes = [str(x).strip() for x in data.get("scenes", []) if str(x).strip()]
    for sc in scenes:
        for pat in meta.FORBIDDEN:
            m = re.search(pat, sc.lower())
            if m:
                warnings.append(f"Careful in the scene text: \"{m.group(0)}\" – please rephrase.")
    return {"caption": caption, "hashtags": hashtags, "cover_text": cover, "shorts_title": title, "scenes": scenes,
            "warnings": warnings}


def full_caption(d: dict) -> str:
    return (d.get("caption", "").strip() + "\n\n" + " ".join(d.get("hashtags", []))).strip()


def from_ollama(prompt: str, language: str) -> dict:
    from . import llm

    data = llm.ask_json(prompt, "Du antwortest ausschließlich mit gültigem JSON.", timeout=600)
    if not isinstance(data, dict):
        raise UserError("The local AI did not give a suitable result. Please try again "
                        "or use \"Create with Claude\".")
    return parse(data, language)
