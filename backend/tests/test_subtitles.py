from editor_app import subtitles


def test_timemap_maps_original_to_new_time():
    tm = subtitles.TimeMap([(1.0, 3.0), (5.0, 6.0)])
    assert tm(1.5) == 0.5
    assert tm(5.5) == 2.5
    assert tm(4.0) is None  # geschnitten
    assert tm.clamp(4.0) == 2.0
    assert tm.total == 3.0


def test_lines_break_at_sentence_and_merge_short_rest():
    words = []
    t = 0.0
    for w in "I decided to make a giveaway. So if you are seeing this, then it is for you.".split():
        words.append({"i": len(words), "w": w, "s": t, "e": t + 0.2})
        t += 0.25
    groups = subtitles.lines(words, max_chars=26)
    texts = [" ".join(w["w"] for w in g) for g in groups]
    assert texts[0] == "I decided to make a giveaway."
    assert all(len(x) <= 26 * 1.35 for x in texts)
    srt = subtitles.srt(groups)
    assert srt.startswith("1\n00:00:00,000 --> ")


def test_ass_contains_styles_and_buzzword():
    a = subtitles.ass(1080, 1920, [[{"w": "Hallo", "s": 0.0, "e": 0.5}]], [{"s": 1.0, "e": 2.8, "text": "Burnout"}], None)
    assert "Style: Buzz,Cormorant Garamond Bold" in a
    assert "Burnout" in a and "\\fscx40" in a
    assert "Dialogue: 0,0:00:00.00" in a


def test_rule_based_buzzwords_are_unique_and_spread():
    from editor_app import buzz
    words, t = [], 0.0
    for w in ("Stress is normal. Burnout is not. Stress again and again. Your nervous system needs rest. " * 4).split():
        words.append({"w": w, "s": t, "e": t + 0.3})
        t += 0.6
    found = buzz.suggest(words, [None] * len(words))
    toks = [words[b["start"]]["w"].strip(".").lower() for b in found]
    assert len(toks) == len(set(toks)) >= 2
