import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

from editor_app import export, meta


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
    assert m["hashtags"] == ["#burnout", "#stress", "#selbstfürsorge"]
    assert any("heilt" in w or "Heilversprechen" in w for w in m["warnings"])
    full = meta.full_description(m)
    assert "0:00 Gewinnspiel" in full and "#burnout" in full


def test_meta_parse_rejects_garbage():
    import pytest
    from editor_app.errors import UserError
    with pytest.raises(UserError):
        meta.parse("Sorry, ich kann das nicht.", 60)


def test_prompt_contains_guardrails_and_times():
    p = meta.build_prompt([(0.0, "Hallo."), (75.0, "Stress ist ein Signal.")], "de", 120)
    assert "keine Heilversprechen" in p and "[1:15] Stress ist ein Signal." in p and "Genau 3 Titel" in p


def test_fcpxml_and_edl(tmp_path):
    info = {"width": 1080, "height": 1920, "duration": 20.0, "fps": 29.97, "fps_rational": "30000/1001"}
    fps = Fraction(30000, 1001)
    frames = [(0, 90), (150, 300)]
    xml = export.fcpxml("Test", Path(tmp_path / "original.mp4"), info, frames, fps)
    root = ET.fromstring(xml.split("\n", 2)[2])
    clips = root.findall(".//asset-clip")
    assert len(clips) == 2 and clips[1].get("offset") == "3003/1000s" and clips[1].get("start") == "1001/200s"
    edl = export.edl("Test", "original.mp4", frames, fps)
    assert "DROP FRAME" in edl and "00:00:05;00 00:00:10;00 00:00:03;00 00:00:08;00" in edl
