"""Studio transitions (split, iris) and language versions."""
from PIL import Image

from editor_app import transitions_studio as ts
from editor_app import translate


def _frames(color, n=12, size=(320, 180)):
    return [Image.new("RGB", size, color) for _ in range(n)]


def test_spans_are_clipped_to_clip_length():
    ta, tb = ts.spans("split", 10, 10)
    assert ta == 3.0 and tb > ta
    ta, tb = ts.spans("split", 1.5, 2.0)
    assert 1.0 <= ta <= 1.5
    assert ts.spans("iris", 5, 5) == (0.4, 0.4)


def test_split_and_iris_render_full_size_frames():
    fa, fb = _frames((200, 30, 30)), _frames((30, 30, 200), 16)
    sp = ts.render_split(fa, fb, 320, 180)
    assert len(sp) == len(fb) and all(f.size == (320, 180) for f in sp)
    ir = ts.render_iris(fa, fb, 320, 180)
    assert ir and all(f.size == (320, 180) for f in ir)
    # ends on clip B
    r, g, b = ir[-1].convert("RGB").getpixel((160, 90))
    assert b > r


def test_translate_apply_and_restore(monkeypatch):
    store = {"overlays": [{"kind": "fx", "title": "Good morning", "items": ["coffee", ""]},
                          {"kind": "text", "text": "Back to editing"}]}

    def change(pid, fn):
        fn(store)
        return store
    monkeypatch.setattr(translate.cutstore, "_change", change)
    monkeypatch.setattr(translate.cutstore, "load", lambda pid: store)
    keys = [r["key"] for r in translate._rows(store["overlays"])]
    assert keys == ["0:title", "0:item:0", "1:text"]
    translate.apply("p", "de", [{"key": "0:title", "dst": "Guten Morgen"}, {"key": "1:text", "dst": "Zurück zum Schnitt"},
                                {"key": "0:item:0", "dst": ""}])
    assert store["overlays"][0]["title"] == "Guten Morgen" and store["overlays"][0]["items"][0] == "coffee"
    assert store["overlays"][1]["text"] == "Zurück zum Schnitt" and store["text_language"] == "de"
    assert store["texts_original"][0]["title"] == "Good morning"
    translate.restore("p")
    assert store["overlays"][0]["title"] == "Good morning" and "text_language" not in store
