"""Studio transitions between two joined clips (from the "Day in my life" training, Nov 2026).

Each transition renders its own short "seam" clip (Python/Pillow frame by frame) that replaces the end of clip A
and/or the start of clip B. combine.build() then joins everything with hard cuts.

  split   coffee | breakfast: A plays on the left, B on the right (lilac background); when A's part ends,
          A slides out and B grows to full screen.
  rope    A freezes (dimmed), a rope drops in with a sticker of Carina from clip B; a cursor clicks it,
          the sticker flies to where she is in B and turns into the real video.
  placed  B starts with the empty room (last frame of A if A ends on the empty room, else built from B; tripod); Carina is lowered in from
          above while she keeps moving, a soft shadow grows and a lilac ring pulses when she lands.
  iris    A closes into a lilac circle, B opens out of it.
"""
from __future__ import annotations

import math
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import fx, fx_studio, media
import logging
log = logging.getLogger(__name__)

LABELS = {"split": "Split screen (A left, B right, then B full)",
          "rope": "Rope + click: your sticker flies into the next clip",
          "placed": "Placed into the room (tripod: you are lowered in)",
          "iris": "Lilac circle closes and opens"}

# seconds taken from the end of A and the start of B
SPANS = {"split": (3.0, 3.0), "rope": (0.0, 0.3), "placed": (0.0, 1.2), "iris": (0.4, 0.4)}
ROPE_TOTAL = 1.6  # seconds the rope seam lasts (A frozen most of it)


def spans(kind: str, len_a: float, len_b: float) -> tuple[float, float]:
    a, b = SPANS[kind]
    if kind == "split":
        L = max(1.0, min(a, len_a - 0.3, len_b - 0.6))
        return L, L + 0.35
    return min(a, max(0.0, len_a - 0.3)), min(b, max(0.3, len_b - 0.3))


def _frames(path: Path, info: dict, t0: float, dur: float, W: int, H: int, fps: str) -> list[Image.Image]:
    if dur <= 0:
        return []
    vf = (f"{media.sdr_filter(info)}scale={W}:{H}:force_original_aspect_ratio=decrease,"
          f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={fps},format=rgb24")
    r = subprocess.run([media.ffmpeg(), "-hide_banner", "-loglevel", "error", "-ss", f"{max(0.0, t0):.3f}",
                        "-t", f"{dur:.3f}", "-i", str(path), "-vf", vf, "-f", "rawvideo", "-"],
                       capture_output=True, creationflags=media._NO_WINDOW)
    raw = r.stdout
    n = len(raw) // (W * H * 3)
    return [Image.fromarray(np.frombuffer(raw[k * W * H * 3:(k + 1) * W * H * 3], np.uint8).reshape(H, W, 3))
            for k in range(n)]


def _audio(path_a: Path, info_a: dict, a0: float, path_b: Path, info_b: dict, b0: float, dur: float,
           mode: str, out: Path, delay: float = 0.0) -> None:
    """Seam audio: 'cross' = A fades into B, 'b' = only B, 'mix' = both (A fading out), 'silent' + B at the end."""
    def src(p, info, t):
        if info.get("has_audio"):
            return ["-ss", f"{max(0.0, t):.3f}", "-t", f"{dur:.3f}", "-i", str(p)]
        return ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    fmt = "aresample=48000,aformat=channel_layouts=stereo"
    if mode == "b":
        ms = int(delay * 1000)
        args, graph = src(path_b, info_b, b0), f"[0:a]{fmt},adelay={ms}|{ms},apad=whole_dur={dur:.3f}[a]"
    else:
        args = src(path_a, info_a, a0) + src(path_b, info_b, b0)
        if mode == "mix":
            graph = (f"[0:a]{fmt},afade=t=out:st={max(0.0, dur - 0.6):.3f}:d=0.6,volume=0.7[x];[1:a]{fmt}[y];"
                     f"[x][y]amix=inputs=2:duration=longest:normalize=0,apad=whole_dur={dur:.3f}[a]")
        else:
            half = dur / 2
            graph = (f"[0:a]{fmt},afade=t=out:st=0:d={half:.3f},apad=whole_dur={dur:.3f}[x];"
                     f"[1:a]{fmt},adelay=0|0,afade=t=in:st=0:d={half:.3f}[y];"
                     f"[x][y]amix=inputs=2:duration=first:normalize=0[a]")
    media.run([media.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", *args, "-filter_complex", graph,
               "-map", "[a]", "-t", f"{dur:.3f}", "-c:a", "pcm_s16le", "-ar", "48000", str(out)])


def _write(frames: list[Image.Image], audio: Path, out: Path, fps: str, encoder: list[str]) -> None:
    W, H = frames[0].size
    p = subprocess.Popen([media.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", fps, "-i", "-", "-i", str(audio),
                          "-map", "0:v", "-map", "1:a", *encoder, "-pix_fmt", "yuv420p", *media.SDR_TAGS,
                          "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", str(out)],
                         stdin=subprocess.PIPE, creationflags=media._NO_WINDOW)
    for f in frames:
        p.stdin.write(np.asarray(f.convert("RGB"), np.uint8).tobytes())
    p.stdin.close()
    p.wait()


def _card(img: Image.Image, w: int, radius: int) -> Image.Image:
    h = int(w * img.height / img.width)
    c = img.resize((max(2, w), max(2, h)), Image.LANCZOS).convert("RGBA")
    m = Image.new("L", c.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, c.width - 1, c.height - 1), max(0, radius), fill=255)
    c.putalpha(m)
    return c


