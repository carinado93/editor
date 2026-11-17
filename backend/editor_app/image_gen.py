"""KI-Hintergrundbilder für den Thumbnail-Maker – Anbieter austauschbar, eine Funktion: generate(prompt, w, h).

Anbieter (Einstellungen → Thumbnail backgrounds; Schlüssel nur in der Datei .env auf Carinas PC):
  pollinations  kostenlos, ohne Schlüssel (pollinations.ai, Modell Flux)
  higgsfield    Higgsfield Cloud API mit eigenem Schlüssel (cloud.higgsfield.ai, eigenes Guthaben)
  frame         ohne Internet: ein Bild aus ihrem eigenen Video, weichgezeichnet und abgedunkelt
Ohne Schlüssel oder offline fällt alles auf "frame" zurück, damit der Thumbnail-Maker immer funktioniert.
"""
from __future__ import annotations

import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from .errors import UserError

# Wird an jeden Prompt angehängt (Carinas Vorgabe)
PROMPT_SUFFIX = ("photorealistic, no people, no text, no logos, empty space at the top, 16:9, "
                 "soft natural light, high detail")

PROVIDERS = {
    "pollinations": {"label": "Free (pollinations.ai, no key)", "cost": "free", "needs_key": False},
    "higgsfield": {"label": "Higgsfield (your own API key)", "cost": "about $0.03 per image from your Higgsfield "
                   "API balance (check cloud.higgsfield.ai)", "needs_key": True},
    "frame": {"label": "No AI – a blurred frame from your video", "cost": "free", "needs_key": False},
}
HIGGSFIELD_MODEL = "bytedance/seedream/v4/text-to-image"
HIGGSFIELD_BASE = "https://api.higgsfield.ai"
LAST_ERROR = ""


def settings() -> dict:
    from . import publish
    prov = publish.env("IMAGE_PROVIDER", "pollinations")
    key = publish.env("HF_KEY") or (f"{publish.env('HF_API_KEY')}:{publish.env('HF_API_SECRET')}"
                                     if publish.env("HF_API_KEY") and publish.env("HF_API_SECRET") else "")
    return {"provider": prov if prov in PROVIDERS else "pollinations", "higgsfield_key_set": bool(key),
            "providers": PROVIDERS}


def save_settings(provider: str | None = None, higgsfield_key: str | None = None) -> dict:
    from . import publish
    lines = publish.ENV_FILE.read_text(encoding="utf-8").splitlines() if publish.ENV_FILE.exists() else []

    def put(k, v):
        nonlocal lines
        lines = [ln for ln in lines if not ln.startswith(k + "=")]
        if v:
            lines.append(f"{k}={v}")
    if provider in PROVIDERS:
        put("IMAGE_PROVIDER", provider)
    if higgsfield_key is not None and "…" not in higgsfield_key:
        k = higgsfield_key.strip()
        if k and ":" not in k:
            raise UserError("The Higgsfield key has two parts: KEY-ID:SECRET (both from cloud.higgsfield.ai → API keys).")
        put("HF_KEY", k)
    publish.ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return settings()


def cost_text(provider: str | None = None, n: int = 1) -> str:
    p = provider or settings()["provider"]
    c = PROVIDERS.get(p, PROVIDERS["frame"])["cost"]
    return f"{n} image{'s' if n > 1 else ''} · {c}"


def full_prompt(prompt: str) -> str:
    p = " ".join(prompt.strip().split())
    return f"{p}, {PROMPT_SUFFIX}" if p else PROMPT_SUFFIX


def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    return ImageOps.fit(img.convert("RGB"), (w, h), Image.LANCZOS)


