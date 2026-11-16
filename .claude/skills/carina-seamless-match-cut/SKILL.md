---
name: "carina-seamless-match-cut"
description: "Use when Carina wants two clips joined so the cut is invisible: whip/swing match cuts, outfit or makeup swaps, mirror reflection swaps, jump-outfit cuts."
---

# Seamless match cuts for Carina

She notices every flaw: a light jump, a one-frame shake, a seam, a body part (hair) at the edge. Her rule: "no sign of editing". Measure, don't guess.

## 1. Find the cut frames
- Tile frames at 20-30 fps with timestamps (ffmpeg fps + drawtext + tile) around both candidate moments. LOOK at them.
- Use rembg (u2net_human_seg) masks per frame to measure the person: top y, xmin/xmax, area. For jumps: cut while the head is out of frame (top=0) going up in clip A, coming down in clip B. For swings: cut mid-whip when the face is at the same edge in both.
- Her timestamps like 01:09 are CapCut seconds:frames (1 s + 9 frames), not minutes.

## 2. Mirror swap (old reflection -> new reflection while real person stays)
- Never split the frame with a vertical seam (she saw it immediately).
- Keep clip A untouched; only replace the reflection: inpaint A's reflection (mask dilated ~30 px, cv2.inpaint TELEA r15), paste clip B's reflection cut-out at the same size/position (align right edge + head top to A's reflection bbox), colour-match to A's original reflection region, add the same horizontal motion blur as the whip, keep A's real person on top.
- Use B frames that are consecutive with where B continues after the cut, so the reflection moves on naturally. Pick the pose she wants (she wanted the one looking into the camera).
- Cut only when A's real face has fully left the frame -> mirror-to-mirror cut.

## 3. Align both sides of the cut with zoom/crop
- Work from the full-res source (DJI 2688x1512) and crop down to 1920x1080 so zoom stays sharp.
- Same zoom on both sides at the cut (otherwise the reflection size jumps). Solve crop centres so the reflection/mirror frame lands at the same output position; use the zoom to crop out stray hair/body at the edges.
- Ramp clip A's zoom over the WHOLE swing (~0.5 s), not 10 frames, including the vertical shift, or it reads as a jolt. Ease B's zoom back to 1.0 during the next camera move.

## 4. Motion continuity (the hidden "shake")
- Check with cv2.phaseCorrelate on 480x270 grey frames across the cut: the per-frame dx should decelerate smoothly (e.g. 50, 48, 43, 22, 29, 12, 7, 3), no backwards step, no dy spike.
- If B starts still while A is whipping: offset B's crop so the motion continues and decays (off_i = c*0.6^(i+1)), shift A's final crop target by c, add fading motion blur to the first B frames. Tune c until the step at the cut matches A's last step.

## 5. Light continuity
- Measure mean brightness per frame across the cut. Match B's colour/brightness to A's last frame (mean/std per channel) and ease back to B's own look over ~36 frames.
- Deflicker the transition: Gaussian-smooth (sigma 5) the per-frame mean RGB including the last 15 frames of A, apply per-frame gain, fade the gain out at the end.

## 6. Delivery
- Audio: concatenate original audio of both clips at the same cut points, 0.04-0.05 s crossfade.
- 1920x1080, 30 fps, crf 20, maxrate 8M, faststart. Send it, ask her to screenshot any frame that still looks edited.