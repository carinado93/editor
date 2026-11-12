"""Animationen für YouTube-Videos im Stil von Carinas eigenem Schnitt (Video "1108"):

- label   : lila Kasten, weiße Großbuchstaben (Poppins ExtraBold)      – Kernaussage, SEO-Wort ("I QUIT MY STABLE JOB")
- sticker : weiße Zettel mit Handschrift, erscheinen nacheinander     – Aufzählungen ("MANY YEARS: TEAM LEAD")
- check   : Checkliste mit Kästchen, Punkt für Punkt                  – Listen, Tipps, Schritte
- quote   : cremefarbene Pille, Cormorant, *Wort* lila-kursiv        – ruhiger Merksatz ("you still *choose yourself*")
- number  : Wort + große Zahl ("BURNOUT ×3")                           – Zahlen, Wiederholungen
- name    : Name + Titel als Bauchbinde                                – wenn Carina sich vorstellt

Claude bekommt das geschnittene Transkript mit Wort-Nummern und sagt, wann was erscheint. Die Zeiten
werden in Original-Zeit gespeichert (wie alle Schnitte) und beim Rendern in die neue Zeit umgerechnet.
"""
from __future__ import annotations

import re
import time

from . import cuts, meta
from .errors import UserError
from .subtitles import BRAUN, CREME, LILA, LILA_TIEF, _esc, _esc_keep_stars, _fmt_ass, ass_color

