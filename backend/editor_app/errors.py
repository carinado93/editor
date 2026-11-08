"""Verständliche deutsche Fehlermeldungen."""
from __future__ import annotations


class UserError(Exception):
    """Ein Fehler, dessen Text direkt in der App angezeigt wird."""


def explain(exc: BaseException) -> str:
    """Macht aus einer technischen Fehlermeldung einen Satz, den man versteht."""
    if isinstance(exc, UserError):
        return str(exc)
    text = f"{type(exc).__name__}: {exc}"
    low = text.lower()
    if "no space left" in low or "errno 28" in low:
        return "Die Festplatte ist voll. Bitte lösche alte Projekte oder Dateien und versuche es nochmal."
    if "cuda" in low or "cudnn" in low or "cublas" in low:
        return ("Die Grafikkarte konnte nicht benutzt werden. Die App rechnet stattdessen mit dem Prozessor "
                "(langsamer, aber es funktioniert). Technisch: " + text)
    if "out of memory" in low or "memoryerror" in low:
        return ("Zu wenig Arbeitsspeicher. Wähle in den Einstellungen ein kleineres Spracherkennungs-Modell "
                "(z. B. 'small') und schließe andere Programme.")
    if "huggingface" in low or "connection" in low or "max retries" in low or "timed out" in low:
        return ("Das Spracherkennungs-Modell konnte nicht heruntergeladen werden. Bitte prüfe die "
                "Internetverbindung. (Nur beim allerersten Mal nötig.)")
    if "invalid data found" in low or "moov atom not found" in low:
        return "Die Videodatei ist beschädigt oder unvollständig. Bitte lade sie nochmal hoch."
    if "ffmpeg" in low and ("not found" in low or "no such file" in low):
        return "Das Programm ffmpeg fehlt. Bitte starte die App mit 'start.bat', das installiert es automatisch."
    return "Unerwarteter Fehler. Bitte schick Claude diese Meldung: " + text
