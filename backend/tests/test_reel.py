from editor_app import captions, cuts, cutstore, subtitles


def transcript():
    words, t = [], 0.3
    for w in "Burnout is not a lack of rest. It is a lack of boundaries. Try this today.".split():
        words.append({"w": w, "s": round(t, 2), "e": round(t + 0.3, 2), "p": 0.9})
        t += 0.4
    return {"language": "en", "duration": 8.0, "segments": [{"s": 0, "e": t, "text": "", "words": words}]}


def test_reel_mode_never_cuts():
    t = transcript()
    s = cuts.default_settings("en")
    s["no_cuts"] = True
    cl = cuts.build(t, s)
    assert cl["detections"] == []
    ev = cuts.evaluate(t, cl)
    assert ev["keep"] == [[0.0, 8.0]] and ev["new_duration"] == 8.0 and not any(ev["flags"])


def test_default_hook_is_first_sentence_long_enough():
    hook = cutstore.default_hook(transcript())[0]
    assert hook["text"].replace("*", "") == "Burnout is not a lack of rest"
    assert "*Burnout*" in hook["text"]  # Themenwort wird Akzent
    assert hook["end"] - hook["start"] >= 4.4


def test_hook_card_avoids_face():
    # Gesicht oben (wie Selfie) → Karte unter das Kinn, aber in der Safe Zone (≤ 1250)
    y = subtitles.hook_y(1920, [0.2, 0.05, 0.8, 0.45], 2, 76)
    assert y >= 0.45 * 1920 and y + 2 * 76 * 1.3 <= 1250 + 1
    # Gesicht unten → Karte oben bei ~300
    assert subtitles.hook_y(1920, [0.3, 0.55, 0.7, 0.85], 2, 76) == 300
    a = subtitles.ass(1080, 1920, None, [], [0.2, 0.05, 0.8, 0.45], hooks=[{"s": 0.2, "e": 4.8, "text": "Not a *lack of rest*"}])
    assert "Style: Hook" in a and "\\i1" in a and "lack of rest" in a


def test_caption_parse_exactly_five_hashtags_and_checks():
    answer = '{"caption": "Burnout is not a lack of rest. 🤍\\n\\nThis week: say no once.\\n\\nNot a diagnosis or therapy. #burnout #rest", "hashtags": ["#burnout", "#stress"], "cover_text": "Rest won\'t fix it", "shorts_title": "Burnout isn\'t about rest"}'
    d = captions.parse(answer, "en")
    assert len(d["hashtags"]) == 5 and d["hashtags"][:3] == ["#burnout", "#stress", "#rest"]
    assert "#" not in d["caption"]
    assert not any("Diagnose" in w for w in d["warnings"])
    full = captions.full_caption(d)
    assert full.endswith(" ".join(d["hashtags"]))


def test_caption_prompt_has_guardrails_and_account():
    p = captions.build_prompt("Hallo", "de", "Hook")
    assert "@carinadorca.coach" in p and "GENAU 5 Hashtags" in p and "keine Heilversprechen" in p
