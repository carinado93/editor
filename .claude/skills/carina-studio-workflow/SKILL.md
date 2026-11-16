---
name: carina-studio-workflow
description: Master workflow for every video job in Carina's video studio (reels, shorts, YouTube, day-in-my-life scenes). Read first before any other carina-* skill.
---

# Carina Video Studio – master workflow

Carina Dorca: stress & burnout PREVENTION coach. EN: Instagram @carina.dorca + English YouTube. DE: @carinadorca.coach + German YouTube (@Cary-redet). She films on phone/DJI, used to cut in CapCut. This app replaces that.

## The approval loop (non-negotiable)
1. **Analyse** the clip(s): ffprobe, scene cuts (`select='gt(scene,0.25)'`), tile frames with timestamps (fps 4–6, drawtext pts, tile 8x5) and LOOK at them. Person masks (rembg) where she is.
2. **Ideas first**: 2–4 concrete options per scene/transition (name + one line), recommend one. When she says "make multiple versions so I can pick" → build each option as its own short preview (or version A/B of the whole clip with one variant per effect so she can mix "battery B + code A").
3. **Text wording**: propose, she approves. First person ("I"). For a second language: show the full translation table first, get "passt", then render.
4. **Preview**: 1280 px, crf 23. Fix ONLY what she names.
5. **Final** only on her go: 1920x1080 crf 17–18, faststart.
6. Deliver with every reel: video + caption + exactly 5 hashtags + cover (+ YouTube title / thumbnail when posting to YouTube).

## Her conventions
- Timestamps like `01:09` = CapCut seconds:frames (1 s + 9 frames).
- Originals are read-only: work on copies, never overwrite uploads.
- Review by friends matters: "too quick / too much text" → slow text parts, cut text, keep pace elsewhere (see carina-pacing-localization).
- She notices every flaw (seams, light jumps, a missing finger in a cut-out). Check every output by tiling frames before sending.

## Skill map
- Brand look → `carina-brand-style`
- Text/cards/stickers/work effects on footage → `carina-scene-effects`
- Transitions (rope + click, window, burst, boom, swipe, workout card, iris…) → `carina-creative-transitions`
- Invisible cuts → `carina-seamless-match-cut`
- Cut-outs, text behind her, clean plates (empty room) → `carina-cutout-cleanplate`
- Endings & CTAs (Strava stats, subscribe/like, thank-you heart) → `carina-endings-cta`
- Speed/readability, German versions, 9:16 Shorts export → `carina-pacing-localization`
- Polishing a finished CapCut cut (text cards, no re-edit) → `carina-reel-edit`
- Covers/thumbnails → `carina-reel-cover`
- Posting, captions, hashtags, pinned comments → `carina-publishing`
- AI footage (only when not filmed) → `carina-higgsfield`

## Pipeline architecture (proven)
- Each scene renders to a numbered PNG folder (PIL + numpy per frame), encoded as a segment mp4 (crf 14 intermediate). Final = concat demuxer of segments.
- Keep a list of frame sources per segment (symlinks) so a segment can be rebuilt (e.g. new language) by swapping only the text-bearing folders.
- Speed changes per section: `-ss a -t (b-a) -i src` (input options!) + `setpts=(PTS-STARTPTS)/speed,fps=30`. Putting -t after -i cuts the wrong range.
- Audio rebuilt per segment: original audio, silence during freezes, short 30 ms fades at joins, synthesized soft SFX (click 2.4 kHz decaying, whoosh = filtered pink noise sin² envelope, pop = falling sine, ding = 1568 Hz + octave). If she posts with trending music she exports silent – ask.
- Cache masks per frame (expensive). Free disk: delete intermediate PNG folders you created once the segment mp4 exists.