def _paste_card(bg: Image.Image, card: Image.Image, cx: float, cy: float, shadow: bool = True):
    if shadow:
        sh = Image.new("RGBA", (card.width + 80, card.height + 80), (0, 0, 0, 0))
        sm = Image.new("RGBA", card.size, (60, 30, 90, 90))
        sm.putalpha(card.getchannel("A").point(lambda v: int(v * 0.35)))
        sh.alpha_composite(sm, (40, 52))
        sh = sh.filter(ImageFilter.GaussianBlur(20))
        bg.alpha_composite(sh, (int(cx - card.width / 2 - 40), int(cy - card.height / 2 - 40)))
    bg.alpha_composite(card, (int(cx - card.width / 2), int(cy - card.height / 2)))


# ------------------------------------------------------------------ split

def render_split(fa: list[Image.Image], fb: list[Image.Image], W: int, H: int) -> list[Image.Image]:
    ctx = fx.Ctx(W, H, None)
    bg = fx_studio._lilac_bg(ctx)
    portrait = H > W
    n = len(fb)
    na = len(fa)
    out = []
    cw = int(W * (0.88 if portrait else 0.46))
    rad = int(36 * ctx.u)
    if portrait:
        pa, pb = (W / 2, H * 0.29), (W / 2, H * 0.71)
    else:
        pa, pb = (W * 0.255, H * 0.52), (W * 0.745, H * 0.52)
    for k in range(n):
        img = bg.copy()
        e_in = fx.ease_out(k / 10)
        if k < na:
            # A: full frame → left card
            w_a = int(W + (cw - W) * e_in)
            cx = W / 2 + (pa[0] - W / 2) * e_in
            cy = H / 2 + (pa[1] - H / 2) * e_in
            _paste_card(img, _card(fa[k], w_a, int(rad * e_in)), cx, cy, shadow=e_in > 0.5)
            sb = fx_studio.back(k / 12)
            _paste_card(img, _card(fb[k], max(2, int(cw * sb)), rad), pb[0], pb[1])
        else:
            q = fx.ease_out((k - na) / max(1, n - na - 1))
            if q < 1:
                _paste_card(img, _card(fa[-1], cw, rad), pa[0] - (W * 0.8 if not portrait else 0) * q,
                            pa[1] - (H * 0.8 if portrait else 0) * q)
            w_b = int(cw + (W - cw) * q)
            _paste_card(img, _card(fb[k], w_b, int(rad * (1 - q))), pb[0] + (W / 2 - pb[0]) * q,
                        pb[1] + (H / 2 - pb[1]) * q, shadow=q < 0.9)
        out.append(img.convert("RGB"))
    return out


# ------------------------------------------------------------------ rope

