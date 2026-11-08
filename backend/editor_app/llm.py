"""Lokale KI über Ollama (läuft auf Carinas PC, kostenlos). Standard-Modell: gemma3:12b."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

from .errors import UserError

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:12b")


def ask_json(prompt: str, system: str = "", timeout: float = 300) -> dict | list:
    body = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "system": system, "stream": False,
                       "format": "json", "options": {"temperature": 0.3}}).encode()
    req = urllib.request.Request(f"{OLLAMA_URL}/api/generate", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise UserError(f"Ollama kennt das Modell '{OLLAMA_MODEL}' nicht. Bitte in einem Terminal "
                            f"'ollama pull {OLLAMA_MODEL}' ausführen.") from exc
        raise UserError(f"Ollama hat einen Fehler gemeldet ({exc.code}).") from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise UserError("Ollama läuft nicht. Bitte starte die Ollama-App (Symbol unten rechts in der Taskleiste) "
                        "und versuche es nochmal.") from exc
    text = data.get("response", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"[\[{].*[\]}]", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise UserError("Die lokale KI hat keine brauchbare Antwort geliefert. Bitte nochmal versuchen.")


BUZZ_SYSTEM = (
    "Du bist Video-Editorin für Carina Dorca, Stress- und Burnout-Coachin (nur Prävention, keine Heilversprechen). "
    "Du wählst Schlüsselwörter, die im Video als animierte Text-Einblendung erscheinen."
)


def suggest_buzzwords(numbered_text: str, language: str, count: int) -> list[dict]:
    lang = "Deutsch" if language == "de" else "Englisch"
    prompt = f"""Hier ist das Transkript eines Videos ({lang}). Jedes Wort hat eine Nummer in eckigen Klammern.

{numbered_text}

Wähle die {count} stärksten Buzzwords oder ganz kurzen Kernphrasen (1 bis 3 Wörter), die als Text-Einblendung
den Inhalt verstärken: emotionale Schlüsselwörter, Zahlen, Kernbegriffe (z. B. "Burnout", "nicht alles auf einmal").
Keine Füllwörter, keine Wiederholungen, gleichmäßig über das Video verteilt.
Antworte NUR als JSON: {{"buzzwords": [{{"start": <Nummer des ersten Worts>, "end": <Nummer des letzten Worts>}}]}}"""
    data = ask_json(prompt, BUZZ_SYSTEM)
    items = data.get("buzzwords", []) if isinstance(data, dict) else data
    out = []
    for it in items:
        try:
            a, b = int(it["start"]), int(it["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= a <= b and b - a < 4:
            out.append({"start": a, "end": b + 1})
    return out
