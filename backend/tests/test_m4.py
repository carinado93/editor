from editor_app import meta


def test_meta_parse_rules():
    answer = '''Hier ist dein Ergebnis:
    {"titles": ["Ich bin dreimal ausgebrannt", "Dieses Notizbuch heilt Burnout", "Nicht alles auf einmal"],
     "chapters": [{"time": "0:05", "title": "Gewinnspiel"}, {"time": "0:09", "title": "zu nah"},
                  {"time": "0:30", "title": "Das Notizbuch"}, {"time": "0:55", "title": "So machst du mit"}],
     "description": "Text", "tags": ["#burnout", "stress"], "hashtags": ["burnout", "#stress", "#selbstfürsorge", "#zu"]}'''
    m = meta.parse(answer, duration=70)
    assert m["chapters"][0]["time"] == "0:00"  # erstes Kapitel muss bei 0:00 sein
    assert [c["time"] for c in m["chapters"]] == ["0:00", "0:30", "0:55"]  # 0:05 → 0:00, "0:09" fällt weg (< 10 s)
    assert m["tags"] == ["burnout", "stress"]
    assert m["hashtags"][:4] == ["#burnout", "#stress", "#selbstfürsorge", "#zu"] and len(m["hashtags"]) == 5
    assert any("healing promise" in w for w in m["warnings"])
    full = meta.full_description(m)
    assert "0:00 Gewinnspiel" in full and "#burnout" in full


def test_meta_parse_rejects_garbage():
    import pytest
    from editor_app.errors import UserError
    with pytest.raises(UserError):
        meta.parse("Sorry, ich kann das nicht.", 60)


def test_prompt_contains_guardrails_and_times():
    p = meta.build_prompt([(0.0, "Hallo."), (75.0, "Stress ist ein Signal.")], "de", 120)
    assert "keine Heilversprechen" in p and "[1:15] Stress ist ein Signal." in p and "Genau 5 Titel" in p
    assert "GENAU 5 Hashtags" in p and "#burnoutprävention" in p


def test_new_hashtags_are_learned(tmp_path, monkeypatch):
    import json
    from editor_app import config
    (tmp_path / "vorlagen").mkdir()
    (tmp_path / "vorlagen" / "hashtags.json").write_text(json.dumps({"en": ["#burnout"]}))
    monkeypatch.setattr(config, "ROOT", tmp_path)
    warnings = []
    tags = meta.fix_hashtags(["#burnout", "#nervoussystemhealing", "rest more"], "en", warnings)
    assert len(tags) == 5 or tags[:3] == ["#burnout", "#nervoussystemhealing", "#restmore"]
    assert json.loads((tmp_path / "vorlagen" / "hashtags.json").read_text())["en"] == ["#burnout"]  # Repo-Datei bleibt
    bank = meta.hashtag_bank("en")
    assert "#nervoussystemhealing" in bank and "#restmore" in bank


def test_chapter_times_come_from_last_rendered_video(monkeypatch, tmp_path):
    """Kapitel: Zeiten aus dem zuletzt gerenderten Video (dessen Schnitte + Zeitraffer), nicht aus dem Entwurf."""
    import json
    import os
    import time
    from editor_app import cutstore, main, projects

    words = [{"w": w, "s": s, "e": s + 0.4} for w, s in
             [("Erster", 0.0), ("Satz", 0.5), ("hier.", 1.0), ("Weg", 5.0), ("damit.", 5.5), ("ok.", 6.0),
              ("Zweiter", 20.0), ("Satz", 20.5), ("kommt.", 21.0), ("Dritter", 40.0), ("Satz", 40.5), ("jetzt.", 41.0)]]
    exp = tmp_path / "export"
    exp.mkdir()
    monkeypatch.setattr(cutstore, "_transcript", lambda pid: {"language": "de", "segments": [{"words": words}]})
    monkeypatch.setattr(main.cuts, "flat_words", lambda t: words)
    # Entwurf jetzt: alles behalten, kein Zeitraffer
    monkeypatch.setattr(cutstore, "view", lambda pid: {"evaluation": {"keep": [[0, 45]], "flags": [False] * 12,
                                                                      "new_duration": 45},
                                                       "cutlist": {"speed": []}})
    monkeypatch.setattr(projects, "path", lambda pid, *parts: tmp_path.joinpath(*parts))
    # gerendert: 4–10 s rausgeschnitten, 10–30 s im 4× Zeitraffer
    old = exp / "a_schnitt_1.mp4"
    old.write_bytes(b"x")
    (exp / "a_schnitt_1.schnitte.json").write_text(json.dumps({"keep": [[0, 45]]}), encoding="utf-8")
    os.utime(old, (time.time() - 100, time.time() - 100))
    new = exp / "a_schnitt_2.mp4"
    new.write_bytes(b"x")
    (exp / "a_schnitt_2.schnitte.json").write_text(json.dumps(
        {"keep": [[0, 4], [10, 45]], "speed": [{"start": 10, "end": 30, "factor": 4}], "duration": 24.0}),
        encoding="utf-8")
    _, v, sents = main._cut_context("p", rendered=True)
    assert v["rendered_file"] == "a_schnitt_2.mp4"
    assert v["evaluation"]["new_duration"] == 24.0
    assert [s for _, s in sents] == ["Erster Satz hier.", "Zweiter Satz kommt.", "Dritter Satz jetzt."]
    starts = [t for t, _ in sents]
    assert starts[0] == 0.0
    assert abs(starts[1] - (4 + 10 / 4)) < 0.01      # 20 s im Original → 6.5 s im fertigen Video
    assert abs(starts[2] - (4 + 20 / 4 + 10)) < 0.01  # 40 s → 19 s
    _, v2, s2 = main._cut_context("p")                # ohne rendered: aktueller Entwurf
    assert len(s2) == 4 and "rendered_file" not in v2
