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


def test_blur_mode_uses_own_original_photo_she_right_centre_left(monkeypatch, tmp_path):
    """26 Nov 2026: default = her ORIGINAL photo heavily blurred, 3 looks (she right, centre, left)."""
    monkeypatch.setattr(thumbstore, "OWN", tmp_path)
    wid = thumbstore.new_own()
    d = thumbstore.wdir(wid)
    photo = Image.new("RGB", (1600, 900), (40, 60, 200))
    cut = fake_cutout().resize((300, 540))
    photo.paste(cut, (650, 360), cut)
    photo.save(d / "photo.png")
    cut.save(d / "cut.png")
    st = json.loads((d / "state.json").read_text(encoding="utf-8"))
    st.update(cutout="cut.png", photo="photo.png", face=FACE, cut_box=[650, 360, 950, 900])
    (d / "state.json").write_text(json.dumps(st), encoding="utf-8")
    out = thumbstore.generate(wid, "blur", [], [["worth", "it?"]], "auto", False, False)
    looks = [(v["spec"]["layout"], v["spec"]["side"]) for v in out["versions"]]
    assert looks == [("side", "right"), ("top", "right"), ("side", "left")]
    assert all(v["spec"]["blur"] for v in out["versions"])
    xs = [(v["person_box"][0] + v["person_box"][2]) / 2 for v in out["versions"]]
    assert xs[0] > 700 and 400 < xs[1] < 880 and xs[2] < 580
    for v in out["versions"]:
        assert not v["face_box"] or not any(_overlap(b, v["face_box"]) for b in v["word_boxes"])


def test_own_blur_background_brightness_always_in_range():
    for col in ((8, 6, 10), (128, 120, 110), (252, 252, 250)):
        for side in ("right", "centre", "left"):
            bg = thumbmaker.own_blur_background(Image.new("RGB", (1600, 1000), col), side)
            assert bg.size == (1280, 720)
            assert 0.44 <= thumbmaker.bg_brightness(bg) <= 0.86


def test_own_blur_background_darkens_the_text_side_only():
    bg = np.asarray(thumbmaker.own_blur_background(Image.new("RGB", (1600, 1000), (150, 140, 135)), "right"))
    left, right = bg[300:420, 20:80].mean(), bg[300:420, 1200:1260].mean()
    assert left < right, "she stands right, so the text side (left) is darker"
    c = np.asarray(thumbmaker.own_blur_background(Image.new("RGB", (1600, 1000), (150, 140, 135)), "centre"))
    assert abs(c[300:420, 20:80].mean() - c[300:420, 1200:1260].mean()) < 4
    assert c[360, 640].mean() > c[360, 30].mean()


def test_shadow_is_soft_brownish_not_purple():
    sh, pad = thumbmaker.soft_shadow(fake_cutout())
    a = np.asarray(sh)
    vis = a[..., 3] > 5
    assert a[..., 3].max() <= int(255 * 0.2) + 2
    r, g, b = (a[vis][:, :3].astype(int).mean(axis=0))
    assert r >= b, "no purple halo"


def _contaminated_person(size=(800, 900)):
    """Brown 'person' on a white wall with a light, half-transparent seam around her and two holes."""
    import cv2
    w, h = size
    rgb = np.full((h, w, 3), 246, np.uint8)
    m = np.zeros((h, w), np.uint8)
    cv2.ellipse(m, (400, 250), (120, 150), 0, 0, 360, 255, -1)       # head
    cv2.rectangle(m, (180, 380), (620, h - 1), 255, -1)               # body to the bottom edge
    person = m > 0
    rgb[person] = (110, 70, 50)
    alpha = person.astype(np.float32)
    # small hole (gap in glasses) and big enclosed hole (between arm and body)
    alpha[240:260, 380:400] = 0
    alpha[520:680, 300:460] = 0
    rgb[520:680, 300:460] = 246
    # white seam: the mask is 8 px too wide, the extra ring is wall colour
    ring = cv2.dilate(m, np.ones((17, 17), np.uint8)) > 0
    alpha[ring & ~person] = 0.85
    return rgb, alpha


def test_cutout_cleanup_no_white_fringe_and_holes():
    from editor_app import thumb_cutout as tc
    rgb, alpha = _contaminated_person()
    assert tc.fringe_pixels(rgb, alpha) > 0, "the test picture really has a white fringe"
    col, a, info = tc.clean(rgb, alpha, face_px=(280, 100, 520, 400))
    assert tc.fringe_pixels(col, a) == 0
    assert a[250, 390] > 0.9, "small hole (glasses) is filled"
    assert a[600, 380] < 0.05, "big enclosed hole (arm/body gap) is background"
    assert info["holes_filled"] >= 1 and info["holes_cleared"] >= 1
    assert a[800, 400] > 0.95, "the solid inside stays"
    assert np.array_equal(col[700:760, 250:280], rgb[700:760, 250:280]), "her inside is never recoloured"


def test_cutout_keeps_only_largest_piece():
    from editor_app import thumb_cutout as tc
    rgb, alpha = _contaminated_person()
    alpha[50:90, 700:760] = 1.0     # floating dot (piece of furniture)
    rgb[50:90, 700:760] = (200, 60, 90)
    _, a, _ = tc.clean(rgb, alpha, face_px=(280, 100, 520, 400))
    assert a[50:90, 700:760].max() < 0.05

