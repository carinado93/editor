"""Große Effekte: Zeichnen, Vorschläge, Zeitraffer."""
from PIL import Image

from editor_app import effects, fx, fxrender, subtitles


def test_every_effect_draws_a_frame():
    frame = Image.new("RGB", (640, 360), (120, 110, 100))
    mask = Image.new("L", (640, 360), 0)
    for typ in fx.TYPES:
        for place in fx.TYPES[typ][2]:
            it = {"id": "x", "type": typ, "place": place, "title": "was wäre *wenn*|ich kündige",
                  "items": ["Grenzen setzen|8", "Pausen", "Hilfe holen"]}
            ctx = fx.Ctx(640, 360, None, [{"w": "Burnout", "s": 0, "e": 3}])
            out = fx.render_frame(frame, it, 1.5, 3.0, ctx, mask)
            assert out.size == (640, 360) and out.mode == "RGB", typ


def test_suggestions_are_parsed_and_limited_to_allowed():
    words = [{"w": w, "s": k * 0.5, "e": k * 0.5 + 0.4} for k, w in enumerate("Ich darf keine Diagnose stellen und keine Medikamente geben".split())]
    flags = [None] * len(words)
    data = {"items": [
        {"type": "checklist", "place": "side", "word": 1, "end_word": 9, "title": "Grenzen", "items": ["keine Diagnose", "keine Medikamente"],
         "item_words": [3, 7], "why": "Liste"},
        {"type": "behind", "place": "side", "word": 2, "end_word": 4, "title": "BURNOUT", "items": [], "item_words": [], "why": ""},
    ]}
    items = effects.parse(data, words, flags, ["checklist"])
    assert [i["type"] for i in items] == ["checklist"]
    assert items[0]["item_t"] == [round(words[3]["e"] - 0.1, 2), round(words[7]["e"] - 0.1, 2)]
    assert items[0]["end"] - items[0]["start"] >= 2.5


def test_speed_ranges_and_atempo():
    tm = subtitles.TimeMap([(0, 10), (12, 20)])
    r = fxrender.prepare_speed([{"start": 13, "end": 17, "factor": 4, "mute": True},
                                {"start": 14, "end": 15, "factor": 2}], tm, 18)
    assert r == [(11.0, 15.0, 4.0, True)]
    assert fxrender._atempo(8) == "atempo=2.0,atempo=2.0,atempo=2.0000"
    assert fxrender._atempo(0.25) == "atempo=0.5,atempo=0.5000"


def test_statement_cards_win_over_side_effects():
    from editor_app import fxrender, subtitles
    tm = subtitles.TimeMap([(0.0, 200.0)])
    ov = [{"kind": "fx", "type": "checklist", "place": "side", "start": 75.7, "end": 81.0},
          {"kind": "fx", "type": "statement", "place": "scene", "start": 80.0, "end": 83.5},
          {"kind": "fx", "type": "label", "place": "side", "start": 80.2, "end": 86.0},
          {"kind": "fx", "type": "statement", "place": "scene", "start": 99.8, "end": 103.0},
          {"kind": "fx", "type": "label", "place": "side", "start": 99.5, "end": 104.0}]
    got = fxrender.prepare(ov, tm, [], 200)
    assert [g["type"] for g in got].count("statement") == 2
    assert all(a["e"] <= b["s"] for a, b in zip(got, got[1:]))  # nie zwei gleichzeitig


def test_styles_save_clean_and_overwrite(tmp_path, monkeypatch):
    from editor_app import styles
    monkeypatch.setattr(styles, "FILE", tmp_path / "s.json")
    styles.save({"name": "My YouTube style", "allowed": ["statement", "nope"], "sizes": {"label": 1.3, "x": 2},
                 "outro": True, "render": {"declick": True, "subtitles": "bad"}})
    items = styles.save({"name": "my youtube style", "allowed": ["label"]})  # gleicher Name → überschreiben
    assert len(items) == 1 and items[0]["allowed"] == ["label"]
    st = styles.clean({"name": "x", "sizes": {"label": 9}, "render": {"subtitles": "srt"}})
    assert st["sizes"]["label"] == 2.5 and st["render"] == {"subtitles": "srt"}


def test_plan_add_update_delete(tmp_path, monkeypatch):
    from editor_app import plan
    monkeypatch.setattr(plan, "FILE", tmp_path / "p.json")
    items = plan.add([{"date": "2026-11-16", "type": "carousel", "title": "A"}, {"type": "x", "date": "bad"}])
    assert items[0]["date"] == "" and items[0]["type"] == "reel"  # Ideen-Kiste zuerst (ohne Datum)
    items = plan.update(items[1]["id"], {"status": "done"})
    assert any(i["status"] == "done" for i in items)
    assert len(plan.delete(items[0]["id"])) == 1
