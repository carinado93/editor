"""Claude über die offizielle Schnittstelle (API): ein Klick, beste Texte.

- Der Schlüssel steht nur auf Carinas PC in der Datei `.env` (nie im Code, nicht im Git).
- Kosten: nur was genutzt wird (Guthaben auf console.anthropic.com), ca. 0,05–0,10 $ pro Reel-Text.
- Modell: Claude Opus 5.5 (beste Qualität). Antworten im festen JSON-Format, damit die App sie direkt übernimmt.
- Falls Claude eine Anfrage aus Sicherheitsgründen ablehnt, übernimmt automatisch ein anderes Claude-Modell
  ("fallbacks": "default").
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .config import ROOT
from .errors import UserError

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
ENV_FILE = ROOT / ".env"
KEY_NAME = "ANTHROPIC_API_KEY"


# ---------- Schlüssel ----------

def _read_env_file() -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def load_key() -> str:
    key = _read_env_file().get(KEY_NAME) or os.environ.get(KEY_NAME, "")
    if key:
        os.environ[KEY_NAME] = key
    return key


def masked() -> str:
    k = load_key()
    return f"{k[:10]}…{k[-4:]}" if len(k) > 16 else ""


def save_key(key: str) -> None:
    key = key.strip()
    if not re.fullmatch(r"sk-ant-[A-Za-z0-9_\-]{20,}", key):
        raise UserError("Das sieht nicht wie ein Claude-Schlüssel aus. Er beginnt mit „sk-ant-“. "
                        "Bitte den ganzen Schlüssel aus console.anthropic.com kopieren.")
    _check(key)
    lines = [ln for ln in (ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else [])
             if not ln.startswith(KEY_NAME + "=")]
    lines.append(f"{KEY_NAME}={key}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ[KEY_NAME] = key


def delete_key() -> None:
    if ENV_FILE.exists():
        lines = [ln for ln in ENV_FILE.read_text(encoding="utf-8").splitlines() if not ln.startswith(KEY_NAME + "=")]
        ENV_FILE.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    os.environ.pop(KEY_NAME, None)


def available() -> bool:
    return bool(load_key())


# ---------- Aufrufe ----------

def _client(key: str | None = None):
    import anthropic

    k = key or load_key()
    if not k:
        raise UserError("Für Claude fehlt noch der Schlüssel. Bitte oben unter „Einstellungen“ eintragen.")
    return anthropic.Anthropic(api_key=k, timeout=180, max_retries=2)


def _explain(exc: Exception) -> UserError:
    import anthropic

    if isinstance(exc, anthropic.AuthenticationError):
        return UserError("Der Claude-Schlüssel stimmt nicht (mehr). Bitte unter „Einstellungen“ neu eintragen.")
    if isinstance(exc, anthropic.PermissionDeniedError):
        return UserError("Der Schlüssel darf das nicht. Bitte auf console.anthropic.com prüfen.")
    if isinstance(exc, anthropic.RateLimitError):
        return UserError("Claude ist gerade ausgelastet. Bitte in einer Minute nochmal versuchen.")
    if isinstance(exc, anthropic.BadRequestError):
        msg = str(getattr(exc, "message", exc))
        if "credit" in msg.lower() or "balance" in msg.lower():
            return UserError("Das Guthaben für Claude ist aufgebraucht. Bitte auf console.anthropic.com → Billing "
                             "aufladen (z. B. 10 $).")
        return UserError("Claude konnte die Anfrage nicht bearbeiten: " + msg[:200])
    if isinstance(exc, anthropic.APIConnectionError):
        return UserError("Keine Verbindung zu Claude. Bitte Internet prüfen.")
    if isinstance(exc, anthropic.APIStatusError):
        return UserError(f"Claude hat einen Fehler gemeldet ({exc.status_code}). Bitte nochmal versuchen.")
    return UserError("Claude hat nicht geantwortet: " + str(exc)[:200])


def _check(key: str) -> None:
    """Schlüssel mit einer winzigen Anfrage prüfen (kostet weniger als 0,001 $)."""
    try:
        _client(key).messages.create(model=MODEL, max_tokens=16, messages=[{"role": "user", "content": "Hi"}],
                                     output_config={"effort": "low"})
    except Exception as exc:  # noqa: BLE001
        raise _explain(exc) from exc


def _create(**kwargs):
    """Anfrage mit automatischem Ausweichen auf ein anderes Modell, falls Claude ablehnt."""
    import anthropic

    client = _client()
    try:
        return client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
    except anthropic.BadRequestError as exc:
        if "fallback" in str(exc).lower():  # Ausweich-Funktion nicht verfügbar → normal anfragen
            try:
                return client.messages.create(**kwargs)
            except Exception as exc2:  # noqa: BLE001
                raise _explain(exc2) from exc2
        raise _explain(exc) from exc
    except Exception as exc:  # noqa: BLE001
        raise _explain(exc) from exc


def _text(resp) -> str:
    if getattr(resp, "stop_reason", "") == "refusal":
        raise UserError("Claude wollte diese Anfrage nicht bearbeiten. Bitte die Idee etwas anders formulieren.")
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


def ask_json(prompt: str, schema: dict, system: str = "", effort: str = "medium") -> dict:
    resp = _create(model=MODEL, max_tokens=16000, system=system or "Du antwortest ausschließlich im verlangten JSON.",
                   messages=[{"role": "user", "content": prompt}],
                   output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}})
    text = _text(resp)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise UserError("Claude hat keine passende Antwort geliefert. Bitte nochmal versuchen.")


def chat(messages: list[dict], system: str) -> str:
    clean = [{"role": m["role"], "content": str(m["content"])} for m in messages
             if m.get("role") in ("user", "assistant") and str(m.get("content", "")).strip()]
    if not clean or clean[-1]["role"] != "user":
        raise UserError("Bitte zuerst eine Nachricht schreiben.")
    resp = _create(model=MODEL, max_tokens=8000, system=system, messages=clean, output_config={"effort": "medium"})
    return _text(resp)


# ---------- Antwort-Formate ----------

def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or list(props), "additionalProperties": False}


_STR = {"type": "string"}
_STRS = {"type": "array", "items": {"type": "string"}}

REEL_SCHEMA = _obj({"scenes": _STRS, "caption": _STR, "hashtags": _STRS, "cover_text": _STR, "shorts_title": _STR})
YOUTUBE_SCHEMA = _obj({"titles": _STRS, "chapters": {"type": "array", "items": _obj({"time": _STR, "title": _STR})},
                       "description": _STR, "tags": _STRS, "hashtags": _STRS})


def chat_system(language: str = "en") -> str:
    from . import meta

    style = ""
    for name in ("KARUSSELL_STIL.md", "THUMBNAIL_STIL.md"):
        p = ROOT / "docs" / name
        if p.exists():
            style += "\n\n" + p.read_text(encoding="utf-8")[:6000]
    return (f"Du bist die Social-Media-Partnerin von Carina Dorca, Stress- und Burnout-Coachin "
            f"(Instagram @carina.dorca auf Englisch, @carinadorca.coach auf Deutsch, YouTube @Cary-redet). "
            f"Du hilfst bei Ideen, Hooks, Reel-Skripten, Captions, Karussell-Texten und YouTube-Texten. "
            f"Antworte in der Sprache, in der Carina schreibt, kurz und konkret, in ihrer warmen, direkten Stimme. "
            f"Hashtags immer genau 5. Bei Skripten: erst Vorschlag, dann Carinas Freigabe.\n\n{meta.GUARDRAILS}"
            f"\n\nCarinas Gestaltungs-Stil (zur Orientierung):{style}")
