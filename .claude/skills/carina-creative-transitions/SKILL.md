---
name: "carina-creative-transitions"
description: "Use when Carina wants a cool transition between two scenes of her reel (wand, click, window, burst, teleport, swipe, pull-back) and asks for ideas."
---

# Creative transitions (approved on the day-in-my-life reel)

Always offer 2-4 options first, recommend one, build after her pick. Quick and professional beats long and cute. Details and parameters: project doc `claude/effects-library-day-in-my-life.md`. For invisible cuts use skill `carina-seamless-match-cut`.

## Menu
1. **Wand + Lumos + flash** – procedural dark wand slides in from the left (no hand), tip glow brightens the room, "Lumos" in Cinzel Decorative lilac rises, white flash into the bright clip.
2. **Clothesline + cursor click** – rope draws in behind her, real object cut-outs (ask for photos of her own things) drop on clothespins and swing, one behind her head, pixel cursor clicks the hero object (ring pulse, soft click).
3. **Window from clicked object** – mac-style window pops out of the object with the next clip playing, then becomes a card/fullscreen.
4. **Object onto previous shot + burst** – freeze, cut-out of the next scene's object pops onto the current one (stays inside it), click, pieces segmented from her own footage burst toward camera, next clip starts underneath. Remove every leftover piece right after the cut.
5. **Golden boom + teleport appear** – empty room 0.5 s, sparkles gather, small golden explosion (≤510 px), white flash + zoom blur (CapCut Flashback), she appears mid-motion (walk-in removed), sparkles drift. Explosion BEFORE she appears.
6. **Pull-back / push-in through a camera screen** – the shot shrinks (0.3 s, motion blur) into the screen of a device cut-out on plain lilac, screen flips, push back in (0.35 s), soft whooshes.
7. **Arm swipe** – next scene sweeps in along her arm swing (soft 90 px edge, motion blur, 8 frames).
8. **Match cut on movement** – jump (head out of frame) or arms at the same height, frames found with mask metrics.
9. **Whip match cut** – blur-to-blur cut with directional blur (fallback when nothing else fits).

## Rejected
Hand clap from another creator's video (not her footage), slow cursor-only intros, dotted backgrounds, boom so big it hides everything.

## Sound
Only soft: click, whoosh (filtered pink noise), ting, swell. Original audio kept, silent during freezes.
## Added 15–16 Nov 2026 (scripts in `scripts/`)
10. **Rope + click → sticker flies into her** (rope.py, chosen for sports): room as clean plate dimmed 28 %, rope draws in, full-body sticker cut-outs of each pose (white outline, box 300 px) drop on pins and swing, done ones faded 45 % + lilac ✓, cursor clicks the current one, sticker arcs (−160 px) and scales to her live bbox (bottom-aligned, width for lying poses), crossfades into her live cut-out over 6 frames. Pill pops at the click.
11. **Placed down into the still room** (descend.py): alternative to 10, see carina-cutout-cleanplate. Her idea for it: the mat rising from below to meet her.
12. **"Workout saved" card** (tw.py t3, chosen): freeze, desaturate + dim, lilac card pops (scale 1.3): pause bars + "WORKOUT SAVED", Time / Activities / Mood, button "RESUME: WORK ▶", cursor click with bounce, push-slide left with motion blur. Must stay ~2 s.
13. Built alternatives: zoom through the gap between her arms into the background monitor and out of her own monitor (tw.py t1), whip spin on seated poses (t2), rope with a WORK sticker (t4).
14. **Rope on the dark shot**: endfreeze.py works on any freeze frame + its mask (she dropped wand/Lumos and the bright clip).
15. **Window → split screen** (split.py), see carina-pacing-localization.
16. **Lilac iris / heart cover** for CTAs and endings, see carina-endings-cta.
