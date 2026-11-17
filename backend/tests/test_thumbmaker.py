"""Thumbnail-Maker: Größe, Gesicht frei, Dateigröße, 'Text hinter mir' (Pixelprüfung)."""
import io
import json

import numpy as np
from PIL import Image, ImageDraw

from editor_app import image_gen, thumbmaker, thumbstore

FACE = [0.32, 0.08, 0.68, 0.30]  # relativ zum Ausschnitt
PERSON_RGB = (12, 200, 40)        # Farbe, die sonst nirgends vorkommt


def fake_cutout() -> Image.Image:
    """Eine einfache 'Person' (Kopf + Oberkörper) in einer Kontrollfarbe, freigestellt."""
    w, h = 500, 900
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((int(FACE[0] * w), int(FACE[1] * h), int(FACE[2] * w), int(FACE[3] * h)), fill=PERSON_RGB + (255,))
    d.rectangle((60, int(0.30 * h), w - 60, h), fill=PERSON_RGB + (255,))
    return im


def fake_generate(prompt, w=1280, h=720, **kw):
    return Image.new("RGB", (w, h), (90, 110, 150)), "fake"


def _overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def test_fake_background_size_face_free_and_small_file(monkeypatch):
    monkeypatch.setattr(image_gen, "generate", fake_generate)
    bg, _ = image_gen.generate("office")
    for layout in ("top", "two", "side", "auto"):
        res = thumbmaker.compose(bg, fake_cutout(), FACE, thumbmaker.Spec("worth", "it?", layout=layout))
        assert res.image.size == (1280, 720)
        assert res.face_box is not None
        for box in res.word_boxes:
            assert not _overlap(box, res.face_box), (layout, box, res.face_box)
        png = thumbmaker.to_png(res.image)
        assert len(png) < 2_000_000
        assert Image.open(io.BytesIO(png)).size == (1280, 720)


def test_text_behind_me_cutout_on_top_and_words_readable(monkeypatch):
    monkeypatch.setattr(image_gen, "generate", fake_generate)
    bg, _ = image_gen.generate("office")
    # fest deckende Person (ganzes Rechteck) -> jeder Pixel in ihrem Kasten muss Person sein, auch hinter dem Text
    cut = Image.new("RGBA", (500, 900), PERSON_RGB + (255,))
    res = thumbmaker.compose(bg, cut, FACE, thumbmaker.Spec("worth", "it?", layout="top", behind=True))
    arr = np.asarray(res.image).astype(int)
    px0, py0, px1, py1 = res.person_box
    behind_px = 0
    for (x0, y0, x1, y1) in res.word_boxes:
        X0, Y0, X1, Y1 = max(x0, px0), max(y0, py0), min(x1, px1), min(y1, py1)
        if X0 < X1 and Y0 < Y1:
            reg = arr[Y0:Y1, X0:X1]
            behind_px += reg.shape[0] * reg.shape[1]
            assert (np.abs(reg - PERSON_RGB).sum(axis=2) < 40).all(), "text drawn on top of the person"
    assert behind_px > 1000, "test setup: the text should sit partly behind the person"
    # ≥70 % von jedem Wort sichtbar
    assert all(v >= 0.70 for v in res.visible), res.visible
    assert not res.warnings


def test_store_makes_three_versions_with_fake_generator(monkeypatch, tmp_path):
    monkeypatch.setattr(thumbstore, "OWN", tmp_path)
    monkeypatch.setattr(image_gen, "generate", fake_generate)
    wid = thumbstore.new_own()
    d = thumbstore.wdir(wid)
    fake_cutout().save(d / "cut.png")
    st = json.loads((d / "state.json").read_text(encoding="utf-8"))
    st.update(cutout="cut.png", photo="cut.png", face=FACE)
    (d / "state.json").write_text(json.dumps(st), encoding="utf-8")
    out = thumbstore.generate(wid, "titles", ["office"], [["I", "quit."], ["worth", "it?"], ["burned", "out."]],
                              "auto", False, False)
    assert len(out["versions"]) == 3
    assert [v["spec"]["title1"] for v in out["versions"]] == ["I", "worth", "burned"]
    for v in out["versions"]:
        f = d / v["png"]
        assert f.exists() and f.stat().st_size < 2_000_000
        assert Image.open(f).size == (1280, 720)


def test_my_colours_mode_makes_three_colour_pairs(monkeypatch, tmp_path):
    monkeypatch.setattr(thumbstore, "OWN", tmp_path)
    wid = thumbstore.new_own()
    d = thumbstore.wdir(wid)
    fake_cutout().save(d / "cut.png")
    st = json.loads((d / "state.json").read_text(encoding="utf-8"))
    st.update(cutout="cut.png", photo="cut.png", face=FACE)
    (d / "state.json").write_text(json.dumps(st), encoding="utf-8")
    out = thumbstore.generate(wid, "colours", [], [["worth", "it?"]], "top", False, False)
    assert [v["prompt"] for v in out["versions"]] == ["colours:lilac+pink", "colours:pink+yellow", "colours:yellow+lilac"]
    assert not out["fallback_used"]
    for v in out["versions"]:
        assert v["spec"]["colours"] and (d / v["png"]).stat().st_size < 2_000_000
