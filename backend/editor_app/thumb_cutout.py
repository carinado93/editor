"""Clean cut-out for thumbnails (Carina's rules from 26 Nov 2026 – white edges must never happen again).

1. Mask: IS-Net "isnet-general-use" (the same ONNX model and pre-processing rembg uses) + alpha matting
   (pymatting closed-form, rembg's defaults: foreground > 240, background < 10, erode 10 px).
2. Cleanup, ALWAYS:
   a) holes: small enclosed holes (< 4000 px) are filled, big enclosed holes (gap between hand, arm and hair) are
      background → alpha 0
   b) leftover background: bright (> 200), unsaturated (< 0.12) pixels within 40 px of the outer edge in the upper
      body → alpha 0; the solid inside (alpha > 0.95 eroded 40 px) is protected. Extra guard (so her white blazer /
      feather cuffs are not eaten): the pixel must also look like the photo's background next to it.
   c) alpha: open 5, erode 3, largest piece only, head: close 15 + open 9, Gaussian 7; lower body: elliptical
      open/close 21 + Gaussian sigma 3.5
   d) colour decontamination: edge pixels take the colour of the solid inside (normalised blur 51 px);
      edge pixels brighter than 205 are replaced completely. The inside (face, photo) is never changed.
3. Check: no pixel with alpha > 0.1 within 6 px of the edge may be brighter than 220 with saturation < 0.08
   (= white fringe). Pixels whose solid-inside colour is itself that white (her white blazer) do not count.
   If it fails: cleanup again, stronger; still failing → warning.
All pixel sizes are meant at the working size (long side 1600 px); the photo is processed at that size.
"""
from __future__ import annotations

import urllib.request

import numpy as np
from PIL import Image

from .config import MODELS_DIR

ISNET_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx"
WORK = 1600
_SESSION = None


# ---------------------------------------------------------------- model

def _session():
    global _SESSION
    if _SESSION is None:
        import onnxruntime as ort
        p = MODELS_DIR / "isnet-general-use.onnx"
        if not p.exists():
            tmp = p.with_suffix(".part")
            urllib.request.urlretrieve(ISNET_URL, tmp)   # ~170 MB, only the first time
            tmp.replace(p)
        prov = [x for x in ("CUDAExecutionProvider", "CPUExecutionProvider") if x in ort.get_available_providers()]
        _SESSION = ort.InferenceSession(str(p), providers=prov)
    return _SESSION


def isnet_mask(img: Image.Image) -> np.ndarray:
    """0..1 mask like rembg's isnet-general-use session (1024², mean 0.5, std 1.0, min-max normalised)."""
    s = _session()
    x = np.asarray(img.convert("RGB").resize((1024, 1024), Image.LANCZOS)).astype(np.float32)
    x = x / max(1.0, float(x.max()))
    x = (x - 0.5) / 1.0
    x = x.transpose(2, 0, 1)[None]
    out = s.run(None, {s.get_inputs()[0].name: x})[0][0, 0]
    mi, ma = float(out.min()), float(out.max())
    out = (out - mi) / max(1e-6, ma - mi)
    m = Image.fromarray((out * 255).astype(np.uint8)).resize(img.size, Image.LANCZOS)
    return np.asarray(m).astype(np.float32) / 255


def alpha_matting(rgb: np.ndarray, mask: np.ndarray, fg_t: int = 240, bg_t: int = 10, erode: int = 10) -> np.ndarray:
    """rembg's alpha_matting_cutout: trimap from the mask, closed-form matting (pymatting)."""
    import cv2
    m8 = (mask * 255).astype(np.uint8)
    k = np.ones((3, 3), np.uint8)
    fg = cv2.erode((m8 > fg_t).astype(np.uint8), k, iterations=erode)
    bg = cv2.erode((m8 < bg_t).astype(np.uint8), k, iterations=erode)
    tri = np.full(m8.shape, 0.5, np.float64)
    tri[fg > 0] = 1.0
    tri[bg > 0] = 0.0
    if not (tri == 0.5).any():
        return mask
    try:
        from pymatting import estimate_alpha_cf
        a = estimate_alpha_cf(rgb.astype(np.float64) / 255, tri)
    except Exception:  # noqa: BLE001 – matting failed (e.g. huge unknown band): keep the model mask
        return mask
    return np.clip(a, 0, 1).astype(np.float32)


# ---------------------------------------------------------------- cleanup

def _hsv(rgb: np.ndarray):
    import cv2
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    return hsv[..., 1].astype(np.float32) / 255, hsv[..., 2].astype(np.float32)


