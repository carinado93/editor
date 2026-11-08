"""Schnittlisten für DaVinci Resolve / Final Cut / Premiere (ohne zu rendern).

- FCPXML 1.9: DaVinci Resolve (Datei → Importieren → Timeline) und Final Cut Pro.
- EDL (CMX 3600): Premiere, DaVinci, Avid.
Beide verweisen auf das Original-Video im Projektordner. So kannst du jeden Schnitt in DaVinci noch verschieben.
Hinweis: CapCut liest diese Formate nicht zuverlässig, dafür das gerenderte MP4 + SRT nehmen.
"""
from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from .render import frame_rate, snap


def _tc(frame: int, fps_int: int, drop: bool) -> str:
    """Timecode HH:MM:SS:FF (bei 29,97/59,94 als Drop-Frame mit ';')."""
    if drop:
        d = 2 if fps_int == 30 else 4
        per10 = fps_int * 600 - d * 9
        tens, rem = divmod(frame, per10)
        frame += d * 9 * tens + (d * ((rem - d) // (fps_int * 60 - d)) if rem > d else 0)
    ff = frame % fps_int
    s = frame // fps_int
    sep = ";" if drop else ":"
    return f"{s // 3600:02d}:{s // 60 % 60:02d}:{s % 60:02d}{sep}{ff:02d}"


def edl(title: str, source_name: str, frames: list[tuple[int, int]], fps: Fraction) -> str:
    fps_int = round(float(fps))
    drop = fps.denominator == 1001
    lines = [f"TITLE: {title}", f"FCM: {'DROP FRAME' if drop else 'NON-DROP FRAME'}", ""]
    rec = 0
    reel = "AX"
    for n, (a, b) in enumerate(frames, 1):
        length = b - a
        lines.append(f"{n:03d}  {reel:<8} AA/V  C        {_tc(a, fps_int, drop)} {_tc(b, fps_int, drop)} "
                     f"{_tc(rec, fps_int, drop)} {_tc(rec + length, fps_int, drop)}")
        lines.append(f"* FROM CLIP NAME: {source_name}")
        lines.append("")
        rec += length
    return "\n".join(lines) + "\n"


def _rt(frames: int, fps: Fraction) -> str:
    """Rationale Zeit für FCPXML, z. B. "1001/60000s" pro Bild."""
    t = Fraction(frames) / fps
    return f"{t.numerator}/{t.denominator}s" if t.denominator != 1 else f"{t.numerator}s"


def fcpxml(title: str, media: Path, info: dict, frames: list[tuple[int, int]], fps: Fraction) -> str:
    frame_dur = _rt(1, fps)
    total = sum(b - a for a, b in frames)
    src_len = int(info["duration"] * fps)
    uri = media.resolve().as_uri()
    w, h = info["width"], info["height"]
    clips = []
    offset = 0
    for a, b in frames:
        clips.append(f'          <asset-clip ref="r2" name={quoteattr(media.name)} offset="{_rt(offset, fps)}" '
                     f'start="{_rt(a, fps)}" duration="{_rt(b - a, fps)}" tcFormat="NDF" audioRole="dialogue"/>')
        offset += b - a
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.9">
  <resources>
    <format id="r1" name="FFVideoFormat{h}p" frameDuration="{frame_dur}" width="{w}" height="{h}"/>
    <asset id="r2" name={quoteattr(media.name)} start="0s" duration="{_rt(src_len, fps)}" hasVideo="1" hasAudio="1"
           format="r1" audioSources="1" audioChannels="2" audioRate="48000">
      <media-rep kind="original-media" src={quoteattr(uri)}/>
    </asset>
  </resources>
  <library>
    <event name={quoteattr(escape(title))}>
      <project name={quoteattr(escape(title) + " – Rohschnitt")}>
        <sequence format="r1" duration="{_rt(total, fps)}" tcStart="0s" tcFormat="NDF" audioLayout="stereo" audioRate="48k">
          <spine>
{chr(10).join(clips)}
          </spine>
        </sequence>
      </project>
    </event>
  </library>
</fcpxml>
'''


def write_all(title: str, media: Path, info: dict, segments: list[list[float]], out_dir: Path, stem: str) -> list[str]:
    fps = frame_rate(info)
    frames = snap(segments, fps, info["duration"])
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    p = out_dir / f"{stem}_davinci.fcpxml"
    p.write_text(fcpxml(title, media, info, frames, fps), encoding="utf-8")
    files.append(p.name)
    p = out_dir / f"{stem}.edl"
    p.write_text(edl(title, media.name, frames, fps), encoding="utf-8")
    files.append(p.name)
    return files
