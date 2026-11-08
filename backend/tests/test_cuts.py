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


def test_noise_between_words_is_found_and_cut(tmp_path):
    import wave
    import numpy as np
    from editor_app import noises

    sr = 16000
    audio = np.zeros(sr * 4, dtype=np.float32)
    rng = np.random.default_rng(0)

    def tone(a, b, amp):
        n = int((b - a) * sr)
        audio[int(a * sr):int(a * sr) + n] = amp * np.sin(np.arange(n) * 2 * np.pi * 200 / sr) + rng.normal(0, 0.001, n)

    tone(0.5, 1.0, 0.3)   # Wort 1
    tone(1.6, 1.85, 0.25)  # "meah" (kein Wort erkannt)
    tone(2.5, 3.0, 0.3)   # Wort 2
    wav = tmp_path / "ton.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(sr)
        w.writeframes((audio * 32767).astype(np.int16).tobytes())
    words = [{"w": "Hallo", "s": 0.5, "e": 1.0, "p": 0.9}, {"w": "Welt", "s": 2.5, "e": 3.0, "p": 0.9}]
    found = noises.find(wav, words)
    assert len(found) == 1 and 1.5 <= found[0]["start"] <= 1.7 and 1.8 <= found[0]["end"] <= 1.95
    t = {"language": "de", "duration": 4.0, "segments": [{"s": 0, "e": 3, "text": "", "words": words}]}
    cl = cuts.build(t, cuts.default_settings("de"))
    cl["noises"] = found
    keep = cuts.evaluate(t, cl)["keep"]
    assert not any(a <= 1.7 <= b for a, b in keep)  # Laut liegt in keinem behaltenen Bereich
    cl["pause_keep"] = [0]  # "behalten" geklickt
    assert len(cuts.evaluate(t, cl)["keep"]) == 1


def test_word_tail_is_not_a_noise(tmp_path):
    import wave
    import numpy as np
    from editor_app import noises

    sr = 16000
    audio = np.zeros(sr * 3, dtype=np.float32)
    n = int(0.9 * sr)  # Wort klingt länger als die Spracherkennung meint (bis 1,4 s statt 1,0 s)
    audio[int(0.5 * sr):int(0.5 * sr) + n] = 0.3 * np.sin(np.arange(n) * 2 * np.pi * 200 / sr)
    wav = tmp_path / "ton.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(sr)
        w.writeframes((audio * 32767).astype(np.int16).tobytes())
    words = [{"w": "someone.", "s": 0.5, "e": 1.0, "p": 0.9}, {"w": "Then", "s": 2.2, "e": 2.5, "p": 0.9}]
    assert noises.find(wav, words) == []


def test_sound_right_after_word_with_dip_is_found(tmp_path):
    """Wie bei 2:14: "someone" – kurze Senke (keine Stille) – "meah"."""
    import wave
    import numpy as np
    from editor_app import noises

    sr = 16000
    rng = np.random.default_rng(1)
    audio = rng.normal(0, 0.003, sr * 4).astype(np.float32)  # Raumrauschen, nie ganz still

    def tone(a, b, amp):
        n = int((b - a) * sr)
        audio[int(a * sr):int(a * sr) + n] += amp * np.sin(np.arange(n) * 2 * np.pi * 180 / sr)

    tone(0.5, 1.15, 0.3)   # "someone" (Spracherkennung sagt: endet bei 1,0)
    tone(1.15, 1.3, 0.02)  # Senke
    tone(1.3, 1.45, 0.2)   # "meah"
    tone(3.0, 3.4, 0.3)    # "Then"
    wav = tmp_path / "ton.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(sr)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
    words = [{"w": "someone.", "s": 0.5, "e": 1.0, "p": 0.9}, {"w": "Then", "s": 3.0, "e": 3.4, "p": 0.9}]
    found = noises.find(wav, words)
    assert len(found) == 1 and 1.25 <= found[0]["start"] <= 1.35, found
