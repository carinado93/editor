from editor_app import clips


def words_from(text, gap_after=None):
    gap_after = gap_after or {}
    out, t = [], 0.5
    for i, w in enumerate(text.split()):
        out.append({"w": w, "s": round(t, 2), "e": round(t + 0.35, 2), "p": 0.9})
        t += 0.4 + gap_after.get(i, 0)
    return out


TEXT = ("Rest did not fix my burnout. I slept more and felt worse. The real problem was saying yes to everything. "
        "Boundaries changed it. Start with one small no this week. That is enough for now.")


def test_sentences_and_exact_durations():
    w = words_from(TEXT)
    sent = clips.sentences(w, [None] * len(w))
    assert [s["id"] for s in sent] == [1, 2, 3, 4, 5, 6] and sent[0]["text"] == "Rest did not fix my burnout."
    clips.exact_durations(w, [None] * len(w), sent, 60)
    assert all(s["dur"] > 0 for s in sent)


def test_validate_reorders_parts_and_avoids_overlap():
    w = words_from(TEXT * 2)
    flags = [None] * len(w)
    sent = clips.sentences(w, flags)
    raw = {"clips": [{"title": "t", "hook_text": "Rest did not fix my *burnout*", "parts": [[3], [1, 2], [4, 5, 6, 7, 8]],
                      "why": "w", "caption": "c", "hashtags": ["#burnout"], "shorts_title": "s"}]}
    out = clips.validate(raw, w, flags, sent, 120, "en")
    c = out[0]
    assert c["segments"][0][0] > c["segments"][1][0]  # Hook (Satz 3) kommt zuerst, obwohl er später im Video ist
    used = sorted(c["segments"])
    assert all(a[1] <= b[0] + 1e-6 for a, b in zip(used, used[1:]))  # nichts doppelt
    assert len(c["hashtags"]) == 5 and c["status"] == "vorschlag"


def test_too_short_is_rejected():
    import pytest
    from editor_app.errors import UserError
    w = words_from(TEXT)
    sent = clips.sentences(w, [None] * len(w))
    with pytest.raises(UserError):
        clips.validate({"clips": [{"title": "t", "hook_text": "h", "parts": [[1]], "why": "", "caption": "",
                                   "hashtags": [], "shorts_title": ""}]}, w, [None] * len(w), sent, 60, "en")


def test_landscape_clip_has_bars_and_right_length(tmp_path):
    import subprocess
    from editor_app import media, render
    src = tmp_path / "quer.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0xC08060:s=640x360:d=10:r=30",
                    "-f", "lavfi", "-i", "sine=frequency=300:duration=10", "-shortest", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", str(src)], check=True)
    info = media.probe(src)
    w = [{"w": "Hallo", "s": 6.1, "e": 6.5, "p": 1}, {"w": "Welt.", "s": 1.1, "e": 1.5, "p": 1}]
    out = tmp_path / "clip.mp4"
    res = render.render_clip(src, info, [[6.0, 8.0], [1.0, 3.0]], out, tmp_path / "w", w, [None, None],
                             "Ein *Hook*", None, None)
    assert abs(res["duration"] - 4.0) < 0.1
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height",
                            "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip()
    assert probe == "1080,1920"
    # oben schwarzer Balken, Mitte unten Video (Farbe), ganz unten wieder schwarz
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "2", "-i", str(out), "-frames:v", "1", "-vf", "scale=1:96",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
    assert raw[2] < 30 and raw[int(96 * 1000 / 1920)] > 60 and raw[-2] < 30
