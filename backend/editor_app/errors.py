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
        return "The hard drive is full. Please delete old projects or files and try again."
    if "cuda" in low or "cudnn" in low or "cublas" in low:
        return ("The graphics card could not be used. The app uses the processor instead "
                "(slower, but it works). Technical details: " + text)
    if "out of memory" in low or "memoryerror" in low:
        return ("Not enough memory. Choose a smaller speech recognition model in the settings "
                "(e.g. 'small') and close other programs.")
    if "huggingface" in low or "connection" in low or "max retries" in low or "timed out" in low:
        return ("The speech recognition model could not be downloaded. Please check your "
                "internet connection. (Only needed the very first time.)")
    if "invalid data found" in low or "moov atom not found" in low:
        return "The video file is damaged or incomplete. Please upload it again."
    if "ffmpeg" in low and ("not found" in low or "no such file" in low):
        return "The program ffmpeg is missing. Please start the app with 'start.bat', it installs it automatically."
    return "Unexpected error. Please send this message to Claude: " + text
