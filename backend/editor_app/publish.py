"""Veröffentlichen der Brief-Karussells: Bilder öffentlich machen (GitHub-Repo carinado93/app, Ordner media/)
und in Metricool planen.

Alle Zugangsdaten stehen nur in der Datei `.env` auf Carinas PC (nie im Code, nicht im Git):
  GITHUB_TOKEN          Fine-grained Token mit "Contents: Read and write" für carinado93/app
  GITHUB_MEDIA_REPO     (optional) Standard carinado93/app
  GITHUB_MEDIA_BRANCH   (optional) Standard main
  METRICOOL_USER_TOKEN  Metricool → Account settings → API
  METRICOOL_USER_ID     Metricool userId
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
KEYS = ("GITHUB_TOKEN", "GITHUB_MEDIA_REPO", "GITHUB_MEDIA_BRANCH", "METRICOOL_USER_TOKEN", "METRICOOL_USER_ID")
SECRET = {"GITHUB_TOKEN", "METRICOOL_USER_TOKEN"}


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


# ---------------------------------------------------------------- GitHub: Bilder öffentlich machen

def upload_media(files: list[tuple[Path, str]], message: str) -> list[str]:
    """Alle JPGs in EINEM Commit nach carinado93/app (media/…) und die öffentlichen Links zurückgeben.
    files: (lokale Datei, Pfad im Repo). Die Links zeigen auf den Commit, bleiben also für immer gleich."""
    token = env("GITHUB_TOKEN")
    if not token:
        raise UserError("To schedule, the slides must be online first. Please add your GitHub token in "
                        "Settings → Publishing (it stays only on your PC).")
    repo = env("GITHUB_MEDIA_REPO", "carinado93/app")
    branch = env("GITHUB_MEDIA_BRANCH", "main")
    api = f"https://api.github.com/repos/{repo}"
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    ref = _http("GET", f"{api}/git/ref/heads/{branch}", h)
    base_commit = ref["object"]["sha"]
    base_tree = _http("GET", f"{api}/git/commits/{base_commit}", h)["tree"]["sha"]
    tree = []
    for local, path in files:
        blob = _http("POST", f"{api}/git/blobs", h,
                     {"content": base64.b64encode(local.read_bytes()).decode(), "encoding": "base64"})
        tree.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    new_tree = _http("POST", f"{api}/git/trees", h, {"base_tree": base_tree, "tree": tree})["sha"]
    commit = _http("POST", f"{api}/git/commits", h, {"message": message, "tree": new_tree, "parents": [base_commit]})
    _http("PATCH", f"{api}/git/refs/heads/{branch}", h, {"sha": commit["sha"], "force": False})
    return [f"https://raw.githubusercontent.com/{repo}/{commit['sha']}/{path}" for _, path in files]


# ---------------------------------------------------------------- Metricool

def schedule_instagram(blog_id: int, media: list[str], text: str, when: str) -> dict:
    """Ein Instagram-Karussell in Metricool planen (genau die info-Struktur aus Carinas Vorgabe)."""
    token, user = env("METRICOOL_USER_TOKEN"), env("METRICOOL_USER_ID")
    if not token or not user:
        raise UserError("Please add your Metricool user token and userId in Settings → Publishing.")
    info = {
        "autoPublish": True, "draft": False, "descendants": [], "firstCommentText": "",
        "hasNotReadNotes": False,
        "media": media,
        "mediaAltText": [],
        "providers": [{"network": "instagram"}],
        "publicationDate": {"dateTime": when[:19], "timezone": "Europe/Berlin"},
        "shortener": False, "smartLinkData": {"ids": []},
        "text": text,
        "instagramData": {"type": "POST", "collaborators": [], "carouselTags": {}, "showReelOnFeed": True,
                          "isAiGenerated": False},
    }
    q = urllib.parse.urlencode({"blogId": blog_id, "userId": user})
    res = _http("POST", f"https://app.metricool.com/api/v2/scheduler/posts?{q}", {"X-Mc-Auth": token}, info)
    data = res.get("data", res) if isinstance(res, dict) else {}
    return {"id": data.get("id") if isinstance(data, dict) else None,
            "planner": f"https://app.metricool.com/planner?blogId={blog_id}"}
