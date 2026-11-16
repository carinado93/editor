---
name: carina-pacing-localization
description: Speed/readability rules, re-pacing an edit after feedback, German versions of finished reels, split screens and 9:16 Shorts export.
---

# Pacing, language versions, formats

## Readability (friends' review: "too quick, too much text")
- ~1 s per 3–4 words on screen; multi-line cards ≥ 2 s; freeze texts ≥ 3–3.5 s with lines appearing 0.6 s apart.
- Remove text that only decorates (her cuts: wand/Lumos, coffee "you might be wondering", 3D text, "let's finish breakfast" card, "second things second").
- Keep her CapCut pacing for parts she approves; slow text-heavy parts (skincare cards 1.25×, office punchlines 1.15×, workout card 0.7×, work effects + ending 1×). Sports/walks 2×.
- Implementation: list of (start, end, speed) ranges over the final render, each cut with input-side -ss/-t, setpts, concat demuxer; rebuild opening segments from frame folders when structure changes.

## Split screen (coffee | breakfast)
After the click/window: window card moves to the left half (880 px, r 36), second clip pops in right (back-ease); when the left clip ends it slides out and the right card maximises to full frame over 10 frames.

## German (or any second language) version
1. Extract every on-screen string from the scripts → translation table → her approval (she changed "Konzernjob" → "Corporate Job", "aufgeben gilt aber nicht").
2. Copy each text script to *_de.py with string replacements and _de output folders; re-check layout (German is ~30 % longer: shrink fonts to fit, split lines, move words away from her arms, widen write-on reveals).
3. Rebuild segments by swapping only text-bearing folders. If the original assembly commands are lost, map each frame of the old segment to its source folder by nearest thumbnail (64x36 grey MSE) and relink.
4. Same speeds as the approved version. Covers and captions in German too.
- Keep trend phrases in English if she wants ("I'm just a girl 🎀").

## 9:16 Shorts from a landscape edit
`scale=1080:-2,pad=1080:1920:0:(oh-ih)/2:black,setsar=1`, crf 19, AAC 192k. She explicitly wanted black bars (not blurred fill).