def _ellipse(n: int):
    import cv2
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (n, n))


def _inside_colour(rgb: np.ndarray, alpha: np.ndarray, radius: int = 51) -> np.ndarray:
    """Normalised blur of the solid inside colours: what colour 'she' has near each edge pixel."""
    import cv2
    inner = (alpha > 0.95).astype(np.float32)
    k = radius | 1
    num = cv2.GaussianBlur(rgb.astype(np.float32) * inner[..., None], (k, k), 0)
    den = cv2.GaussianBlur(inner, (k, k), 0)[..., None]
    # far from any inside pixel: widen the search so every edge pixel gets a colour
    wide_num = cv2.GaussianBlur(rgb.astype(np.float32) * inner[..., None], (k * 3 | 1, k * 3 | 1), 0)
    wide_den = cv2.GaussianBlur(inner, (k * 3 | 1, k * 3 | 1), 0)[..., None]
    col = np.where(den > 1e-3, num / np.maximum(den, 1e-6), wide_num / np.maximum(wide_den, 1e-6))
    return np.clip(col, 0, 255)


def fill_holes(alpha: np.ndarray, small: int = 4000) -> tuple[np.ndarray, int, int]:
    """a) Enclosed holes: small → filled, big → background (alpha 0). Returns (alpha, n_filled, n_cleared)."""
    import cv2
    a = alpha.copy()
    hole = (a < 0.5).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(hole, 4)
    h, w = a.shape
    filled = cleared = 0
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if x == 0 or y == 0 or x + bw >= w or y + bh >= h:
            continue   # touches the image border = real background
        sel = lab == i
        if area < small:
            a[sel] = 1.0
            filled += 1
        else:
            a[sel] = 0.0
            cleared += 1
    return a, filled, cleared


def remove_leftover(rgb: np.ndarray, alpha: np.ndarray, face_px, bright: float = 200, sat: float = 0.12,
                    band: int = 40) -> np.ndarray:
    """b) Bright, grey background left on hair/hand/sleeve near the outer edge → transparent."""
    import cv2
    s, v = _hsv(rgb)
    solid = alpha > 0.5
    dist = cv2.distanceTransform(solid.astype(np.uint8), cv2.DIST_L2, 5)
    near_edge = solid & (dist <= band)
    protect = cv2.erode((alpha > 0.95).astype(np.uint8), _ellipse(81)) > 0     # 40 px each side
    h, w = alpha.shape
    ys = np.nonzero(solid.any(axis=1))[0]
    top, bot = (int(ys[0]), int(ys[-1])) if len(ys) else (0, h)
    if face_px:
        fh = face_px[3] - face_px[1]
        upper_end = int(face_px[3] + 1.4 * fh)
    else:
        upper_end = top + int((bot - top) * 0.55)
    upper = np.zeros_like(solid)
    upper[:max(0, min(h, upper_end))] = True
    # looks like the photo's background next to it? (normalised blur of the clear background)
    bgm = (alpha < 0.05).astype(np.float32)
    num = cv2.GaussianBlur(rgb.astype(np.float32) * bgm[..., None], (101, 101), 0)
    den = cv2.GaussianBlur(bgm, (101, 101), 0)[..., None]
    bgcol = num / np.maximum(den, 1e-6)
    like_bg = (np.abs(rgb.astype(np.float32) - bgcol).mean(axis=2) < 28) | (den[..., 0] < 1e-3)
    kill = near_edge & upper & ~protect & (v > bright) & (s < sat) & like_bg
    # soft light glow around hair/head: semi-transparent, clearly lighter and greyer than her inside next to it
    _, vin = _hsv(_inside_colour(rgb, alpha).astype(np.uint8))
    glow = near_edge & upper & ~protect & (alpha < 0.9) & (v > vin + 25) & (s < 0.2) & (v > 150)
    out = alpha.copy()
    out[kill | glow] = 0.0
    return out


