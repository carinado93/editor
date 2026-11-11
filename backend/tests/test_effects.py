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
