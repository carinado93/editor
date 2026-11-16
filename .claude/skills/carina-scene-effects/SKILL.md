---
name: "carina-scene-effects"
description: "Use when Carina sends day-in-my-life or vlog scenes and wants text effects, cards, stickers or iPhone mockups on her clips (not the cut itself)."
---

# Scene text & layout effects (approved 14-15 Nov 2026)

Full parameter list: project doc `claude/effects-library-day-in-my-life.md`. Read it before building.

## Workflow (her rules)
1. She sends the joined clip + what she wants + reference recordings. Tile the reference (16-24 frames) and copy motion/structure only.
2. Propose 2-4 effect ideas per scene with one recommendation. Build only after she picks. Text wording: propose, she approves, first person.
3. Low-res preview (1280 px) of the whole timeline, fix only what she names, final render on her go.
4. Her timestamps "01:09" = seconds:frames.

## Building blocks
- Person masks: rembg u2net_human_seg per frame (cache), largest component, binary_opening 7 to drop stray bits.
- **Text behind me**: draw words, paste the person back on top. Split words left/right of her body so no letter disappears behind her head.
- **Freeze**: 1-2 s still, audio silent, words pop one by one (no fade).
- **Cards**: video shrinks into a rounded card (r 36, soft shadow) on lilac #D6C6F0 or butter yellow #FAE8A5, text on the free space; grows back before the next transition. Sinking card: 1 -> 0.82 -> 0.66 with bounce for "and some more".
- **Sticker cut-out**: white outline (MaxFilter 19) + shadow on solid lilac.
- **Torn paper label** (plum #7A649E, jagged edges, lilac Anton text) that rings ±7° at 14 Hz, 0.45 s on / 0.35 s off.
- **3D cylinder text**: one 3-line block (Anton, vertical stretch 1.5), all rows same direction, left -> right, bulge f=0.72+0.33·cosθ, white with plum shadow, no background.
- **iPhone mockup**: landscape phone (bezel 26, r 60) on plain lilac, cards popping right, ~2.2 s per card, punchline card filled plum.
- **To-do card** with animated ticks; **x2 sticker** on 2x speed walks; **⏪ + writing-on Cormorant italic**; emoji via Noto Color Emoji.
- Fonts via @fontsource + fontTools: Titan One, Fredoka, Inter 300/800, Anton, Cinzel Decorative, Cormorant Garamond 600 italic, Noto Serif Display.

## Rejected (don't offer again)
Light trail outline around her, dotted lilac backgrounds, text touching the edge (keep ~200 px), text hiding behind her head, slow cursor intros, real other creators' footage.

## Check before sending
Tile key frames: no text on face, nothing cut at edges, words readable. Then send with SendUserFile.
## Added 15–16 Nov 2026 (scripts in `scripts/`)
- **Meditation timer** (med.py): pause slam ⏸ + B&W slide, half speed, "meditation time" write-on, 30:00→00:00 ring timer, ding pulse.
- **Sport label pill**: lilac pill top-left, drawn stopwatch with rotating hand, Titan name + white inner pill "× 30 min"; old pill slides up when the next sport starts. Title "and now… SPORTS AT HOME" with letter drop.
- **Work effects, version B chosen** (fx.py):
  - yawns: tall "brain battery" draining 40→3 % lilac→red + iOS-style popup "Low Battery · 3% remaining · connect to coffee"
  - bored typing: dark code chips with lilac dot typing themselves ("if (tired) { keepGoing() }", "// why is this not working")
  - evening: night tint, sun sets, moon rises, time counts 18:00→21:47, pill "wait… it's night?" (clip at half speed)
  - shutdown: RGB-split glitch + scanlines, then shutdown at 2× with pill "logging off…"
  - version A alternatives: horizontal battery, "lines of code" counter, lilac flip clock, CRT power-off
- **Office scripts**: office_txt.py (torn labels DRESSED/HOME ringing, "what do we have planned for today?"), office2.py (to-do card, escalating "and some more", sticker cut-out with words, 24 HOURS label, notebook panel + ✗, "I'm just a girl 🎀", writing-on "back to editing").
- **Skincare iPhone cards**: skin.py (header + 6 first-person cards, 2.2 s per card; slow to 1.25× of her CapCut speed for reading).
