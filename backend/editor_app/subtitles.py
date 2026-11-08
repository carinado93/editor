"""Untertitel (SRT + eingebrannt) und Buzzword-Animationen (ASS/libass), im Stil von Carinas Marke.

Alle Zeiten werden von der Original-Zeit in die neue (geschnittene) Zeit umgerechnet.
"""
from __future__ import annotations

import bisect
import re

# Markenfarben (#RRGGBB)
CREME = "#F4EEE4"
BRAUN = "#4A3A30"
FLIEDER = "#CDBFE0"
LILA = "#6A4C9C"
LILA_TIEF = "#3A2862"


def ass_color(hex_: str, alpha: int = 0) -> str:
    """#RRGGBB → &HAABBGGRR (ASS-Format, alpha 0 = deckend)."""
    h = hex_.lstrip("#")
    return f"&H{alpha:02X}{h[4:6]}{h[2:4]}{h[0:2]}".upper()


class TimeMap:
    """Rechnet Original-Zeit → neue Zeit um (aus den behaltenen Bereichen)."""

    def __init__(self, keep: list[tuple[float, float]]):
        self.starts = [a for a, _ in keep]
        self.keep = keep
        self.offsets = []
        acc = 0.0
        for a, b in keep:
            self.offsets.append(acc)
            acc += b - a
        self.total = acc

    def __call__(self, t: float) -> float | None:
        k = bisect.bisect_right(self.starts, t) - 1
        if k < 0:
            return None
        a, b = self.keep[k]
        if t > b:
            return None
        return self.offsets[k] + (t - a)

    def clamp(self, t: float) -> float:
        """Wie __call__, aber Zeiten in geschnittenen Bereichen springen an den nächsten Anfang."""
        k = bisect.bisect_right(self.starts, t) - 1
        if k < 0:
            return 0.0
        a, b = self.keep[k]
        return self.offsets[k] + (min(t, b) - a)


def kept_words(words: list[dict], flags: list, tmap: TimeMap) -> list[dict]:
    out = []
    for k, (w, f) in enumerate(zip(words, flags)):
        if f:
            continue
        s, e = tmap.clamp(w["s"]), tmap.clamp(w["e"])
        if e <= s:
            e = s + 0.05
        out.append({"i": k, "w": w["w"], "s": s, "e": e})
    return out


def lines(words: list[dict], max_chars: int = 32, max_gap: float = 1.0) -> list[list[dict]]:
    """Wörter zu Untertitel-Zeilen gruppieren (kurz, gut lesbar, Umbruch an Satzenden)."""
    out: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        text = " ".join(x["w"] for x in cur + [w])
        if cur and (len(text) > max_chars or w["s"] - cur[-1]["e"] > max_gap):
            out.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.!?…]$", w["w"]) or (re.search(r"[,;:]$", w["w"]) and len(text) > max_chars * 0.6):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    # Kurze Reste ("giveaway.") nicht allein aufblitzen lassen, sondern an die Zeile davor hängen
    merged: list[list[dict]] = []
    for g in out:
        if merged and len(g) <= 2 and g[-1]["e"] - g[0]["s"] < 0.8 and g[0]["s"] - merged[-1][-1]["e"] < 0.5 \
                and len(" ".join(x["w"] for x in merged[-1] + g)) <= max_chars * 1.35:
            merged[-1] = merged[-1] + g
        else:
            merged.append(g)
    return merged