def _sticker(frame: Image.Image, mask: Image.Image, box: int) -> Image.Image | None:
    rgba = frame.convert("RGBA")
    rgba.putalpha(mask.point(lambda v: 255 if v > 110 else int(v * 1.5)))
    bb = rgba.getchannel("A").point(lambda v: 255 if v > 120 else 0).getbbox()
    if not bb:
        return None
    cut = rgba.crop(bb)
    s = box / max(cut.size)
    cut = cut.resize((max(2, int(cut.width * s)), max(2, int(cut.height * s))), Image.LANCZOS)
    pad = 22
    c = Image.new("RGBA", (cut.width + 2 * pad, cut.height + 2 * pad), (0, 0, 0, 0))
    c.alpha_composite(cut, (pad, pad))
    a = c.getchannel("A").filter(ImageFilter.MaxFilter(17)).filter(ImageFilter.GaussianBlur(1.2))
    white = Image.new("RGBA", c.size, (255, 255, 255, 255))
    white.putalpha(a)
    sh = Image.new("RGBA", c.size, (0, 0, 0, 0))
    sh.putalpha(a.point(lambda v: int(v * 0.45)))
    sh = sh.filter(ImageFilter.GaussianBlur(8))
    o = Image.new("RGBA", (c.width + 20, c.height + 20), (0, 0, 0, 0))
    o.alpha_composite(sh, (10, 16))
    o.alpha_composite(white)
    o.alpha_composite(c)
    return o