def _get(url: str, timeout: float = 120, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "carina-video-editor", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _pollinations(prompt: str, w: int, h: int, seed: int) -> Image.Image:
    q = urllib.parse.urlencode({"width": w, "height": h, "nologo": "true", "seed": seed, "model": "flux",
                                "enhance": "false", "safe": "true"})
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?{q}"
    data = _get(url, timeout=180)
    return Image.open(io.BytesIO(data))


def _higgsfield(prompt: str, w: int, h: int, seed: int) -> Image.Image:
    from . import publish
    key = publish.env("HF_KEY") or (f"{publish.env('HF_API_KEY')}:{publish.env('HF_API_SECRET')}"
                                     if publish.env("HF_API_KEY") else "")
    if not key or ":" not in key:
        raise UserError("No Higgsfield key yet – add it in Settings → Thumbnail backgrounds.")
    h_ = {"Authorization": f"Key {key}", "Content-Type": "application/json", "User-Agent": "carina-video-editor"}
    body = json.dumps({"prompt": prompt, "resolution": "2K", "aspect_ratio": "16:9", "seed": seed}).encode()
    req = urllib.request.Request(f"{HIGGSFIELD_BASE}/{HIGGSFIELD_MODEL}", data=body, method="POST", headers=h_)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            sub = json.loads(r.read())
    except urllib.error.HTTPError as exc:
        raise UserError(f"Higgsfield answered {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}") from exc
    status_url = sub.get("status_url") or f"{HIGGSFIELD_BASE}/requests/{sub['request_id']}/status"
    t0 = time.time()
    while time.time() - t0 < 300:
        st = json.loads(_get(status_url, timeout=30, headers={"Authorization": f"Key {key}"}))
        s = st.get("status")
        if s == "completed":
            imgs = st.get("images") or (st.get("result") or {}).get("images") or []
            url = imgs[0]["url"] if imgs and isinstance(imgs[0], dict) else (imgs[0] if imgs else None)
            if not url:
                raise UserError("Higgsfield finished but sent no image.")
            return Image.open(io.BytesIO(_get(url, timeout=120)))
        if s in ("failed", "nsfw", "cancelled", "canceled"):
            raise UserError(f"Higgsfield could not make the image ({s}).")
        time.sleep(2)
    raise UserError("Higgsfield took too long (5 min).")


# Carinas Farben für "Meine Farben"-Hintergründe (je 2 kombiniert). Rosa = Altrosa aus ihren Meditations-Thumbnails.
BRAND_COLOURS = {
    "lilac": (201, 179, 236),   # #C9B3EC
    "pink": (232, 185, 183),    # #E8B9B7 dusty rose from her meditation thumbnails
    "yellow": (250, 232, 165),  # #FAE8A5 butter yellow
    "white": (254, 248, 243),   # #FEF8F3 warm white like her meditation thumbnails
}
COLOUR_PAIRS = [("lilac", "pink"), ("pink", "yellow"), ("yellow", "lilac")]   # Standard für die 3 Versionen
ALL_PAIRS = COLOUR_PAIRS + [("white", "pink"), ("lilac", "white")]


def colour_background(c1: str, c2: str, w: int = 1280, h: int = 720, seed: int = 0) -> Image.Image:
    """Weicher Verlauf aus zwei ihrer Farben + große, unscharfe Lichtkreise und feines Korn (kein Foto, keine KI).
    Oben geht der Verlauf in ein tiefes Pflaume über, damit der weiße Titel lesbar bleibt."""
    import numpy as np
    a, b = (np.array(BRAND_COLOURS[c], np.float32) for c in (c1, c2))
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    t = np.clip((xx / w) * 0.75 + (yy / h) * 0.25, 0, 1)[..., None]
    t = t * t * (3 - 2 * t)
    img = a * (1 - t) + b * t
    for _ in range(6):  # Lichtkreise in beiden Farben + Weiß
        cx, cy = rng.uniform(0, w), rng.uniform(h * 0.25, h)
        r = rng.uniform(0.18, 0.4) * w
        col = [a, b, np.array([255, 250, 245], np.float32)][rng.integers(0, 3)]
        m = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * (r / 2) ** 2)))[..., None] * rng.uniform(0.15, 0.32)
        img = img * (1 - m) + col * m
    plum = np.array([74, 52, 110], np.float32)
    top = np.clip(1 - yy / (h * 0.5), 0, 1)[..., None] ** 1.5 * 0.58
    img = img * (1 - top) + plum * top
    img += rng.normal(0, 2.2, img.shape[:2])[..., None]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def frame_background(frame: Image.Image | None, w: int, h: int, seed: int = 0) -> Image.Image:
    """Ohne KI: ihr eigenes Videobild, stark weichgezeichnet und etwas dunkler (nur Hintergrund, nicht sie selbst).
    Je nach seed ein anderer Ausschnitt, damit die 3 Versionen sich unterscheiden."""
    if frame is None:
        return Image.new("RGB", (w, h), (70, 58, 92))
    k = (seed // 7) % 3
    if k:
        fw, fh = frame.size
        z = 0.62
        cw, ch = int(fw * z), int(fh * z)
        x0 = 0 if k == 1 else fw - cw
        frame = frame.crop((x0, 0, x0 + cw, ch))
    bg = _cover(frame, w, h).filter(ImageFilter.GaussianBlur(28))
    return ImageEnhance.Brightness(bg).enhance(0.72)


def generate(prompt: str, w: int = 1280, h: int = 720, *, seed: int = 0, provider: str | None = None,
             fallback_frame: Image.Image | None = None) -> tuple[Image.Image, str]:
    """Ein Hintergrundbild w×h. Gibt (Bild, tatsächlich genutzter Anbieter) zurück; bei Fehler/offline → Videobild."""
    prov = provider or settings()["provider"]
    text = full_prompt(prompt)
    if prov == "pollinations":
        try:
            return _cover(_pollinations(text, w, h, seed), w, h), "pollinations"
        except Exception:  # noqa: BLE001 – offline, gesperrt, Fehler: Ersatz statt Abbruch
            pass
    elif prov == "higgsfield":
        try:
            return _cover(_higgsfield(text, w, h, seed), w, h), "higgsfield"
        except Exception as exc:  # noqa: BLE001 – kein Schlüssel / kein Guthaben / offline → Videobild
            global LAST_ERROR
            LAST_ERROR = str(exc)
    return frame_background(fallback_frame, w, h, seed), "frame"