def smooth_alpha(alpha: np.ndarray, face_px, erode: int = 3) -> np.ndarray:
    """c) Morphology on the matte: no dots, no stairs, smooth edges."""
    import cv2
    a = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, _ellipse(5))
    a = cv2.erode(a, _ellipse(erode * 2 + 1) if erode > 1 else np.ones((3, 3), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats((a > 0.3).astype(np.uint8), 8)
    if n > 2:
        keep = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        region = cv2.dilate((lab == keep).astype(np.uint8), _ellipse(5))
        a = a * region
    h = a.shape[0]
    if face_px:
        split = int(min(h, face_px[3] + 0.6 * (face_px[3] - face_px[1])))
    else:
        ys = np.nonzero((a > 0.5).any(axis=1))[0]
        split = int(ys[0] + (ys[-1] - ys[0]) * 0.35) if len(ys) else h // 3
    head = cv2.morphologyEx(a, cv2.MORPH_CLOSE, _ellipse(15))
    head = cv2.morphologyEx(head, cv2.MORPH_OPEN, _ellipse(9))
    head = cv2.GaussianBlur(head, (7, 7), 0)
    low = (a > 0.5).astype(np.float32)          # body: firm edge (no see-through blotches on chair/sleeve)
    low = cv2.morphologyEx(low, cv2.MORPH_OPEN, _ellipse(21))
    low = cv2.morphologyEx(low, cv2.MORPH_CLOSE, _ellipse(21))
    low = cv2.GaussianBlur(low, (0, 0), 3.5)
    # soft hand-over between head and body area (no visible seam)
    wgt = np.clip((np.arange(h, dtype=np.float32) - (split - 40)) / 80, 0, 1)[:, None]
    return np.clip(head * (1 - wgt) + low * wgt, 0, 1)


def decontaminate(rgb: np.ndarray, alpha: np.ndarray, white: float = 205) -> np.ndarray:
    """d) Edge pixels take the colour of her solid inside; very bright edge pixels are replaced completely."""
    import cv2
    col = _inside_colour(rgb, alpha)
    base = rgb.astype(np.float32)
    try:   # first un-mix the background out of the semi-transparent pixels (F from I = aF + (1-a)B)
        from pymatting import estimate_foreground_ml
        base = np.clip(estimate_foreground_ml(rgb.astype(np.float64) / 255, alpha.astype(np.float64)) * 255, 0, 255)
    except Exception:  # noqa: BLE001
        pass
    edge = (alpha < 0.98) & (alpha > 0.0)
    ring = cv2.dilate((alpha < 0.5).astype(np.uint8), _ellipse(13)) > 0   # 6 px band at the outline
    edge |= ring & (alpha > 0)
    _, v = _hsv(rgb)
    _, vb = _hsv(base.astype(np.uint8))
    wgt = np.clip(1.5 * (1 - alpha), 0, 1)
    wgt = np.where((v > white) | (vb > white), 1.0, wgt)
    wgt = np.where(edge, wgt, 0.0)[..., None]
    out = np.where(edge[..., None], base * (1 - wgt) + col * wgt, rgb.astype(np.float32))   # inside untouched
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


def fringe_pixels(rgb: np.ndarray, alpha: np.ndarray, band: int = 6) -> int:
    """Automatic test: white-fringe pixels (alpha > 0.1, ≤ 6 px from the edge, > 220 bright, saturation < 0.08)."""
    import cv2
    s, v = _hsv(rgb)
    vis = alpha > 0.1
    out_d = cv2.distanceTransform(vis.astype(np.uint8), cv2.DIST_L2, 5)
    near = vis & (out_d <= band)
    bad = near & (v > 220) & (s < 0.08)
    if not bad.any():
        return 0
    # her own white clothes are not fringe: the solid inside next to it is just as white
    col = _inside_colour(rgb, alpha)
    cs, cv = _hsv(col.astype(np.uint8))
    own_white = (cv > 215) & (cs < 0.10)
    return int((bad & ~own_white).sum())


def clean(rgb: np.ndarray, alpha: np.ndarray, face_px=None, strength: int = 0) -> tuple[np.ndarray, np.ndarray, dict]:
    """Run a)–d). strength 1/2 = stronger cleanup after a failed check."""
    import cv2
    bright = (200, 188, 175)[strength]
    band = (40, 55, 70)[strength]
    erode = (3, 4, 6)[strength]
    a, n_fill, n_clear = fill_holes(alpha)
    a = remove_leftover(rgb, a, face_px, bright=bright, band=band)
    a = smooth_alpha(a, face_px, erode=erode)
    a, _, _ = fill_holes(a)            # the morphology can open new tiny holes
    n, lab, stats, _ = cv2.connectedComponentsWithStats((a > 0.3).astype(np.uint8), 8)
    if n > 2:                          # only the largest piece – no floating bits of chair or wall
        keep = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        a = a * cv2.dilate((lab == keep).astype(np.uint8), _ellipse(9))
    a = np.where(a < 0.02, 0.0, a).astype(np.float32)
    col = decontaminate(rgb, a, white=(205, 195, 185)[strength])
    return col, a, {"holes_filled": n_fill, "holes_cleared": n_clear}


def cutout(photo: Image.Image, face: list[float] | None = None, segmenter=None) -> tuple[Image.Image, Image.Image, dict]:
    """Photo → (RGBA at photo size with clean edges, alpha mask L, report). face = box 0..1 in the photo."""
    img = photo.convert("RGB")
    sc = min(1.0, WORK / max(img.size))
    work = img.resize((round(img.width * sc), round(img.height * sc)), Image.LANCZOS) if sc < 1 else img
    rgb = np.asarray(work)
    try:
        m = isnet_mask(work)
        engine = "isnet"
    except Exception:  # noqa: BLE001 – model not available (offline first start): MediaPipe person mask
        from . import fx
        seg = segmenter or fx.Segmenter()
        try:
            m = np.asarray(seg.mask(work)).astype(np.float32) / 255
        finally:
            if segmenter is None:
                seg.close()
        engine = "mediapipe"
    a = alpha_matting(rgb, m)
    fpx = None
    if face:
        fpx = (face[0] * work.width, face[1] * work.height, face[2] * work.width, face[3] * work.height)
    report = {"engine": engine, "tries": 0, "fringe": None, "warnings": []}
    for strength in range(3):
        col, alpha, info = clean(rgb, a, fpx, strength)
        report.update(info)
        report["tries"] = strength + 1
        report["fringe"] = fringe_pixels(col, alpha)
        if report["fringe"] == 0:
            break
    if report["fringe"]:
        report["warnings"].append(f"{report['fringe']} light pixels are still at the edge of the cut-out – "
                                  "please check the edge and use the eraser.")
    a8 = Image.fromarray((alpha * 255).astype(np.uint8))
    c8 = Image.fromarray(col)
    if sc < 1:   # back to photo size: alpha smooth, colours only replaced where the edge is
        a8 = a8.resize(img.size, Image.LANCZOS)
        cbig = c8.resize(img.size, Image.LANCZOS)
        edge = Image.fromarray((((alpha < 0.98) & (alpha > 0)) * 255).astype(np.uint8)).resize(img.size, Image.BILINEAR)
        c8 = Image.composite(cbig, img, edge)
    rgba = c8.convert("RGBA")
    rgba.putalpha(a8)
    return rgba, a8, report


def check_sheet(cut: Image.Image, face: list[float] | None = None, bg=(0x5A, 0x46, 0x46)) -> Image.Image:
    """Visual check: cut-out on dark #5A4646, plus zooms of head, hair edge, hand/hair gap and sleeve."""
    W_, H_ = cut.size
    base = Image.new("RGB", cut.size, bg)
    base.paste(cut, (0, 0), cut)
    a = np.asarray(cut.getchannel("A"))
    ys, xs = np.nonzero(a > 128)
    if not len(ys):
        return base
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    if face:
        fx0, fy0, fx1, fy1 = face[0] * W_, face[1] * H_, face[2] * W_, face[3] * H_
    else:
        fx0, fy0, fx1, fy1 = x0 + (x1 - x0) * 0.3, y0, x0 + (x1 - x0) * 0.7, y0 + (y1 - y0) * 0.25
    fw, fh = fx1 - fx0, fy1 - fy0
    boxes = [(fx0 - fw * 0.6, fy0 - fh * 0.6, fx1 + fw * 0.6, fy1 + fh * 0.3),        # head
             (fx0 - fw * 0.9, fy0, fx0 + fw * 0.1, fy1 + fh * 0.8),                  # hair edge left
             (fx1 - fw * 0.1, fy0, fx1 + fw * 0.9, fy1 + fh * 0.8),                  # hair edge right / hand
             (x0, fy1 + fh * 0.6, x0 + (x1 - x0) * 0.45, min(y1, fy1 + fh * 2.4))]   # sleeve
    tiles = []
    for b in boxes:
        b = tuple(int(max(0, min(v, lim))) for v, lim in zip(b, (W_, H_, W_, H_)))
        if b[2] - b[0] < 8 or b[3] - b[1] < 8:
            continue
        tiles.append(base.crop(b).resize((400, int(400 * (b[3] - b[1]) / (b[2] - b[0])))))
    side = base.copy()
    side.thumbnail((600, 900))
    th = max([side.height] + [t.height for t in tiles])
    sheet = Image.new("RGB", (side.width + 410 * len(tiles), th), (30, 30, 30))
    sheet.paste(side, (0, 0))
    for k, t in enumerate(tiles):
        sheet.paste(t, (side.width + 10 + 410 * k, 0))
    return sheet
