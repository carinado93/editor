"""Wochen-Plan für Carinas Content: Ideen mit Datum, Format und Status. Claude plant eine Woche oder holt Ideen
aus einem Chat-Text. Gespeichert auf Carinas PC in daten/plan.json."""
from __future__ import annotations

import json
import re
import threading
import time
from datetime import date, timedelta

from . import meta
from .config import ROOT
from .errors import UserError

FILE = ROOT / "daten" / "plan.json"
TYPES = ("reel", "carousel", "youtube", "letter", "story")
STATUSES = ("idea", "doing", "done")
_lock = threading.Lock()

ITEM_SCHEMA = {"type": "object", "properties": {
    "date": {"type": "string"}, "type": {"type": "string", "enum": list(TYPES)}, "title": {"type": "string"},
    "idea": {"type": "string"}, "account": {"type": "string"}},
    "required": ["date", "type", "title", "idea", "account"], "additionalProperties": False}
SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": ITEM_SCHEMA}},
          "required": ["items"], "additionalProperties": False}


def _load() -> list[dict]:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save(items: list[dict]) -> list[dict]:
    FILE.parent.mkdir(parents=True, exist_ok=True)
    items.sort(key=lambda x: (x.get("date") or "9999", x.get("created", 0)))
    FILE.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    return items


def list_all() -> list[dict]:
    return _load()


def _clean(raw: dict) -> dict:
    d = str(raw.get("date") or "").strip()[:10]
    if d and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        d = ""
    return {
        "date": d,  # leer = Ideen-Kiste (noch ohne Tag)
        "type": raw.get("type") if raw.get("type") in TYPES else "reel",
        "title": str(raw.get("title", "")).strip()[:140] or "New idea",
        "idea": str(raw.get("idea", "")).strip()[:2000],
        "account": str(raw.get("account", "")).strip()[:40],
        "status": raw.get("status") if raw.get("status") in STATUSES else "idea",
    }


def add(raw_items: list[dict]) -> list[dict]:
    with _lock:
        items = _load()
        for n, r in enumerate(raw_items):
            it = _clean(r)
            it["id"] = f"p{int(time.time() * 1000)}{n}"
            it["created"] = time.time()
            items.append(it)
        return _save(items)


def update(pid: str, patch: dict) -> list[dict]:
    with _lock:
        items = _load()
        for it in items:
            if it["id"] == pid:
                merged = _clean({**it, **{k: v for k, v in patch.items() if v is not None}})
                it.update(merged)
                if "link" in patch:
                    it["link"] = patch["link"]
        return _save(items)


def delete(pid: str) -> list[dict]:
    with _lock:
        return _save([it for it in _load() if it["id"] != pid])


def _ask(prompt: str, engine: str) -> list[dict]:
    if engine == "claude":
        from . import claude
        raw = claude.ask_json(prompt, SCHEMA, effort="medium")
    else:
        from . import llm
        raw = llm.ask_json(prompt, "Du antwortest ausschließlich mit gültigem JSON.", timeout=900)
    return [r for r in (raw.get("items", []) if isinstance(raw, dict) else []) if isinstance(r, dict)]


ACCOUNTS = ("carina.dorca (EN coaching)", "carinadorca.coach (DE coaching)", "YouTube @Cary-redet",
            "thelongexhale.book (EN letters)", "lieberschatten.buch (DE letters)")


def generate_week(start: str, focus: str, counts: dict, language: str, engine: str = "claude") -> list[dict]:
    """Eine Woche planen (Mo–So ab `start`). counts: {"reel": 3, "carousel": 2, "youtube": 1, "letter": 0}."""
    try:
        d0 = date.fromisoformat(start[:10])
    except ValueError:
        d0 = date.today()
    d0 -= timedelta(days=d0.weekday())  # immer ab Montag
    days = [(d0 + timedelta(days=k)).isoformat() for k in range(7)]
    want = ", ".join(f"{int(v)}× {k}" for k, v in counts.items() if k in TYPES and int(v or 0) > 0) or "3× reel, 2× carousel, 1× youtube"
    taken = [f"- {it['title']}" for it in _load()][-40:]
    lang = "Deutsch" if language == "de" else "Englisch"
    prompt = f"""Du bist die Social-Media-Partnerin von Carina Dorca (Stress- & Burnout-Prävention; Instagram @carina.dorca EN,
@carinadorca.coach DE, YouTube @Cary-redet; Bücher-Accounts thelongexhale.book EN und lieberschatten.buch DE mit
Briefen/Gedichten an ihre Angst). Sie hatte dreimal Burnout und lebt seit Jahren mit Angst.

Plane ihre Woche {days[0]} bis {days[-1]}: {want}. Schwerpunkt/Wunsch: {focus.strip() or "frei, abwechslungsreich"}.
Verteile die Beiträge sinnvoll über die Woche (nicht alles an einem Tag; YouTube eher Mitte der Woche).
Pro Beitrag:
- date: einer dieser Tage: {", ".join(days)}
- type: reel | carousel | youtube | letter | story
- title: der konkrete, leicht polarisierende Hook (max. 12 Wörter) – keine generischen Sprüche
- idea: 2–3 Sätze, was sie sagt/zeigt, mit ihrer persönlichen Erfahrung, und eine Mini-Aufgabe für die Zuschauer
- account: passender Account aus: {", ".join(ACCOUNTS)}
Texte auf {lang} (Bücher-Accounts: Sprache des Accounts). Keine Wiederholung von bereits geplanten Ideen:
{chr(10).join(taken) or "- (noch keine)"}

{meta.GUARDRAILS}

Antworte NUR mit JSON nach dem Schema."""
    got = _ask(prompt, engine)
    if not got:
        raise UserError("Claude did not return a plan. Please try again.")
    for r in got:
        if r.get("date") not in days:
            r["date"] = days[0]
    return add(got)


def extract(text: str, language: str, engine: str = "claude") -> list[dict]:
    """Ideen aus einem Chat-Text (z. B. Claudes Ideenliste) als einzelne Plan-Einträge (noch ohne Datum)."""
    if not text.strip():
        raise UserError("There is no text to take ideas from.")
    prompt = f"""Hier ist ein Text mit Content-Ideen für Carina Dorca (Stress- & Burnout-Prävention):

{text.strip()[:8000]}

Mache daraus einzelne Plan-Einträge – eine Idee = ein Eintrag. date immer "" (noch ohne Tag).
type: reel | carousel | youtube | letter | story (aus dem Text ableiten). title = der Hook genau so wie im Text
(ohne Nummer, ohne Sternchen). idea = 1–3 Sätze aus dem Text. account = passender Account aus: {", ".join(ACCOUNTS)}
(oder ""). Erfinde keine neuen Ideen. Sprache: {"Deutsch" if language == "de" else "wie im Text"}.
Antworte NUR mit JSON nach dem Schema."""
    got = _ask(prompt, engine)
    if not got:
        raise UserError("No ideas were found in this text.")
    for r in got:
        r["date"] = ""
    return add(got)
