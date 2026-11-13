"""Runde 2: Retake-Ketten, Aufzählungen, Nachhören, YouTube-Animationen."""
from editor_app import animations, cuts, relisten, subtitles


def _t(text: str, gaps: dict[int, float] | None = None, lang: str = "de") -> dict:
    words, t = [], 0.0
    for k, w in enumerate(text.split()):
        t += (gaps or {}).get(k, 0.05)
        words.append({"w": w, "s": round(t, 2), "e": round(t + 0.3, 2), "p": 0.9})
        t += 0.3
    return {"language": lang, "duration": t + 1, "segments": [{"s": 0, "e": t, "text": text, "words": words}]}


def _kept(t: dict) -> str:
    cl = cuts.build(t, cuts.default_settings(t["language"]))
    ev = cuts.evaluate(t, cl)
    return " ".join(w["w"] for w, f in zip(cuts.flat_words(t), ev["flags"]) if not f)


def test_several_attempts_only_last_stays():
    t = _t("Mein Lehrgang war stattlich zugelassen und von CFU. Mein Lehrgang war stattlich geprüft und von CFU. "
           "Mein Lehrgang war stattlich geprüft. Mein Lehrgang war stattlich geprüft und von CFU zugelassen. Danke.")
    assert _kept(t) == "Mein Lehrgang war stattlich geprüft und von CFU zugelassen. Danke."


def test_deliberate_list_is_not_cut():
    t = _t("Ich darf keine Diagnose stellen. Ich darf dir nicht sagen, du hast Depressionen, du hast Angst, "
           "du hast irgendwas.")
    assert _kept(t).startswith("Ich darf keine Diagnose stellen. Ich darf dir nicht sagen, du hast Depressionen, du hast Angst")


def test_restart_after_filler_is_cut():
    t = _t("zwei Bachelor, ein Master of, ähm, Master of Science. Dann")
    assert _kept(t) == "zwei Bachelor, ein Master of Science. Dann"


def test_splice_inserts_hidden_attempts():
    orig = [{"w": "Mein", "s": 109.0, "e": 109.5, "p": 0.9}, {"w": "Lehrgang", "s": 109.5, "e": 114.5, "p": 0.9},
            {"w": "war", "s": 114.6, "e": 114.9, "p": 0.9}]
    new = [("Mein", 109.0), ("Lehrgang", 109.54), ("war,", 109.9), ("mein", 110.08), ("Lehrgang", 110.52),
           ("war", 110.96), ("äh,", 111.82), ("nein,", 113.66), ("mein", 114.08), ("Lehrgang", 114.2), ("war.", 114.64)]
    new = [{"w": w, "s": s, "e": round(s + 0.3, 2), "p": 0.9} for w, s in new]
    out = relisten.splice(orig, new)
    assert out is not None
    assert [w["w"] for w in out][:4] == ["Mein", "Lehrgang", "war,", "mein"]
    assert out[1]["e"] < 110  # das 5-Sekunden-Wort ist jetzt kurz
    assert sum(1 for w in out if w.get("neu")) == 8


def test_splice_rejects_different_words():
    orig = [{"w": "ich", "s": 1.0, "e": 1.2, "p": 0.9}, {"w": "wollte", "s": 1.2, "e": 2.5, "p": 0.9},
            {"w": "die", "s": 2.6, "e": 2.8, "p": 0.9}]
    new = [{"w": "Gut", "s": 1.0, "e": 1.3, "p": 0.9}, {"w": "kauf", "s": 1.3, "e": 1.6, "p": 0.9}]
    assert relisten.splice(orig, new) is None


def test_animation_parse_and_render():
    t = _t("Ich bin Carina. Ich hatte dreimal Burnout. Erstens Schlaf, zweitens Pausen, drittens Grenzen.", {3: 4.0, 8: 3.0})
    words = cuts.flat_words(t)
    flags = [None] * len(words)
    data = {"items": [
        {"style": "name", "word": 0, "text": "Carina Dorca|Stress- & Burnout-Coach", "number": "", "list": []},
        {"style": "number", "word": 6, "text": "Burnout", "number": "×3", "list": []},
        {"style": "check", "word": 8, "text": "Drei Dinge", "number": "",
         "list": [{"word": 8, "text": "Schlaf"}, {"word": 10, "text": "Pausen"}, {"word": 12, "text": "Grenzen"}]},
        {"style": "label", "word": 999, "text": "falsch", "number": "", "list": []},
    ]}
    items = animations.parse(data, words, flags)
    assert [i["style"] for i in items] == ["name", "number", "check"]
    assert len(items[2]["list"]) == 3
    assert all(a["end"] <= b["start"] for a, b in zip(items, items[1:]))
    ev = animations.ass_events(items, subtitles.TimeMap([(0, 100)]), 1920, 1080, None)
    assert any("YtNumber" in e and "×3" in e for e in ev)
    assert sum("YtSticker" in e for e in ev) == 3
    assert "[7]Erstens" in animations.numbered_sentences(words, flags)


def test_own_reel_from_selection_rounds_to_sentences():
    from editor_app import clips, cuts
    t = _t("This is about burnout. Rest is not enough. Here are three things. First sleep.", lang="en")
    cl = cuts.build(t, cuts.default_settings("en"))
    flags = cuts.word_cut_flags(len(cuts.flat_words(t)), cl["detections"], cl["manual"])
    c = clips.from_selection(t, cl, flags, 6, 7)  # mitten in "Rest is not enough."
    assert c["own"] and c["parts"] == [[2]] and c["text"].startswith("Rest") and c["hook_text"]