def _fmt_srt(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def srt(groups: list[list[dict]]) -> str:
    out = []
    for n, g in enumerate(groups, 1):
        end = g[-1]["e"] + 0.15
        if n < len(groups):
            end = min(end, groups[n][0]["s"])
        out.append(f"{n}\n{_fmt_srt(g[0]['s'])} --> {_fmt_srt(end)}\n{' '.join(w['w'] for w in g)}\n")
    return "\n".join(out)


def _fmt_ass(t: float) -> str:
    cs = int(round(max(0.0, t) * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _esc(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")")


def ass(width: int, height: int, groups: list[list[dict]] | None, buzz: list[dict], face_box: list[float] | None,
        karaoke: bool = False) -> str:
    """ASS-Datei mit Untertiteln und Buzzword-Pops.

    Platzierung: Hochformat → Untertitel bei ~70 % Höhe (Instagram/Shorts-Safe-Zone endet bei ~1250/1920),
    Buzzwords knapp unter dem Gesicht. Querformat → Untertitel unten, Buzzwords neben dem Gesicht.
    """
    portrait = height > width
    unit = min(width, height) / 1080
    sub_size = round((54 if portrait else 46) * unit)
    buzz_size = round((96 if portrait else 84) * unit)
    fx0, fy0, fx1, fy1 = face_box or [0.3, 0.1, 0.7, 0.5]

    if portrait:
        sub_y = round(height * 0.70)
        buzz_y = round(height * min(0.62, max(fy1 + 0.04, 0.50)))
        buzz_x = width // 2
    else:
        sub_y = round(height * 0.90)
        face_cx = (fx0 + fx1) / 2
        buzz_x = round(width * (0.76 if face_cx < 0.5 else 0.24))
        buzz_y = round(height * 0.42)

    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Untertitel,Poppins SemiBold,{sub_size},{ass_color(LILA if karaoke else BRAUN)},{ass_color(BRAUN)},{ass_color(CREME, 0x18)},{ass_color("#000000", 0xB0)},0,0,0,0,100,100,0,0,3,{round(14 * unit)},0,5,40,40,0,1
Style: Buzz,Cormorant Garamond Bold,{buzz_size},{ass_color(LILA_TIEF)},{ass_color(LILA_TIEF)},{ass_color(FLIEDER, 0x10)},{ass_color("#000000", 0xA0)},-1,0,0,0,100,100,1,0,3,{round(20 * unit)},0,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    for n, g in enumerate(groups or []):
        start = g[0]["s"]
        end = g[-1]["e"] + 0.15
        if groups and n + 1 < len(groups):
            end = min(end, groups[n + 1][0]["s"])
        if karaoke:
            parts, t = [], start
            for w in g:
                dur = max(1, int(round((w["e"] - t) * 100)))
                parts.append(f"{{\\k{dur}}}{_esc(w['w'])} ")
                t = w["e"]
            text = "".join(parts).strip()
        else:
            text = _esc(" ".join(w["w"] for w in g))
        ev.append(f"Dialogue: 0,{_fmt_ass(start)},{_fmt_ass(end)},Untertitel,,0,0,0,,{{\\pos({width // 2},{sub_y})}}{text}")

    for b in buzz:
        text = _esc(b["text"]).upper() if b.get("upper") else _esc(b["text"])
        pop = "{\\fscx40\\fscy40\\t(0,160,\\fscx112\\fscy112)\\t(160,260,\\fscx100\\fscy100)\\fad(0,220)}"
        ev.append(f"Dialogue: 1,{_fmt_ass(b['s'])},{_fmt_ass(b['e'])},Buzz,,0,0,0,,{{\\pos({buzz_x},{buzz_y})}}{pop}{text}")
    return head + "\n".join(ev) + "\n"


def buzz_events(buzzwords: list[dict], words: list[dict], tmap: TimeMap, min_show: float = 1.8) -> list[dict]:
    """Buzzwords (Wort-Bereiche) → Einblendungen in neuer Zeit. Mindestens `min_show` Sekunden sichtbar."""
    out = []
    for b in sorted(buzzwords, key=lambda x: x["start"]):
        s = tmap.clamp(words[b["start"]]["s"])
        e = max(s + min_show, tmap.clamp(words[b["end"] - 1]["e"]) + 0.8)
        text = b.get("text") or " ".join(re.sub(r"[.,!?;:…]+$", "", w["w"]) for w in words[b["start"]:b["end"]])
        if out and s < out[-1]["e"]:
            out[-1]["e"] = s  # nie zwei Buzzwords gleichzeitig
        out.append({"s": s, "e": min(e, tmap.total), "text": text})
    return [b for b in out if b["e"] - b["s"] > 0.3]
