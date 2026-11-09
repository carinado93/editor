from PIL import Image

from editor_app import covers


def photo():
    img = Image.new("RGB", (540, 960), (200, 180, 170))
    return img


def test_sizes_and_styles():
    face = [0.25, 0.1, 0.75, 0.5]
    assert covers.youtube_talking(photo(), face, "Rest didn't fix my *burnout*", "your body remembers").size == (1280, 720)
    assert covers.youtube_meditation(photo(), face, "Affirmations Meditation", "Gentle words", "5 minutes", "guided").size == (1280, 720)
    for c in ("lila", "hell", "oliv"):
        assert covers.reel_cover(photo(), face, "Only you control you", c).size == (1080, 1920)


def test_marked_text_and_default():
    assert covers.parse_marked("REST DIDN'T FIX MY *BURNOUT*") == [("REST DIDN'T FIX MY ", False), ("BURNOUT", True)]
    assert covers.parse_marked("WHAT HELPED MY *ANXIETY*?") == [("WHAT HELPED MY ", False), ("ANXIETY?", True)]
    t = covers.default_thumb_text("Why burnout is not about rest | stress", {"burnout"})
    assert "*burnout*" in t and "|" not in t


def test_cover_rotation(tmp_path, monkeypatch):
    from editor_app import config
    monkeypatch.setattr(covers, "ROOT", tmp_path)
    assert covers.next_cover_color() == "hell"  # zuletzt war lila
    assert covers.advance_cover_color("hell") == "oliv"
    assert covers.next_cover_color() == "oliv"
    assert covers.advance_cover_color("oliv") == "lila"