def render_rope(a_last: Image.Image, fb_live: list[Image.Image], seg, W: int, H: int, fps: float,
                n: int) -> list[Image.Image]:
    """A stays frozen, the last len(fb_live) frames cross into clip B (which then just continues)."""
    ctx = fx.Ctx(W, H, None)
    u = ctx.u
    live = len(fb_live)
    target = fb_live[-1]
    tmask = seg.mask(target)
    bb = tmask.point(lambda v: 255 if v > 120 else 0).getbbox() or (W // 3, H // 4, 2 * W // 3, H)
    st = _sticker(target, tmask, int(300 * u)) or Image.new("RGBA", (10, 10))
    click = int(n * 0.38)
    freeze = n - live
    out = []
    rope_y = lambda x: 70 * u + 80 * u * (1 - ((x - W / 2) / (W * 0.52)) ** 2)  # noqa: E731
    sx = W * 0.5
    pin = Image.new("RGBA", (int(22 * u) + 2, int(48 * u) + 2), (0, 0, 0, 0))
    ImageDraw.Draw(pin).rounded_rectangle((1, 1, 22 * u, 46 * u), int(5 * u), fill=(196, 150, 104, 255),
                                          outline=(120, 84, 54, 255), width=2)
    for k in range(n):
        dim = 0.28 * fx.ease_out(k / 6) if k < click else 0.28 * (1 - fx.ease_out((k - click) / 10))
        base = a_last if k < freeze else fb_live[k - freeze]
        img = Image.blend(base.convert("RGB"), Image.new("RGB", (W, H), (0, 0, 0)), dim).convert("RGBA")
        if k >= freeze:  # live B underneath, crossfade from the frozen picture
            wl = fx.ease_out((k - freeze + 1) / max(1, live))
            img = Image.blend(Image.blend(a_last.convert("RGB"), Image.new("RGB", (W, H)), dim).convert("RGBA"),
                              img, wl)
        d = ImageDraw.Draw(img)
        oy = 0 if k < click + 3 else -260 * u * fx.ease_out((k - click - 3) / 8)
        xe = -20 + (W + 40) * fx.ease_out(k / 7)
        pts = [(x, rope_y(x) + oy) for x in np.linspace(-20, xe, 80)]
        d.line(pts, fill=(70, 55, 45, 255), width=max(3, int(5 * u)))
        d.line([(x, y - 1) for x, y in pts], fill=(150, 128, 108, 255), width=max(1, int(2 * u)))
        dt = max(0.0, (k - 2) / fps)
        ang = 14 * math.exp(-dt * 1.6) * math.sin(dt * 7) + 2.2 * math.sin(k / fps * 2.2)
        py = rope_y(sx) + oy
        if k < click:
            yy = py - (1 - fx.ease_out(dt / 0.25)) * 300 * u
            big = st.rotate(ang, resample=Image.BICUBIC, expand=True)
            img.alpha_composite(big, (int(sx - big.width / 2), int(yy - 6 * u)))
            img.alpha_composite(pin, (int(sx - pin.width / 2), int(yy - 28 * u)))
        else:
            e = fx.ease_out((k - click) / max(1, freeze + live // 2 - click))
            tw = (bb[2] - bb[0]) / max(1, st.width - 64)
            th = (bb[3] - bb[1]) / max(1, st.height - 64)
            s = 1 + ((tw if st.width > st.height else th) * 1.03 - 1) * e
            al = 1.0 if k < freeze else max(0.0, 1 - (k - freeze + 1) / max(1, live))
            if al > 0.02:
                sp = st.resize((max(2, int(st.width * s)), max(2, int(st.height * s))), Image.LANCZOS)
                sp = sp.rotate(ang * (1 - e), resample=Image.BICUBIC, expand=True)
                if al < 1:
                    sp.putalpha(sp.getchannel("A").point(lambda v: int(v * al)))
                cx = sx + ((bb[0] + bb[2]) / 2 - sx) * e
                cy0 = py + st.height / 2
                cy1 = bb[3] - (st.height - 64) * s / 2
                cy = cy0 + (cy1 - cy0) * e - 160 * u * math.sin(math.pi * e)
                img.alpha_composite(sp, (int(cx - sp.width / 2), int(cy - sp.height / 2)))
        if click <= k < click + 12:  # click ring
            q = (k - click) / 12
            r = int((40 + 220 * q) * u)
            ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(ring).ellipse((sx - r, py + 150 * u - r, sx + r, py + 150 * u + r),
                                         outline=(255, 255, 255, int(255 * (1 - q))), width=max(2, int(6 * u)))
            img.alpha_composite(ring)
        if 6 <= k < click + 5:
            p = fx.ease_out((k - 6) / max(1, click - 7))
            tx, ty = sx + 10 * u, py + 150 * u
            x, y = W * 0.86 + (tx - W * 0.86) * p, H * 0.93 + (ty - H * 0.93) * p
            img.alpha_composite(fx_studio._cursor(u * (0.82 if abs(k - click) <= 1 else 1)), (int(x), int(y)))
        out.append(img.convert("RGB"))
    return out


# ------------------------------------------------------------------ placed
def person_share(img: Image.Image, seg) -> float:
    m = np.asarray(seg.mask(img.convert("RGB")).resize((160, 90)), dtype=np.uint8)
    return float((m > 128).mean())


def _room_plate(path_a, info_a, a_end, path_b, W, H, fps_s, fpsf, seg):
    """The empty room. Best: clip A ends on the empty room (she filmed it) -> use that frame. Otherwise build it
    from clip B (works only if she moves around enough in B)."""
    last = _frames(path_a, info_a, max(0.0, a_end - 1.0 / fpsf), 1.5 / fpsf, W, H, fps_s)
    if last and person_share(last[-1], seg) < 0.01:
        return last[-1]
    from . import fxrender
    plate = fxrender.auto_plate(path_b, W, H, seg)
    if plate is not None and person_share(plate, seg) > 0.02:
        log.warning("placed: empty room not clean (she barely moves in clip B) - film the empty room at the end of clip A")
    return plate


def render_placed(fb: list[Image.Image], plate: Image.Image, seg, W: int, H: int) -> list[Image.Image]:
    u = min(W, H) / 1080
    n = len(fb)
    empty = max(3, int(n * 0.18))
    desc = n - empty
    out = []
    plate = plate.convert("RGB").resize((W, H))
    land = None
    for k, fr in enumerate(fb):
        if k < empty:
            out.append(plate.copy())
            continue
        m = seg.mask(fr)
        ma = np.asarray(m, np.float32) / 255
        ys, xs = np.nonzero(ma > 0.5)
        if len(ys) == 0:
            out.append(fr)
            continue
        bot = int(ys.max())
        cx = float(xs[ys > bot - 60].mean()) if (ys > bot - 60).any() else float(xs.mean())
        land = (cx, bot)
        t = (k - empty + 1) / desc
        e = fx.ease_out(t)
        dy = -(bot + 40) * (1 - e)
        s = 1 + 0.10 * (1 - e)
        # move frame + mask with an affine transform around her feet
        A = (1 / s, 0, cx - cx / s, 0, 1 / s, bot - (bot + dy) / s)
        cut = fr.transform((W, H), Image.AFFINE, A, Image.BILINEAR)
        mm = m.transform((W, H), Image.AFFINE, A, Image.BILINEAR)
        v = (bot + 40) * 3 * (1 - t) ** 2 / desc
        if v > 6:
            rad = min(14, v / 4)
            mm = mm.filter(ImageFilter.GaussianBlur(rad / 3))
        img = plate.copy().convert("RGBA")
        sh = Image.new("L", (W, H), 0)
        sw = int(260 * u * (0.4 + 0.6 * e))
        ImageDraw.Draw(sh).ellipse((cx - sw, bot - sw * 0.16, cx + sw, bot + sw * 0.16), fill=255)
        sh = sh.filter(ImageFilter.GaussianBlur(max(2, int(25 * u)))).point(lambda v: int(v * 0.45 * e))
        img.paste(Image.new("RGBA", (W, H), (0, 0, 0, 255)), (0, 0), sh)
        img.paste(cut, (0, 0), mm)
        rem = n - 1 - k
        if rem < 4:
            img = Image.blend(img.convert("RGB"), fr, 1 - rem / 4).convert("RGBA")
        if land and rem < 10:  # lilac ring at her feet
            q = (10 - rem) / 10
            r = (200 + 380 * fx.ease_out(q)) * u
            ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(ring).ellipse((cx - r, bot - r * 0.17, cx + r, bot + r * 0.17),
                                         outline=fx_studio.LILAC + (int(200 * (1 - q)),), width=max(3, int(10 * u)))
            img.alpha_composite(ring)
        out.append(img.convert("RGB"))
    return out


# ------------------------------------------------------------------ iris

def render_iris(fa: list[Image.Image], fb: list[Image.Image], W: int, H: int) -> list[Image.Image]:
    ctx = fx.Ctx(W, H, None)
    bg = fx_studio._lilac_bg(ctx).convert("RGB")
    R0 = math.hypot(W, H) / 2 + 20
    out = []
    for k, f in enumerate(fa):
        R = R0 * (1 - fx.ease_out((k + 1) / len(fa)))
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).ellipse((W / 2 - R, H / 2 - R, W / 2 + R, H / 2 + R), fill=255)
        out.append(Image.composite(f, bg, m.filter(ImageFilter.GaussianBlur(6))))
    for k, f in enumerate(fb):
        R = R0 * fx.ease_out((k + 1) / len(fb))
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).ellipse((W / 2 - R, H / 2 - R, W / 2 + R, H / 2 + R), fill=255)
        out.append(Image.composite(f, bg, m.filter(ImageFilter.GaussianBlur(6))))
    return out


# ------------------------------------------------------------------ seam

def make_seam(kind: str, path_a: Path, info_a: dict, a_end: float, path_b: Path, info_b: dict, b_start: float,
              ta: float, tb: float, W: int, H: int, fps: Fraction, out: Path, encoder: list[str]) -> float:
    """Renders the seam clip and returns its length in seconds."""
    fps_s = f"{fps.numerator}/{fps.denominator}"
    fpsf = float(fps)
    fa = _frames(path_a, info_a, a_end - ta, ta, W, H, fps_s) if ta > 0 else []
    fb = _frames(path_b, info_b, b_start, tb, W, H, fps_s)
    if not fb:
        raise RuntimeError("could not read clip B")
    seg = None
    if kind in ("rope", "placed"):
        seg = fx.Segmenter()
    try:
        if kind == "split":
            frames = render_split(fa, fb, W, H)
            mode = "mix"
        elif kind == "rope":
            a_last = _frames(path_a, info_a, max(0.0, a_end - 1.0 / fpsf), 1.0 / fpsf * 1.5, W, H, fps_s)
            a_last = (a_last or [fb[0]])[-1]
            frames = render_rope(a_last, fb, seg, W, H, fpsf, max(len(fb) + 8, int(ROPE_TOTAL * fpsf)))
            mode = "b"
        elif kind == "placed":
            plate = _room_plate(path_a, info_a, a_end, path_b, W, H, fps_s, fpsf, seg)
            frames = render_placed(fb, plate or fb[0], seg, W, H)
            mode = "b"
        else:
            frames = render_iris(fa, fb, W, H)
            mode = "cross"
    finally:
        if seg is not None:
            seg.close()
    dur = len(frames) / fpsf
    wav = out.with_suffix(".wav")
    a0 = a_end - ta if ta > 0 else a_end
    delay = dur - len(fb) / fpsf if kind == "rope" else 0.0
    _audio(path_a, info_a, a0, path_b, info_b, b_start, dur, mode if ta > 0 or mode == "b" else "b", wav, delay)
    _write(frames, wav, out, fps_s, encoder)
    try:
        wav.unlink()
    except OSError:
        pass
    return dur
