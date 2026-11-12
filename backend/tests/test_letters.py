from pathlib import Path

from PIL import Image

from editor_app import letters as L


def test_split_blank_lines_and_auto():
    s, auto = L.split_text("Dear dog,\nline two\n\n*script*\nend.")
    assert s == [["Dear dog,", "line two"], ["*script*", "end."]] and not auto
    s, auto = L.split_text("One.\nTwo.\nThree and\nfour.\nFive.")
    assert auto and all(2 <= len(x) <= 5 for x in s[:-1]) and sum(len(x) for x in s) == 5


def test_render_both_styles_and_zip(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "DIR", tmp_path)
    b = L.new_letter("Dear test", "01", ["en", "de"])
    Image.new("RGB", (1200, 1500), (120, 130, 100)).save(L._dir(b["id"]) / "bilder" / "p.png")
    for lang in ("en", "de"):
        L.set_text(b, lang, 0, "Dear test,\nfirst line\n\nsecond\n*script line*\nend.")
        L.render_part(b, lang, 0)
    p = b["parts"]["en"][1]
    L.set_text(b, "en", 1, "Dear test,\nhello\n\nmore\nlines.")
    p["style"] = "painted"
    for s in p["slides"]:
        s["image"] = "p.png"
    for lvl in (0, 1, 2, 3):
        p["acrylic"] = lvl
        assert L.render_slide(b, "en", 1, 1).size == (1080, 1350)
    L.render_part(b, "en", 1)
    names = __import__("zipfile").ZipFile(__import__("io").BytesIO(L.zip_bytes(b))).namelist()
    assert "01 - Dear test/EN/Part 1 - Holding my breath/03-coming-soon.png" in names
    assert "01 - Dear test/DE/Teil 1 - Den Atem anhalten/03-demnaechst.png" in names
    assert L.hashtag_count(b["parts"]["de"][0]["caption"]) == 5


def test_forbidden_words():
    b = {"id": "x", "parts": {"en": [{"style": "storyteller", "slides": [{"lines": ["I am a stress & burnout coach"]}]}]}}
    try:
        L.render_slide(b, "en", 0, 0)
        assert False
    except Exception as e:  # noqa: BLE001
        assert "never" in str(e)
