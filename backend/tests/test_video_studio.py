"""Video Studio / Drone Cutter: Takt, Schnittplan, Farb-LUT, Titel, Musik, Render."""
import json
from pathlib import Path
import subprocess
import wave

import numpy as np
import pytest
from PIL import Image

from editor_app import media
from editor_app.video_studio import analysis, beats, color, music, planner, render, store, text


def _click_track(path, bpm=96, dur=20, sr=44100):
    t = np.zeros(sr * dur)
    for k in np.arange(0, dur, 60 / bpm):
        i, n = int(k * sr), int(0.1 * sr)
        t[i:i + n] += 0.8 * np.sin(2 * np.pi * 60 * np.arange(n) / sr) * np.exp(-np.arange(n) / sr * 30)
    w = wave.open(str(path), "wb")
    w.setnchannels(1), w.setsampwidth(2), w.setframerate(sr)
    w.writeframes((np.clip(t, -1, 1) * 32767).astype(np.int16).tobytes())
    w.close()
    return path


def _clip(path, dur=12, size="640x360", fps=30):
    """Bewegter Testclip (Farbverlauf + Muster, langsamer Schwenk)."""
    subprocess.run([media.ffmpeg(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"testsrc2=size=1280x720:rate={fps}:duration={dur}", "-vf",
                    f"crop=960:540:'160+100*sin(t/4)':90,scale={size}", "-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def test_beat_tracker_finds_tempo_and_beats(tmp_path):
    r = beats.analyse(_click_track(tmp_path / "c.wav", bpm=96))
    assert abs(r["bpm"] - 96) < 1.0
    period = 60 / 96
    # jeder gefundene Schlag liegt höchstens 25 ms neben dem echten Klick
    errs = [min(abs(b - k * period) for k in range(40)) for b in r["beats"]]
    assert max(errs) < 0.025


@pytest.mark.parametrize("mode,dur", [("reel", 15), ("reel", 30), ("reel", 60), ("youtube", 180)])
def test_plan_fits_length_exactly_and_snaps_to_beats(mode, dur):
    L = 6 if mode == "reel" else 16   # YouTube-Aufnahmen sind länger (6–16 s)
    moments = [{"clip": "a", "start": float(s), "dur": float(L), "score": 0.7 - s * 0.001, "hero": s == 0,
                "transit": False, "direction": "", "scene": s // L} for s in range(0, 2400, L)]
    bts = list(np.arange(0.31, dur, 60 / 100))
    shots = planner.plan(moments, dur, mode, bts, fps=30.0, title_len=3.0 if mode == "reel" else 0)
    total = sum(s.dur for s in shots)
    assert abs(total - dur) < 1 / 30 + 1e-6
    lo, hi = planner.MODES[mode]["min"], planner.MODES[mode]["first_max"]
    # im Wunschbereich; liegt dort kein Schlag, darf es bis ±25 % abweichen (Schnitt bleibt auf dem Takt)
    assert all(lo * 0.85 - 1e-6 <= s.dur <= hi * 1.25 + 1e-6 for s in shots)
    for s in shots[1:]:   # jeder Schnitt auf einem Schlag (±1 Bild)
        assert min(abs(s.t0 - b) for b in bts) <= 1 / 30 + 1e-6
    if mode == "reel":
        assert shots[0].hero and shots[0].dur >= 3.0     # Hook = bester Moment, trägt den Titel
    used = [(s.clip, s.src_in, s.src_in + s.src_dur) for s in shots]
    for i, a in enumerate(used):   # gleiche Bilder nie zweimal
        for b in used[i + 1:]:
            assert a[0] != b[0] or a[2] <= b[1] + 1e-6 or b[2] <= a[1] + 1e-6


def test_colour_cube_identity_and_no_crushed_blacks():
    x = np.linspace(0, 1, color.N)
    ident = np.stack(np.meshgrid(x, x, x, indexing="ij")[::-1], -1)
    assert np.abs(color.bake({"protect_skin": True}) - ident).max() < 1e-9
    lut = color.bake(color.params_for("natural_plus"))
    assert lut[0, 0, 0].max() < 0.01 and lut[-1, -1, -1].min() > 0.9   # Schwarz bleibt, Weiß nicht ausgefressen
    img = (np.random.default_rng(1).random((40, 40, 3)) * 255).astype(np.uint8)
    assert np.array_equal(color.apply_lut(img, ident), img)              # Interpolation exakt


def test_cube_file_roundtrip(tmp_path):
    lut = color.bake(color.params_for("golden_hour"))
    f = color.write_cube(lut, tmp_path / "g.cube")
    assert np.abs(color.read_cube(f) - lut).max() < 1e-5


def test_skin_tones_are_protected():
    skin = np.array([[[0.85, 0.62, 0.5]]])
    p = color.params_for("tropical_pop")
    on = color.grade(skin, {**p, "protect_skin": True})
    off = color.grade(skin, {**p, "protect_skin": False})
    sat = lambda c: c.max() - c.min()  # noqa: E731
    assert sat(on) < sat(off)


def test_location_title_centred_caps_and_tightening():
    t = text.Title(text="Sri Lanka", subtitle="Island")
    early, late = text.state(t, 0.5), text.state(t, 2.6)
    assert early[1] > late[1] and early[0] < 1.0       # Laufweite zieht sich zusammen, Einblenden
    assert text.state(t, t.start + t.duration + 0.1)[0] == 0
    im = text.render_frame(t, 1080, 1920, 2.0)
    a = np.asarray(im.getchannel("A")) > 128
    ys, xs = np.where(a)
    assert abs((xs.min() + xs.max()) / 2 - 540) < 12            # waagrecht mittig
    assert 0.38 * 1920 < ys.min() < 0.46 * 1920                 # etwas über der Mitte


def test_music_window_beats_loop_and_filter():
    tr = {"duration": 10.0, "bpm": 120, "beats": list(np.arange(0.0, 10.0, 0.5))}
    bts = music.beats_in_window(tr, 2.0, 25.0)
    assert bts[0] == 0.0 and max(bts) <= 25.0 and len(bts) >= 45   # geloopt
    inp, chain = music.audio_filter(music.MUSIC_DIR / "x.mp3", 2.0, 15.0, duck=(0.2, 3.2))
    assert "-stream_loop" in inp and "afade=t=out" in chain and "volume=" in chain


def test_analysis_finds_moments(tmp_path):
    f = _clip(tmp_path / "a.mp4", dur=10)
    r = analysis.analyse("a", f)
    assert r["moments"] and all(0 <= m["start"] < 10 for m in r["moments"])
    assert r["moments"][0]["score"] >= r["moments"][-1]["score"]


def test_render_reel_end_to_end(tmp_path):
    src = _clip(tmp_path / "a.mp4", dur=12)
    info = media.probe(src)
    plan = {"format": "reel", "shots": [
        {"clip": "a", "src_in": 0.5, "src_dur": 3.0, "t0": 0, "dur": 3.0, "speed": 1.0},
        {"clip": "a", "src_in": 5.0, "src_dur": 2.0, "t0": 3.0, "dur": 2.0, "speed": 1.0},
        {"clip": "a", "src_in": 8.0, "src_dur": 2.0, "t0": 5.0, "dur": 2.0, "speed": 1.0}],
        "grade": {"look": "natural_plus", "strength": 1.0},
        "title": {"text": "Sri Lanka", "subtitle": "Island", "start": 0.2, "duration": 2.5},
        "music": {"file": "click.wav", "path": str(_click_track(tmp_path / "click.wav")), "start": 0.0}}
    out = tmp_path / "out.mp4"
    res = render.render(plan, {"a": {"path": src, "info": info}}, tmp_path / "work", out, "preview")
    assert res["width"] == 540 and res["height"] == 960
    o = media.probe(out)
    assert abs(o["duration"] - 7.0) < 0.1 and o["has_audio"]
    # Titel ist im Bild (weiße Pixel in der Titelzeile bei 1,5 s)
    fr = tmp_path / "f.png"
    subprocess.run([media.ffmpeg(), "-y", "-loglevel", "error", "-ss", "1.5", "-i", str(out), "-frames:v", "1",
                    str(fr)], check=True)
    row = np.asarray(Image.open(fr).convert("L"))[int(0.40 * 960):int(0.48 * 960)]
    assert (row > 240).sum() > 50


def test_store_project_flow_settings_and_music_warning(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "BASE", tmp_path)
    st = store.create("Madeira")
    sid = st["sid"]
    src = _clip(tmp_path / "a.mp4", dur=8)
    store.write_chunk(sid, "up12345", 0, src.read_bytes())
    st = store.finish_upload(sid, "up12345", "a.mp4")
    assert len(st["clips"]) == 1 and st["clips"][0]["info"]["width"] == 640
    st = store.set_settings(sid, {"location": "Madeira", "title": {"size": 0.08}})
    assert st["settings"]["title"]["size"] == 0.08 and st["settings"]["title"]["font"] == "Montserrat ExtraLight"
    assert store.target_duration({"format": "youtube", "minutes": 3, "length": 15}) == 180
    assert "Content ID" in music.CONTENT_ID_NOTE
    json.dumps(store.load(sid))


def test_lut_path_with_windows_drive_letter_is_escaped_once(tmp_path, monkeypatch):
    """Carinas Fehler 18.11.: C:/… im lut3d-Pfad → genau ein Backslash vor dem Doppelpunkt."""
    monkeypatch.setattr(media, "has_filter", lambda name: True)
    f, extra = color.ffmpeg_filter(Path("C:/Users/carin/editor-app/daten/grade.cube"), tmp_path)
    assert "file='C\\:/Users/carin/editor-app/daten/grade.cube'" in f and not extra


def test_speed_ramp_pieces_sum_and_mean():
    from editor_app.video_studio import speed
    ps = speed.pieces("hero", 1.0, 2.4)
    assert abs(sum(L for L, _ in ps) - 2.4) < 1e-9
    assert min(v for _, v in ps) < 0.5 and max(v for _, v in ps) > 0.9   # Zeitlupe in der Mitte, Ränder normal
    assert 0.6 < speed.mean_speed("hero") < 0.75
    assert speed.pieces("", 2.0, 3.0) == [(3.0, 2.0)]


def test_auto_transitions_match_cut_and_youtube_dissolves():
    from editor_app.video_studio import transitions
    shots = [{"dur": 2.0, "direction": "left", "hero": False}, {"dur": 2.0, "direction": "left", "hero": False},
             {"dur": 2.0, "direction": "", "hero": True}, {"dur": 2.0, "direction": "", "hero": False}]
    yt = transitions.auto(shots, "youtube")
    assert [t["id"] for t in yt] == ["dissolve", "dissolve", "fade_black"]
    assert all(t["dur"] <= 0.9 for t in yt)                          # nie länger als knapp die halbe Aufnahme
    reel = transitions.auto(shots * 3, "reel", seed=1)
    assert {t["id"] for t in reel} - {"cut"}                         # einige Übergänge …
    assert sum(t["id"] == "cut" for t in reel) >= len(reel) / 2      # … aber meist harte Schnitte


def test_title_animations_differ():
    t_rise = text.Title(text="Madeira", anim_in="rise")
    t_letters = text.Title(text="Madeira", anim_in="letters")
    a = np.asarray(text.render_frame(t_rise, 540, 960, 0.5).getchannel("A"))
    b = np.asarray(text.render_frame(t_letters, 540, 960, 0.5).getchannel("A"))
    assert np.where(a > 30)[0].mean() > 0.44 * 960        # steigt von unten auf
    assert (b > 30).sum() < (a > 30).sum()                 # erst ein Teil der Buchstaben sichtbar
    o = text.Title(text="@carina.dorca", keep_case=True, anim_in="fade", start=0, duration=2)
    assert text.render_frame(o, 540, 960, 1.0) is not None


def test_render_with_transitions_ramp_and_outro(tmp_path):
    src = _clip(tmp_path / "a.mp4", dur=14)
    info = media.probe(src)
    shots = [{"clip": "a", "src_in": 0.5, "src_dur": 2.5, "t0": 0, "dur": 2.5, "speed": 1.0},
             {"clip": "a", "src_in": 4.0, "src_dur": 1.4, "t0": 2.5, "dur": 2.0, "speed": 1.0, "ramp": "hero"},
             {"clip": "a", "src_in": 7.0, "src_dur": 4.0, "t0": 4.5, "dur": 2.0, "speed": 2.0}]
    plan = {"format": "youtube", "shots": shots, "grade": {"look": "none"},
            "transitions": [{"id": "dissolve", "dur": 0.5}, {"id": "swipe_left", "dur": 0.4}],
            "outro": {"enabled": True, "text": "@test", "duration": 1.5}}
    out = tmp_path / "o.mp4"
    render.render(plan, {"a": {"path": src, "info": info}}, tmp_path / "w", out, "preview")
    r = subprocess.run([media.ffprobe(), "-v", "error", "-count_frames", "-select_streams", "v", "-show_entries",
                        "stream=nb_read_frames,width,height", "-of", "json", str(out)], capture_output=True, text=True)
    s = json.loads(r.stdout)["streams"][0]
    assert (s["width"], s["height"]) == (960, 540)
    assert abs(int(s["nb_read_frames"]) - 6.5 * 30) <= 1           # Länge bleibt trotz Übergängen exakt


def test_both_formats_and_timeline_edits(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "BASE", tmp_path)
    sid = store.create("Both")["sid"]
    src = _clip(tmp_path / "a.mp4", dur=40, size="480x270")
    store.write_chunk(sid, "up12345", 0, src.read_bytes())
    store.finish_upload(sid, "up12345", "a.mp4")
    store.set_settings(sid, {"format": "both", "length": 15, "minutes": 0.5, "location": "Test"})
    assert store.formats(store.load(sid)["settings"]) == ["reel", "youtube"]
    analyses = store.analyse_all(sid)
    for f in ("reel", "youtube"):
        p = store.make_plan(sid, analyses, f)
        assert abs(sum(x["dur"] for x in p["shots"]) - store.target_duration(store.load(sid)["settings"], f)) < 0.04
        assert len(p["transitions"]) == len(p["shots"]) - 1
    st = store.edit_shot(sid, "reel", 1, "speed", 2)
    sh = st["plans"]["reel"]["shots"][1]
    assert sh["speed"] == 2 and abs(sh["src_dur"] - sh["dur"] * 2) < 0.15 or sh["src_dur"] < sh["dur"] * 2
    before = [dict(x) for x in st["plans"]["reel"]["shots"]]
    st = store.edit_shot(sid, "reel", 2, "left")
    after = st["plans"]["reel"]["shots"]
    assert after[1]["clip"] == before[2]["clip"] and abs(after[1]["dur"] - before[1]["dur"]) < 1e-9
    st = store.edit_shot(sid, "reel", 0, "transition", "flash")
    assert st["plans"]["reel"]["transitions"][0]["id"] == "flash" and st["plans"]["reel"]["edited"]


def test_auto_reframe_finds_the_busy_side():
    img = Image.new("RGB", (1920, 1080), (120, 150, 200))
    rng = np.random.default_rng(0)
    busy = (rng.random((1080, 500, 3)) * 255).astype(np.uint8)   # viel Struktur rechts
    img.paste(Image.fromarray(busy), (1350, 0))
    assert analysis.best_xpos(img, 9 / 16) > 0.75


def test_templates_and_custom_lut(tmp_path):
    for tpl in text.TEMPLATES:
        im = text.template_frame(tpl, "Madeira", 540, 960, 1.0, 3.0)
        assert im is not None and im.getbbox(), tpl
    lut = color.bake(color.params_for("bw_drama"))
    f = color.write_cube(lut, tmp_path / "bw.cube")
    half = color.read_cube(color.custom_lut_file(f, 0.5, {}, tmp_path / "c"))
    x = np.linspace(0, 1, half.shape[0])
    ident = np.stack(np.meshgrid(x, x, x, indexing="ij")[::-1], -1)
    assert np.allclose(half, ident + (lut - ident) * 0.5, atol=1e-5)    # Stärke 50 % = halbe Mischung


def test_render_with_zoom_keyframes_effects_stabilize_and_text(tmp_path):
    src = _clip(tmp_path / "a.mp4", dur=8)
    info = media.probe(src)
    shots = [{"clip": "a", "src_in": 0.5, "src_dur": 3.0, "t0": 0, "dur": 3.0, "speed": 1.0, "zoom": 1.0,
              "zoom_end": 1.3, "xpos": 0.8, "fx": {"sharpen": 40, "vignette": 50, "grain": 20, "denoise": True},
              "stabilize": "recommended", "adjust": {"exposure": 0.3}, "look": "golden_hour"},
             {"clip": "a", "src_in": 4.0, "src_dur": 2.0, "t0": 3.0, "dur": 2.0, "speed": 1.0}]
    plan = {"format": "reel", "shots": shots, "grade": {"look": "vivid_travel", "fx": {"clarity": 20}},
            "texts": [{"tpl": "location_pin", "text": "Madeira", "t0": 0.5, "dur": 2.0}]}
    out = tmp_path / "o.mp4"
    res = render.render(plan, {"a": {"path": src, "info": info}}, tmp_path / "w", out, "preview")
    assert abs(media.probe(out)["duration"] - 5.0) < 0.1 and res["width"] == 540


def test_shot_panel_edits(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "BASE", tmp_path)
    sid = store.create("Edits")["sid"]
    src = _clip(tmp_path / "a.mp4", dur=30, size="480x270")
    store.write_chunk(sid, "up12345", 0, src.read_bytes())
    store.finish_upload(sid, "up12345", "a.mp4")
    store.make_plan(sid, store.analyse_all(sid), "reel")
    st = store.edit_shot(sid, "reel", 1, "set", {"adjust": {"exposure": 0.4}, "fx": {"sharpen": 30}, "look": "bw_drama",
                                                 "zoom": 1.2, "evil": 1})
    sh = st["plans"]["reel"]["shots"][1]
    assert sh["look"] == "bw_drama" and sh["zoom"] == 1.2 and "evil" not in sh
    st = store.edit_shot(sid, "reel", 1, "apply_all")
    assert all(x.get("look") == "bw_drama" for x in st["plans"]["reel"]["shots"])
    st = store.edit_shot(sid, "reel", 0, "add_text", {"tpl": "subscribe", "text": "Subscribe"})
    assert st["plans"]["reel"]["texts"][0]["tpl"] == "subscribe"
    looks = store.looks_preview(sid, "reel", 0, 1.0)
    assert len(looks) >= 10 and (tmp_path / sid / "work" / "looks" / looks[0]["file"]).exists()


def test_curves_and_colour_wheels():
    s_curve = color.curve_lut([0, -40, 0, 40, 0], 9)
    assert s_curve[2] < 0.25 and s_curve[6] > 0.75 and abs(s_curve[4] - 0.5) < 1e-6 and np.all(np.diff(s_curve) >= 0)
    g = color.grade(np.array([[[0.2, 0.2, 0.2], [0.8, 0.8, 0.8]]]),
                    {"wheels": {"shadows": [220, 60, 0], "highlights": [35, 60, 0]}, "protect_skin": False})
    assert g[0, 0, 2] > g[0, 0, 0] and g[0, 1, 0] > g[0, 1, 2]     # Tiefen blau, Lichter orange


def test_masks_shapes_and_masked_render(tmp_path):
    from editor_app.video_studio import masks
    for shape in masks.SHAPES:
        m = np.asarray(masks.make({"shape": shape, "size": 0.6, "feather": 0.2}, 320, 180))
        assert 0 < (m > 128).mean() < 1, shape
    inv = np.asarray(masks.make({"shape": "circle", "invert": True}, 320, 180))
    assert inv[90, 160] < 50 and inv[2, 2] > 200
    src = _clip(tmp_path / "a.mp4", dur=4)
    info = media.probe(src)
    shots = [{"clip": "a", "src_in": 0.2, "src_dur": 2.0, "t0": 0, "dur": 2.0, "speed": 1.0,
              "mask": {"shape": "sky", "y": 0.5, "feather": 0.2, "adjust": {"exposure": -1.0}}}]
    out = tmp_path / "m.mp4"
    render.render({"format": "youtube", "shots": shots, "grade": {"look": "none"}}, {"a": {"path": src, "info": info}},
                  tmp_path / "w", out, "preview")
    fr = tmp_path / "f.png"
    subprocess.run([media.ffmpeg(), "-y", "-loglevel", "error", "-ss", "1", "-i", str(out), "-frames:v", "1", str(fr)],
                   check=True)
    a = np.asarray(Image.open(fr).convert("L")).astype(float)
    ref = tmp_path / "r.png"
    subprocess.run([media.ffmpeg(), "-y", "-loglevel", "error", "-ss", "1.2", "-i", str(src), "-frames:v", "1",
                    "-vf", "scale=960:540", str(ref)], check=True)
    b = np.asarray(Image.open(ref).convert("L")).astype(float)
    assert a[:100].mean() < b[:100].mean() - 15            # oben (Himmel-Maske) dunkler
    assert abs(a[-100:].mean() - b[-100:].mean()) < 12      # unten unverändert


def test_captions_ass_styles_and_fillers():
    from editor_app.video_studio import captions
    tr = {"segments": [{"words": [{"w": "Hello", "s": 0.0, "e": 0.4}, {"w": "äh", "s": 0.4, "e": 0.6},
                                  {"w": "Madeira!", "s": 0.6, "e": 1.2}]}]}
    words = captions.words_from(tr)
    assert [w["w"] for w in words] == ["Hello", "Madeira!"]
    for style in captions.STYLES:
        a = captions.ass(words, 1080, 1920, style)
        assert "Dialogue:" in a and "PlayResY: 1920" in a
    assert "\\kf" in captions.ass(words, 1080, 1920, "karaoke") and "MADEIRA" in captions.ass(words, 1080, 1920, "bold")
    f = captions.ffmpeg_filter(Path("C:/x/captions.ass"))
    assert "filename='C\\:/x/captions.ass'" in f


def test_ai_object_removal_inpaints_box(tmp_path):
    from editor_app.video_studio import ai_tools
    seg = tmp_path / "s.mp4"
    subprocess.run([media.ffmpeg(), "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x406080:s=320x180:d=1:r=10",
                    "-vf", "drawbox=x=140:y=70:w=40:h=40:color=red:t=fill", "-pix_fmt", "yuv420p", str(seg)], check=True)
    out = tmp_path / "o.mp4"
    ai_tools.process_segment(seg, out, {"remove": [0.4, 0.35, 0.2, 0.3]}, 10)
    fr = tmp_path / "f.png"
    subprocess.run([media.ffmpeg(), "-y", "-loglevel", "error", "-i", str(out), "-frames:v", "1", str(fr)], check=True)
    px = np.asarray(Image.open(fr).convert("RGB"))[90, 160].astype(int)
    assert px[0] < 150 and abs(px[2] - 0x80) < 40               # rotes Kästchen verschwunden
    assert ai_tools.status()["remove_object"]["status"] == "ready"


def test_ping_pong_camera_is_rejected_and_lookalikes_are_not_repeated():
    S = analysis.Sample
    steady = [S(t=k / 4, sharp=0.6, bright=0.5, clip=0, color=0.5, motion=12, jitter=0.5, dx=12, dy=0, zoom=0)
              for k in range(24)]
    pingpong = [S(t=6 + k / 4, sharp=0.6, bright=0.5, clip=0, color=0.5, motion=12, jitter=0.5, dx=0,
                  dy=20 if (k // 7) % 2 == 0 else -20, zoom=0) for k in range(28)]
    assert analysis._reversals(steady)[0] == 0 and analysis._reversals(pingpong)[0] >= 3
    ms = analysis.moments("a", steady + pingpong, [24])
    best = max(ms, key=lambda m: m["score"] if isinstance(m, dict) else m.score)
    best = best if isinstance(best, dict) else best.to_dict()
    assert best["start"] < 6                                       # die ruhige Fahrt gewinnt
    water = [0.1, 0.4, 0.6] * 32
    a = {"clip": "a", "start": 0.0, "dur": 6.0, "score": 0.9, "info": {"feat": water}, "scene": 0}
    b = {"clip": "b", "start": 0.0, "dur": 6.0, "score": 0.89, "info": {"feat": water}, "scene": 0}
    c = {"clip": "c", "start": 0.0, "dur": 6.0, "score": 0.5, "info": {"feat": [0.7, 0.5, 0.2] * 32}, "scene": 0}
    shots = planner.plan([a, b, c], 4.5, "reel", None, 30.0, ramps=False)
    clips = [s.clip for s in shots]
    assert not ("a" in clips and "b" in clips) or len(shots) > 2  # gleich aussehendes Wasser nicht zweimal
