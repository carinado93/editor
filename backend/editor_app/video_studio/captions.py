"""Automatische Untertitel für Video Studio (Schritt 7): Whisper-Spracherkennung → ASS (eingebrannt) + .srt.

Stile: clean (weiß, Schatten), bold (groß, Großbuchstaben), karaoke (Wort für Wort hervorgehoben, Lila),
boxed (dunkle Box). Füllwörter (äh, ähm, uh, um …) können weggelassen werden.
Braucht Ton: "Keep original sound" muss an sein (Drohnenclips haben meist keinen Ton).
"""
from __future__ import annotations

import re
from pathlib import Path

from .. import media, subtitles, transcribe
from ..config import ROOT

STYLES = {"clean": "Clean (white)", "bold": "Bold (big caps)", "karaoke": "Word by word (lilac highlight)",
          "boxed": "Boxed"}
FILLERS = {"äh", "ähm", "öhm", "hm", "hmm", "uh", "um", "uhm", "erm", "eh"}


def words_from(transcript: dict, drop_fillers: bool = True) -> list[dict]:
    out = []
    for seg in transcript.get("segments", []):
        for w in seg.get("words", []):
            t = w.get("w", "").strip()
            if not t:
                continue
            if drop_fillers and re.sub(r"[^\wäöü]", "", t.lower()) in FILLERS:
                continue
            out.append({"w": t, "s": float(w["s"]), "e": float(w["e"])})
    return out


def _t(x: float) -> str:
    h, r = divmod(max(0.0, x), 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def ass(words: list[dict], W: int, H: int, style: str = "clean") -> str:
    vertical = H > W
    size = int(min(W, H) * (0.075 if style == "bold" else 0.058))
    margin_v = int(H * (0.22 if vertical else 0.08))
    font = "Poppins ExtraBold" if style == "bold" else "Poppins SemiBold"
    border = 3 if style == "boxed" else 1
    outline = max(2, size // 14) if style != "boxed" else max(4, size // 6)
    back = "&H80000000" if style == "boxed" else "&H64000000"
    primary = "&H00FFFFFF"
    secondary = "&H00E09CB7" if style == "karaoke" else "&H00FFFFFF"   # Lila #B79CE0 (BGR)
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\nWrapStyle: 0\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
            "MarginR, MarginV, Encoding\n"
            f"Style: Cap,{font},{size},{primary if style != 'karaoke' else secondary},{primary},&H96000000,{back},0,0,0,0,"
            f"100,100,0,0,{border},{outline},1,2,{int(W * 0.06)},{int(W * 0.06)},{margin_v},1\n\n[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    lines = []
    for g in subtitles.lines(words, max_chars=26 if vertical else 40):
        a, b = g[0]["s"], g[-1]["e"] + 0.15
        if style == "karaoke":
            text = "".join(f"{{\\kf{max(1, int((w['e'] - w['s']) * 100))}}}{w['w']} " for w in g).strip()
        else:
            text = " ".join(w["w"] for w in g)
            if style == "bold":
                text = text.upper()
        lines.append(f"Dialogue: 0,{_t(a)},{_t(b)},Cap,,0,0,0,,{text}")
    return head + "\n".join(lines) + "\n"


def make(audio_src: Path, work: Path, W: int, H: int, style: str = "clean", language: str = "auto",
         drop_fillers: bool = True) -> tuple[Path, Path, int] | None:
    """Ton → Untertitel. Gibt (ass, srt, Anzahl Wörter) zurück oder None, wenn nichts gesprochen wird."""
    work.mkdir(parents=True, exist_ok=True)
    wav = work / "speech.wav"
    media._run_with_progress(["-i", str(audio_src), "-vn", "-ac", "1", "-ar", "16000", str(wav)], 1.0, None)
    tr = transcribe.transcribe(wav, work / "asr", "auto", language)
    words = words_from(tr, drop_fillers)
    if not words:
        return None
    a = work / f"captions_{style}.ass"
    a.write_text(ass(words, W, H, style), encoding="utf-8")
    s = work / "captions.srt"
    s.write_text(subtitles.srt(subtitles.lines(words, max_chars=40)), encoding="utf-8")
    return a, s, len(words)


def ffmpeg_filter(ass_file: Path) -> str:
    def esc(p: Path) -> str:
        return str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    return f"subtitles=filename='{esc(ass_file)}':fontsdir='{esc(ROOT / 'assets' / 'fonts')}'"