STYLES = ("label", "sticker", "check", "quote", "number", "name")
GELB = "#F2C14E"
GRUEN = "#5E8C4A"
WEISS = "#FFFFFF"

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "style": {"type": "string", "enum": list(STYLES)},
                    "word": {"type": "integer", "description": "Nummer des Worts, bei dem es erscheint"},
                    "text": {"type": "string"},
                    "number": {"type": "string", "description": "nur bei style=number, z. B. ×3"},
                    "list": {
                        "type": "array",
                        "description": "nur bei sticker/check: die Punkte, je mit dem Wort, bei dem er erscheint",
                        "items": {"type": "object",
                                  "properties": {"word": {"type": "integer"}, "text": {"type": "string"}},
                                  "required": ["word", "text"], "additionalProperties": False},
                    },
                },
                "required": ["style", "word", "text", "number", "list"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def numbered_sentences(words: list[dict], flags: list) -> str:
    """Behaltene Wörter als Sätze, jeder mit Zeit (neue Zeit) und Wort-Nummern: "[12]Burnout [13]ist …"."""
    out, cur, t_new, last_e = [], [], 0.0, None
    for k, w in enumerate(words):
        if flags and flags[k]:
            continue
        if last_e is not None:
            t_new += max(0.0, min(w["s"] - last_e, 0.4))
        if not cur:
            cur.append(f"({int(t_new // 60)}:{int(t_new % 60):02d})")
        cur.append(f"[{k}]{w['w']}")
        t_new += w["e"] - w["s"]
        last_e = w["e"]
        if cuts.ends_sentence(w["w"]) and len(cur) > 3:
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return "\n".join(out)


def build_prompt(words: list[dict], flags: list, language: str) -> str:
    lang = "Deutsch" if language == "de" else "Englisch"
    return f"""Du bist Video-Editorin für Carina Dorca (YouTube @Cary-redet, Stress- und Burnout-Prävention).
Plane die Text-Animationen für ihr fertig geschnittenes YouTube-Video – genau so, wie sie selbst schneidet.

So schneidet Carina (aus ihrem eigenen Video):
- Animationen kommen OFT, immer wenn es passt: ungefähr alle 8–20 Sekunden, am Anfang dichter.
- SEO-/Kernwörter wie Burnout, Stress, Angst/Anxiety, Erschöpfung, Grenzen, Prävention, Nervensystem bekommen fast
  immer eine Einblendung, wenn sie zum ersten Mal oder betont fallen.
- Sobald sie etwas aufzählt (Gründe, Schritte, Dinge, "erstens/zweitens", "A, B und C"), erscheint eine Liste:
  style "sticker" (Handschrift-Zettel) oder "check" (Checkliste) – jeder Punkt genau in dem Moment, in dem sie ihn sagt.
- Zahlen und Wiederholungen ("dreimal Burnout", "2 Produkte", "7 Tage") → style "number" (text = Wort, number = "×3", "2", "7 TAGE").
- Starke Kernaussagen, Wendepunkte → style "label" (max. 5 Wörter, Großbuchstaben, z. B. "ICH HABE GEKÜNDIGT").
- Ruhige Merksätze, Gefühle, Erkenntnisse → style "quote" (max. 7 Wörter, ein *Wort* in Sternchen wird lila-kursiv).
- Wenn sie sich vorstellt ("ich bin Carina …") → einmal style "name" (text = "Carina Dorca|Stress- & Burnout-Coach"
  bzw. auf Englisch "Carina Dorca|Stress & Burnout Coach").
- Texte kurz, konkret, in ihren Worten, auf {lang}. Keine Heilversprechen, keine Diagnosen.
- Nie zwei Einblendungen gleichzeitig: mindestens 4 Sekunden zwischen den Startpunkten (Listen zählen als eine).
- "word" = Nummer in eckigen Klammern des LETZTEN Worts der Stelle, die die Einblendung zeigt. Die Einblendung
  erscheint erst, wenn Carina dieses Wort ausgesprochen hat – NIE bevor sie es gesagt hat. Beispiel: Sie sagt
  "[40]Coaching [41]ist [42]Prävention, [43]nicht [44]Behandlung" → Text "COACHING = PRÄVENTION", word = 42.
  Bei Listen gilt das für jeden Punkt einzeln: word = das Wort, mit dem sie den Punkt fertig gesagt hat.
- Für alle Stile außer sticker/check ist "list" leer; "number" ist leer, außer bei style "number".

Transkript (Zeit in Klammern, [Nummer] vor jedem Wort):
{numbered_sentences(words, flags)}

{meta.lang_rule(language)}
Antworte NUR mit JSON nach dem Schema."""


def _duration(style: str, text: str) -> float:
    base = {"label": 2.8, "quote": 3.6, "number": 3.0, "name": 4.5}.get(style, 3.0)
    return base + min(1.5, len(text) / 40)


def _said(w: dict) -> float:
    """Zeitpunkt, an dem das Wort gesagt ist: kurz vor seinem Ende (nie vor dem Wort)."""
    return max(w["s"] + 0.15, w["e"] - 0.1)


def parse(data: dict, words: list[dict], flags: list) -> list[dict]:
    """Claude-Antwort → Animationen mit Original-Zeiten. Unpassendes wird still verworfen."""
    n = len(words)

    def ok(k) -> bool:
        return isinstance(k, int) and 0 <= k < n and not (flags and flags[k])

    out: list[dict] = []
    stamp = int(time.time() * 1000) % 10_000_000
    for i, it in enumerate(data.get("items") or []):
        style = it.get("style")
        text = str(it.get("text") or "").strip()
        k = it.get("word")
        if style not in STYLES or not text or not ok(k):
            continue
        start = _said(words[k])
        item = {"id": f"yt-{stamp}-{i}", "kind": "yt", "style": style, "text": text[:80], "on": True,
                "start": round(start, 2), "number": str(it.get("number") or "").strip()[:12], "list": []}
        if style in ("sticker", "check"):
            pts = [p for p in it.get("list") or [] if ok(p.get("word")) and str(p.get("text") or "").strip()]
            pts.sort(key=lambda p: p["word"])
            item["list"] = [{"text": str(p["text"]).strip()[:48], "t": round(_said(words[p["word"]]), 2)}
                            for p in pts[:6]]
            if not item["list"]:
                item["list"] = [{"text": text[:48], "t": round(start, 2)}]
            item["start"] = min(item["start"], item["list"][0]["t"])
            end = item["list"][-1]["t"] + 2.8
        else:
            end = start + _duration(style, text)
        item["end"] = round(end, 2)
        out.append(item)
    out.sort(key=lambda x: x["start"])
    # Nie zwei gleichzeitig: zu dicht folgende fliegen raus, sonst wird die frühere gekürzt
    kept: list[dict] = []
    for o in out:
        if kept and o["start"] - kept[-1]["start"] < 1.7:
            continue
        if kept and kept[-1]["end"] > o["start"] - 0.2:
            kept[-1]["end"] = round(o["start"] - 0.2, 2)
        kept.append(o)
    return [o for o in kept if o["end"] - o["start"] >= 1.2]


def suggest_claude(transcript: dict, flags: list) -> list[dict]:
    from . import claude
    words = cuts.flat_words(transcript)
    if not words:
        raise UserError("There is no transcript yet.")
    data = claude.ask_json(build_prompt(words, flags, transcript.get("language", "de")), SCHEMA, effort="medium")
    items = parse(data, words, flags)
    if not items:
        raise UserError("Claude did not find any spots for animations. Please try again.")
    return items


def suggest_ollama(transcript: dict, flags: list) -> list[dict]:
    """Kostenlos: die lokale KI bekommt das Video in Stücken von ca. 3 Minuten (sonst sieht sie nur das Ende)."""
    from . import llm
    words = cuts.flat_words(transcript)
    if not words:
        raise UserError("There is no transcript yet.")
    lang = transcript.get("language", "de")
    items: list[dict] = []
    chunk = 450  # Wörter ≈ 3 Minuten
    for a in range(0, len(words), chunk):
        sub_flags = [True] * len(words)
        for k in range(a, min(len(words), a + chunk)):
            sub_flags[k] = flags[k] if flags else None
        prompt = build_prompt(words, sub_flags, lang).replace(
            "Antworte NUR mit JSON nach dem Schema.",
            'Antworte NUR mit JSON: {"items": [{"style": "...", "word": 12, "text": "...", "number": "", "list": []}]}')
        try:
            data = llm.ask_json(prompt, "Du antwortest ausschließlich mit gültigem JSON.", timeout=600)
        except UserError:
            if not items:
                raise
            break
        items.extend(parse(data if isinstance(data, dict) else {}, words, sub_flags))
    if not items:
        raise UserError("The local AI did not find any spots for animations. Please try again or use Claude.")
    items.sort(key=lambda x: x["start"])
    return items


# ---------------------------------------------------------------- Rendern (ASS)

def ass_styles(unit: float) -> list[str]:
    def st(name, font, size, prim, box, bold=0, italic=0, pad=12):
        return (f"Style: {name},{font},{round(size * unit)},{ass_color(prim)},{ass_color(prim)},{ass_color(box)},"
                f"{ass_color('#000000', 0xC8)},{bold},{italic},0,0,100,100,0,0,3,{round(pad * unit)},0,7,0,0,0,1")
    return [
        st("YtLabel", "Poppins ExtraBold", 56, WEISS, LILA, pad=12),
        st("YtSticker", "Caveat", 44, BRAUN, WEISS, bold=-1, pad=10),
        st("YtQuote", "Cormorant Garamond SemiBold", 56, BRAUN, CREME, pad=16),
        st("YtNumber", "Poppins Black", 130, GELB, LILA_TIEF, pad=16),
        st("YtName", "Cormorant Garamond SemiBold", 46, BRAUN, CREME, pad=10),
        st("YtTitle", "Poppins SemiBold", 22, WEISS, LILA, pad=6),
        "Style: YtDraw,Arial,20,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
    ]


def _wrap(text: str, max_chars: int) -> str:
    lines, cur = [], ""
    for w in text.split():
        if cur and len(cur) + 1 + len(w.replace("*", "")) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return "\\N".join(lines)


def _pop(delay_ms: int = 0) -> str:
    d = delay_ms
    return (f"\\fscx60\\fscy60\\t({d},{d + 160},\\fscx106\\fscy106)\\t({d + 160},{d + 260},\\fscx100\\fscy100)"
            f"\\fad(0,220)")


def _accent_on(text: str, base: str) -> str:
    out = []
    for part in re.split(r"(\*[^*]+\*)", _esc_keep_stars(text)):
        if part.startswith("*") and part.endswith("*") and len(part) > 2:
            out.append(f"{{\\fnCormorant Garamond SemiBold\\i1\\c{ass_color(LILA)}}}{part[1:-1]}{{\\i0\\c{ass_color(base)}}}")
        elif part:
            out.append(part)
    return "".join(out)


def ass_events(items: list[dict], tmap, width: int, height: int, face_box: list[float] | None) -> list[str]:
    """Dialogue-Zeilen für alle eingeschalteten YouTube-Animationen (Zeiten → neue Zeit)."""
    unit = height / 1080
    fx0, fy0, fx1, fy1 = face_box or [0.38, 0.12, 0.62, 0.48]
    face_cx = (fx0 + fx1) / 2
    right = face_cx < 0.55  # neben dem Gesicht auf der freieren Seite
    side_x = round(width * min(0.80, fx1 + 0.05)) if right else round(width * max(0.20, fx0 - 0.05))
    side_an = 7 if right else 9
    side_y = round(height * max(0.18, (fy0 + fy1) / 2))
    chest_x = round(width * face_cx)
    chest_y = round(height * min(0.80, max(0.56, fy1 + 0.26)))
    ev: list[str] = []
    for it in items:
        if not it.get("on", True):
            continue
        s, e = tmap.clamp(it["start"]), tmap.clamp(it["end"])
        if e - s < 0.5:
            continue
        S, E = _fmt_ass(s), _fmt_ass(e)
        style = it.get("style", "label")
        if style == "label":
            body = _esc(_wrap(it["text"].upper(), 18))
            ev.append(f"Dialogue: 3,{S},{E},YtLabel,,0,0,0,,{{\\an8\\pos({chest_x},{chest_y}){_pop()}}}{body}")
        elif style == "quote":
            body = _accent_on(_wrap(it["text"], 30), BRAUN)
            ev.append(f"Dialogue: 3,{S},{E},YtQuote,,0,0,0,,{{\\an8\\pos({chest_x},{chest_y}){_pop()}}}{body}")
        elif style == "number":
            ev.append(f"Dialogue: 3,{S},{E},YtLabel,,0,0,0,,{{\\an{side_an}\\pos({side_x},{side_y}){_pop()}}}"
                      f"{_esc(it['text'].upper())}")
            ny = side_y + round(86 * unit)
            ev.append(f"Dialogue: 3,{S},{E},YtNumber,,0,0,0,,{{\\an{side_an}\\pos({side_x},{ny}){_pop(180)}}}"
                      f"{_esc(it.get('number') or '')}")
        elif style == "name":
            name, _, title = it["text"].partition("|")
            ev.append(f"Dialogue: 3,{S},{E},YtName,,0,0,0,,{{\\an{side_an}\\pos({side_x},{side_y}){_pop()}}}"
                      f"{_esc(name.strip())}")
            if title.strip():
                ty = side_y + round(66 * unit)
                ev.append(f"Dialogue: 3,{S},{E},YtTitle,,0,0,0,,{{\\an{side_an}\\pos({side_x},{ty}){_pop(150)}}}"
                          f"{_esc(title.strip())}")
        else:  # sticker / check: Punkte erscheinen nacheinander untereinander
            step = round(68 * unit)
            box = round(30 * unit)
            for n, p in enumerate(it.get("list") or []):
                ps = max(s, tmap.clamp(p["t"]))
                if e - ps < 0.4:
                    continue
                y = side_y + n * step
                rot = -2 if n % 2 == 0 else 1.5
                x = side_x
                if style == "check":
                    # Kästchen (weiß, lila Rand) links vom Text, Haken erscheint kurz danach
                    bx = x if right else x - box
                    tx = x + box + round(14 * unit) if right else x - box - round(14 * unit)
                    sq = f"m 0 0 l {box} 0 {box} {box} 0 {box}"
                    ev.append(f"Dialogue: 4,{_fmt_ass(ps)},{E},YtDraw,,0,0,0,,{{\\an7\\pos({bx},{y + round(6 * unit)})"
                              f"\\bord{max(1, round(3 * unit))}\\3c{ass_color(LILA)}\\c{ass_color(WEISS)}\\fad(150,220)\\p1}}{sq}")
                    tk = (f"m {round(box * 0.18)} {round(box * 0.52)} l {round(box * 0.42)} {round(box * 0.78)} "
                          f"{round(box * 0.86)} {round(box * 0.2)} {round(box * 0.94)} {round(box * 0.3)} "
                          f"{round(box * 0.42)} {round(box * 0.95)} {round(box * 0.1)} {round(box * 0.6)}")
                    ev.append(f"Dialogue: 5,{_fmt_ass(ps + 0.35)},{E},YtDraw,,0,0,0,,{{\\an7\\pos({bx},{y + round(6 * unit)})"
                              f"\\c{ass_color(GRUEN)}\\fad(120,220)\\p1}}{tk}")
                    x = tx
                ev.append(f"Dialogue: 4,{_fmt_ass(ps)},{E},YtSticker,,0,0,0,,{{\\an{side_an}\\pos({x},{y})"
                          f"\\frz{rot}{_pop()}}}{_esc(p['text'].upper() if style == 'sticker' else p['text'])}")
    return ev
