"""Effekte: frühere Stände wiederherstellen, Claude überschreibt selbst hinzugefügte Effekte nicht."""
import copy

from editor_app import cutstore


def _setup(monkeypatch):
    db = {"cl": {"overlays": [], "history": [], "settings": {}}}
    monkeypatch.setattr(cutstore, "load", lambda pid: copy.deepcopy(db["cl"]))
    monkeypatch.setattr(cutstore, "_save", lambda pid, cl: db.__setitem__("cl", copy.deepcopy(cl)))
    monkeypatch.setattr(cutstore, "_transcript", lambda pid: {"duration": 60, "segments": []})
    monkeypatch.setattr(cutstore, "view", lambda pid, cl=None: {"cutlist": copy.deepcopy(db["cl"])})
    return db


def fx(i, t, title, claude=False):
    return {"id": f"fx-{1000 + i}-{i}" if claude else f"fx-{1000 + i}", "kind": "fx", "type": "bigwords",
            "place": "side", "on": True, "title": title, "text": title, "start": t, "end": t + 3}


def test_versions_restore_and_claude_keeps_own_effects(monkeypatch):
    db = _setup(monkeypatch)
    cutstore.set_overlays("p", [fx(1, 0, "Guten Morgen")])
    cutstore.set_effects("p", [fx(2, 10, "Claude A", claude=True)])
    titles = [o["title"] for o in db["cl"]["overlays"]]
    assert "Guten Morgen" in titles and "Claude A" in titles          # eigener Effekt bleibt
    cutstore.set_effects("p", [fx(3, 20, "Claude B", claude=True)])
    titles = [o["title"] for o in db["cl"]["overlays"]]
    assert titles.count("Guten Morgen") == 1 and "Claude A" not in titles and "Claude B" in titles
    vs = cutstore.fx_versions("p")
    assert vs and any("Claude A" in " ".join(v["summary"]) for v in vs)
    k = next(i for i, v in enumerate(vs) if "Claude A" in " ".join(v["summary"]))
    cutstore.restore_fx_version("p", k)
    assert "Claude A" in [o["title"] for o in db["cl"]["overlays"]]
    n = len(db["cl"]["fx_versions"])
    cutstore.undo("p")
    assert len(db["cl"]["fx_versions"]) == n                           # Versionen bleiben beim Rückgängig
