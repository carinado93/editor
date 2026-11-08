"""Tests für die Schnitt-Regeln (Carinas Regeln vom 8.11.)."""
from editor_app import cuts


def make(text: str, gaps: dict[int, float] | None = None, lang="en"):
    """Baut ein Transkript: jedes Wort 0,3 s, 0,05 s Abstand; gaps[i] = Pause *vor* Wort i."""
    gaps = gaps or {}
    t, words = 0.5, []
    for i, w in enumerate(text.split()):
        t += gaps.get(i, 0.05)
        words.append({"w": w, "s": round(t, 3), "e": round(t + 0.3, 3), "p": 0.9})
        t += 0.3
    return {"language": lang, "duration": t + 1, "segments": [{"s": 0, "e": t, "text": text, "words": words}]}


def kept(transcript, **settings):
    s = {**cuts.default_settings(transcript["language"]), **settings}
    ev = cuts.evaluate(transcript, cuts.build(transcript, s))
    return " ".join(w["w"] for w, f in zip(cuts.flat_words(transcript), ev["flags"]) if not f)


def test_restart_keeps_last_version():
    assert kept(make("I decided to make a, I decided to make a giveaway.")) == "I decided to make a giveaway."


def test_many_attempts_keep_only_the_last():
    t = make("So make sure to take part now. So make sure to, so make sure to, "
             "so make sure to take part now. So make sure to take part now in the giveaway.")
    assert kept(t) == "So make sure to take part now in the giveaway."


def test_restart_mid_sentence_with_thinking_pause_keeps_content():
    # 1:10 in Carinas Video: lange Denkpause vor dem Neuanfang, "burnt out three times" darf nicht verloren gehen
    text = ("and the thing is I burnt out three times and I made this notebook for the days that uh, "
            "and the thing is I made this notebook for the days that felt like too much.")
    t = make(text, gaps={20: 4.8})
    assert kept(t) == ("and the thing is I burnt out three times and I made this notebook "
                       "for the days that felt like too much.")


def test_more_than_five_seconds_of_speech_is_not_a_retake():
    filler = " ".join(["blah"] * 1) + " " + " ".join(f"w{i}" for i in range(20))  # 20 Wörter ≈ 7 s Sprechen
    t = make(f"I want to say {filler}. I want to say this.")
    assert kept(t).startswith("I want to say blah")


def test_repeated_sentence_is_cut():
    assert kept(make("So here it is. So here it is. My notebook.")) == "So here it is. My notebook."


def test_double_word_and_fragment():
    assert kept(make("then then just text")) == "then just text"
    assert kept(make("das ist Resi- Resilienz.", lang="de")) == "das ist Resilienz."


def test_two_common_words_mid_sentence_are_not_a_retake():
    t = make("more information in the caption and in the first comment.")
    assert kept(t) == "more information in the caption and in the first comment."


def test_signal_word_cuts_the_broken_sentence():
    t = make("Das ist gut. Stress ist eigentlich nochmal Stress ist ein Signal.", gaps={6: 0.6, 7: 0.6}, lang="de")
    assert kept(t) == "Das ist gut. Stress ist ein Signal."


def test_signal_word_inside_sentence_is_kept():
    t = make("Lies es nochmal durch.", lang="de")
    assert kept(t) == "Lies es nochmal durch."


def test_fillers_can_be_switched_off():
    t = make("Ähm, das ist äh wichtig.", lang="de")
    assert kept(t) == "das ist wichtig."
    fillers = {**cuts.DEFAULT_FILLERS["de"], "äh": False}
    assert kept(t, fillers=fillers) == "das ist äh wichtig."


def test_long_pause_is_shortened():
    t = make("Hallo. Welt.", gaps={1: 2.0}, lang="de")
    s = cuts.default_settings("de")
    ev = cuts.evaluate(t, cuts.build(t, s))
    assert len(ev["keep"]) == 2
    gap_left = ev["keep"][1][0] - ev["keep"][0][1]
    assert gap_left > 1.5  # 2 s Pause → auf 0,3 s gekürzt, also ~1,7 s herausgeschnitten
    assert ev["pauses"][0]["length"] == 2.0
    # Pause behalten
    cl = cuts.build(t, s, pause_keep=[0])
    assert len(cuts.evaluate(t, cl)["keep"]) == 1


def test_manual_keep_and_cut():
    t = make("I decided to make a, I decided to make a giveaway.")
    cl = cuts.build(t, cuts.default_settings("en"))
    cl["manual"] = {"keep": [0, 1, 2, 3, 4], "cut": [10]}
    flags = cuts.evaluate(t, cl)["flags"]
    assert flags[:5] == [None] * 5 and flags[10] == "manuell"


def test_padding_never_reaches_into_a_cut_word():
    t = make("and I made this notebook uh, and the thing is I made this notebook for you.", gaps={7: 3.0})
    s = cuts.default_settings("en")
    ev = cuts.evaluate(t, cuts.build(t, s))
    words = cuts.flat_words(t)
    for k, f in enumerate(ev["flags"]):
        if f:  # geschnittenes Wort: darf in keinem behaltenen Bereich liegen
            mid = (words[k]["s"] + words[k]["e"]) / 2
            assert not any(a <= words[k]["s"] + 0.01 and words[k]["s"] + 0.01 <= b for a, b in ev["keep"]), words[k]
            assert not any(a <= mid <= b for a, b in ev["keep"])
