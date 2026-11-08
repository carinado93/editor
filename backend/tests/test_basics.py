"""Schnelle Tests ohne Spracherkennungs-Modell (das wird durch eine Attrappe ersetzt)."""
import subprocess
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from editor_app import config, jobs, projects, transcribe

    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(projects, "PROJECTS_DIR", tmp_path)

    def fake_transcribe(wav, cache_dir, model_name="auto", language="auto", progress=None):
        progress and progress(1.0, "fertig")
        return {"language": "de", "model": "test", "device": "Prozessor", "duration": 2.0,
                "segments": [{"s": 0.1, "e": 1.0, "text": "Hallo Welt",
                              "words": [{"w": "Hallo", "s": 0.1, "e": 0.5, "p": 0.9},
                                        {"w": "Welt", "s": 0.6, "e": 1.0, "p": 0.4}]}]}

    monkeypatch.setattr(transcribe, "transcribe", fake_transcribe)
    from editor_app.main import app
    with TestClient(app) as c:
        yield c


def make_video(path, seconds=2):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=s=320x568:d={seconds}:r=30",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-shortest",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)], check=True)


def test_youtube_cuts_and_render(client, tmp_path, monkeypatch):
    from editor_app import transcribe

    def fake(wav, cache_dir, model_name="auto", language="auto", progress=None):
        words, t = [], 0.2
        for w in "Ich habe, Ich habe gelernt äh zu atmen.".split():
            words.append({"w": w, "s": round(t, 2), "e": round(t + 0.25, 2), "p": 0.9})
            t += 0.3
        words[-1]["s"], words[-1]["e"] = 3.0, 3.3  # lange Pause davor
        return {"language": "de", "model": "test", "device": "Prozessor", "duration": 4.0,
                "segments": [{"s": 0.2, "e": 3.3, "text": "", "words": words}]}

    monkeypatch.setattr(transcribe, "transcribe", fake)
    video = tmp_path / "clip.mp4"
    make_video(video, seconds=4)
    data = video.read_bytes()
    pid = client.post("/api/projects", json={"mode": "youtube", "filename": "clip.mp4", "size": len(data)}).json()["id"]
    client.put(f"/api/projects/{pid}/upload?offset=0", content=data)
    client.post(f"/api/projects/{pid}/upload/done")
    for _ in range(100):
        if client.get(f"/api/projects/{pid}").json()["status"] in ("fertig", "fehler"):
            break
        time.sleep(0.2)
    v = client.get(f"/api/projects/{pid}/cuts").json()
    flags = v["evaluation"]["flags"]
    assert flags[:2] == ["retake", "retake"] and flags[5] == "fuellwort"
    assert v["evaluation"]["new_duration"] < 3.0
    # Retake zurücknehmen und wieder rückgängig machen
    det = next(d for d in v["cutlist"]["detections"] if d["type"] == "retake")
    assert client.post(f"/api/projects/{pid}/cuts/toggle", json={"id": det["id"], "active": False}).json()["evaluation"]["flags"][0] is None
    assert client.post(f"/api/projects/{pid}/cuts/undo").json()["evaluation"]["flags"][0] == "retake"
    # Rendern
    client.post(f"/api/projects/{pid}/render", json={"quality": "original"})
    for _ in range(300):
        p = client.get(f"/api/projects/{pid}").json()
        if p["render"]["status"] in ("fertig", "fehler"):
            break
        time.sleep(0.2)
    assert p["render"]["status"] == "fertig", p["render"]["error"]
    out = p["exports"][0]
    assert abs(out["duration"] - v["evaluation"]["new_duration"]) < 0.1
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "csv=p=0",
                        str(tmp_path / pid / "export" / out["file"])], capture_output=True, text=True).stdout
    durs = [float(line.split(",")[1]) for line in r.strip().splitlines()]
    assert len(durs) == 2 and abs(durs[0] - durs[1]) < 0.05  # Bild und Ton gleich lang
    assert client.get(f"/api/projects/{pid}/export/{out['file']}").status_code == 200


def test_chunk_bounds_cut_in_quiet_place():
    from editor_app.transcribe import SR, chunk_bounds

    audio = np.full(SR * 25, 0.5, dtype=np.float32)
    audio[int(SR * 10.3):int(SR * 10.5)] = 0.0  # leise Stelle nahe der 10-s-Grenze
    bounds = chunk_bounds(audio, chunk_seconds=10, search=2)
    assert bounds[0][0] == 0 and bounds[-1][1] == len(audio)
    assert 10.3 * SR <= bounds[0][1] <= 10.5 * SR
    assert all(a < b for a, b in bounds)
    assert chunk_bounds(audio[: SR * 5], chunk_seconds=10) == [(0, SR * 5)]


def test_wrong_file_type_is_explained(client):
    r = client.post("/api/projects", json={"mode": "youtube", "filename": "notizen.pdf", "size": 10})
    assert r.status_code == 400
    assert "nicht unterstützt" in r.json()["fehler"]


def test_upload_in_chunks_and_process(client, tmp_path):
    video = tmp_path / "clip.mp4"
    make_video(video)
    data = video.read_bytes()
    p = client.post("/api/projects", json={"mode": "youtube", "filename": "clip.mp4", "size": len(data)}).json()
    pid = p["id"]
    half = len(data) // 2
    assert client.put(f"/api/projects/{pid}/upload?offset=0", content=data[:half]).json()["uploaded"] == half
    # falscher Offset: der Server sagt, wo es weitergeht
    assert client.put(f"/api/projects/{pid}/upload?offset=0", content=data[:10]).json()["uploaded"] == half
    assert client.put(f"/api/projects/{pid}/upload?offset={half}", content=data[half:]).json()["uploaded"] == len(data)
    client.post(f"/api/projects/{pid}/upload/done")
    for _ in range(100):
        p = client.get(f"/api/projects/{pid}").json()
        if p["status"] in ("fertig", "fehler"):
            break
        time.sleep(0.2)
    assert p["status"] == "fertig", p["error"]
    assert p["info"]["width"] == 320 and p["info"]["height"] == 568
    assert p["transcript"]["words"] == 2
    assert client.get(f"/api/projects/{pid}/transcript").json()["segments"][0]["text"] == "Hallo Welt"
    assert client.get(f"/api/projects/{pid}/vorschau.mp4").status_code == 200
    # Original unverändert
    assert (tmp_path / pid / "original.mp4").read_bytes() == data
    assert client.delete(f"/api/projects/{pid}").json()["ok"]
    assert client.get("/api/projects").json() == []
