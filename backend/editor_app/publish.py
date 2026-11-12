"""Brief-Karussells an Claude übergeben: Bilder + Auftrags-Datei ins GitHub-Repo carinado93/app
(Branch carousel-media, Ordner media/letters/…). Claude plant dann mit Carinas Metricool-Verbindung und erstellt
Bilder mit ihrer Canva-Verbindung – die App selbst braucht dafür keine Metricool-API und keinen Canva-Zugang.

Zugangsdaten nur in der Datei `.env` auf Carinas PC (nie im Code, nicht im Git):
  GITHUB_TOKEN          Fine-grained Token mit "Contents: Read and write" für carinado93/app
  GITHUB_MEDIA_REPO     (optional) Standard carinado93/app
  GITHUB_MEDIA_BRANCH   (optional) Standard carousel-media
"""
from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .config import ROOT
from .errors import UserError

ENV_FILE = ROOT / ".env"
KEYS = ("GITHUB_TOKEN", "GITHUB_MEDIA_REPO", "GITHUB_MEDIA_BRANCH")
SECRET = {"GITHUB_TOKEN"}
REPO_DEFAULT, BRANCH_DEFAULT = "carinado93/app", "carousel-media"


# ---------------------------------------------------------------- .env

def _env_file() -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def env(key: str, default: str = "") -> str:
    return _env_file().get(key) or os.environ.get(key, "") or default


def settings() -> dict:
    """Für die Einstellungen-Seite: was ist eingetragen (Geheimnisse nur maskiert)."""
    out = {}
    for k in KEYS:
        v = env(k)
        out[k] = (f"{v[:4]}…{v[-4:]}" if len(v) > 10 else ("set" if v else "")) if k in SECRET else v
    return out


def save_settings(values: dict) -> dict:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    for k, v in values.items():
        if k not in KEYS or v is None:
            continue
        v = str(v).strip()
        if k in SECRET and (not v or "…" in v):  # maskierter Wert zurückgeschickt → nicht überschreiben
            continue
        if re.search(r"[\r\n]", v):
            raise UserError("Please paste the value without line breaks.")
        lines = [ln for ln in lines if not ln.startswith(k + "=")]
        if v:
            lines.append(f"{k}={v}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return settings()


def _http(method: str, url: str, headers: dict, body: dict | bytes | None = None, timeout: float = 60):
    data = json.dumps(body).encode() if isinstance(body, dict) else body
    req = urllib.request.Request(url, data=data, method=method, headers={"User-Agent": "editor-app", **headers})
    if isinstance(body, dict):
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise UserError(f"{urllib.parse.urlparse(url).netloc} answered {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise UserError(f"Could not reach {urllib.parse.urlparse(url).netloc}: {exc.reason}") from exc


# ---------------------------------------------------------------- GitHub (carinado93/app, Branch carousel-media)

def _gh():
    token = env("GITHUB_TOKEN")
    if not token:
        raise UserError("Please add your GitHub token once in Settings → Publishing (it stays only on your PC). "
                        "The app needs it to put the slides into carinado93/app for Claude.")
    repo = env("GITHUB_MEDIA_REPO", REPO_DEFAULT)
    branch = env("GITHUB_MEDIA_BRANCH", BRANCH_DEFAULT)
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    return f"https://api.github.com/repos/{repo}", repo, branch, h


def upload(files: list[tuple[bytes, str]], message: str) -> tuple[str, list[str]]:
    """Mehrere Dateien in EINEM Commit hochladen. Gibt (commit, öffentliche Links) zurück –
    die Links zeigen auf den Commit und bleiben dadurch für immer gleich."""
    api, repo, branch, h = _gh()
    ref = _http("GET", f"{api}/git/ref/heads/{branch}", h)
    base_commit = ref["object"]["sha"]
    base_tree = _http("GET", f"{api}/git/commits/{base_commit}", h)["tree"]["sha"]
    tree = []
    for data, path in files:
        blob = _http("POST", f"{api}/git/blobs", h, {"content": base64.b64encode(data).decode(), "encoding": "base64"})
        tree.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    new_tree = _http("POST", f"{api}/git/trees", h, {"base_tree": base_tree, "tree": tree})["sha"]
    commit = _http("POST", f"{api}/git/commits", h, {"message": message, "tree": new_tree, "parents": [base_commit]})
    _http("PATCH", f"{api}/git/refs/heads/{branch}", h, {"sha": commit["sha"], "force": False})
    return commit["sha"], [f"https://raw.githubusercontent.com/{repo}/{commit['sha']}/{path}" for _, path in files]


def list_dir(path: str) -> list[dict]:
    """Dateien in einem Ordner des Branches (leer, wenn es ihn noch nicht gibt)."""
    api, _, branch, h = _gh()
    try:
        res = _http("GET", f"{api}/contents/{urllib.parse.quote(path)}?ref={branch}", h)
    except UserError as exc:
        if " 404" in str(exc):
            return []
        raise
    return res if isinstance(res, list) else []


def read_file(path: str) -> bytes | None:
    api, _, branch, h = _gh()
    try:
        res = _http("GET", f"{api}/contents/{urllib.parse.quote(path)}?ref={branch}", h)
    except UserError as exc:
        if " 404" in str(exc):
            return None
        raise
    if isinstance(res, dict) and res.get("content"):
        return base64.b64decode(res["content"])
    if isinstance(res, dict) and res.get("download_url"):  # große Dateien (> 1 MB)
        with urllib.request.urlopen(res["download_url"], timeout=60) as r:
            return r.read()
    return None


def repo_branch() -> tuple[str, str]:
    return env("GITHUB_MEDIA_REPO", REPO_DEFAULT), env("GITHUB_MEDIA_BRANCH", BRANCH_DEFAULT)
