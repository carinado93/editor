"""Enter = new line in every effect text.

Pillow refuses multi-line strings in the calls our effect drawers use (``text`` with an anchor such as "mm",
``textlength``, ``font.getlength``) and raises an error. Instead of rewriting ~50 drawers, these calls are taught
to handle "\n": lines are drawn below each other (block centred on the anchor), widths are the widest line,
boxes cover all lines. Strings without "\n" go straight to Pillow, unchanged.
"""
from __future__ import annotations

from PIL import ImageDraw, ImageFont

LINE = 1.15   # line height as a factor of the font size

_orig_text = ImageDraw.ImageDraw.text
_orig_textlength = ImageDraw.ImageDraw.textlength
_orig_textbbox = ImageDraw.ImageDraw.textbbox
_orig_getlength = ImageFont.FreeTypeFont.getlength
_orig_getbbox = ImageFont.FreeTypeFont.getbbox


def _multi(s) -> bool:
    return isinstance(s, str) and "\n" in s


def _size(font) -> float:
    return float(getattr(font, "size", 10) or 10)


def _shift(anchor: str | None, total: float) -> float:
    v = (anchor or "la")[1:2] or "a"
    return {"t": 0.0, "a": 0.0, "m": total / 2, "s": total, "b": total, "d": total}.get(v, 0.0)


def _text(self, xy, text, fill=None, font=None, anchor=None, *args, **kw):
    if not _multi(text):
        return _orig_text(self, xy, text, fill, font, anchor, *args, **kw)
    lines = text.replace("\r", "").split("\n")
    f = font or self.getfont()
    lh = _size(f) * LINE
    x, y = xy[0], xy[1]
    y0 = y - _shift(anchor, lh * (len(lines) - 1))
    for k, ln in enumerate(lines):
        if ln:
            _orig_text(self, (x, y0 + k * lh), ln, fill, font, anchor, *args, **kw)
    return None


def _textlength(self, text, font=None, *args, **kw):
    if not _multi(text):
        return _orig_textlength(self, text, font, *args, **kw)
    return max(_orig_textlength(self, ln, font, *args, **kw) for ln in text.split("\n"))


def _textbbox(self, xy, text, font=None, anchor=None, *args, **kw):
    if not _multi(text):
        return _orig_textbbox(self, xy, text, font, anchor, *args, **kw)
    lines = text.split("\n")
    f = font or self.getfont()
    lh = _size(f) * LINE
    y0 = xy[1] - _shift(anchor, lh * (len(lines) - 1))
    boxes = [_orig_textbbox(self, (xy[0], y0 + k * lh), ln or " ", font, anchor, *args, **kw) for k, ln in enumerate(lines)]
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def _getlength(self, text, *args, **kw):
    if not _multi(text):
        return _orig_getlength(self, text, *args, **kw)
    return max(_orig_getlength(self, ln, *args, **kw) for ln in text.split("\n"))


def _getbbox(self, text, *args, **kw):
    if not _multi(text):
        return _orig_getbbox(self, text, *args, **kw)
    lines = text.split("\n")
    lh = _size(self) * LINE
    boxes = [_orig_getbbox(self, ln or " ", *args, **kw) for ln in lines]
    return (min(b[0] for b in boxes), boxes[0][1], max(b[2] for b in boxes), int(boxes[-1][3] + lh * (len(lines) - 1)))


def install() -> None:
    if getattr(ImageDraw.ImageDraw.text, "_multiline", False):
        return
    _text._multiline = True
    ImageDraw.ImageDraw.text = _text
    ImageDraw.ImageDraw.textlength = _textlength
    ImageDraw.ImageDraw.textbbox = _textbbox
    ImageFont.FreeTypeFont.getlength = _getlength
    ImageFont.FreeTypeFont.getbbox = _getbbox


install()
