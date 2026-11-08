import subprocess
import time

from editor_app import updater


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


def test_update_finds_new_version_and_restarts(tmp_path, monkeypatch):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(remote)], check=True)
    author = tmp_path / "author"
    subprocess.run(["git", "clone", "-q", str(remote), str(author)], check=True)
    for k, v in (("user.email", "t@t"), ("user.name", "t")):
        git(author, "config", k, v)
    (author / "a.txt").write_text("1")
    git(author, "add", "."), git(author, "commit", "-qm", "eins"), git(author, "push", "-q", "origin", "main")
    app = tmp_path / "app"
    subprocess.run(["git", "clone", "-q", str(remote), str(app)], check=True)
    monkeypatch.setattr(updater, "ROOT", app)
    updater._cache.update(t=0.0, data=None)
    assert updater.status(force=True)["available"] is False

    (author / "a.txt").write_text("2")
    git(author, "commit", "-qam", "zwei"), git(author, "push", "-q", "origin", "main")
    st = updater.status(force=True)
    assert st["available"] is True and st["behind"] == 1

    exits = []
    monkeypatch.setattr(updater.os, "_exit", lambda code: exits.append(code))
    res = updater.update_and_restart(busy=False)
    time.sleep(1.3)
    assert res["ok"] and (app / "a.txt").read_text() == "2" and exits == [updater.RESTART_CODE]


def test_update_refused_while_busy(monkeypatch, tmp_path):
    import pytest
    from editor_app.errors import UserError
    with pytest.raises(UserError):
        updater.update_and_restart(busy=True)


def test_zip_install_explains(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "ROOT", tmp_path)
    updater._cache.update(t=0.0, data=None)
    st = updater.status(force=True)
    assert st["can_update"] is False and "ZIP" in st["reason"]
