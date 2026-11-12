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
