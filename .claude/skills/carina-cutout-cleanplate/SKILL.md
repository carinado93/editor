---
name: carina-cutout-cleanplate
description: Person cut-outs, text behind Carina, finger/hand mask fixes, and clean plates (her removed from the room) for empty-room and placed-down effects.
---

# Cut-outs & clean plates

## Person masks
- rembg `u2net_human_seg` at 960x540, upscale to 1920x1080, soft threshold `clip((m-0.25)/0.5)`; keep the largest connected component (dilate 25 px), drops plants/furniture blobs. See `scripts/maskfix.py`.
- Cache one PNG mask per frame; compute only frames you need (first 45 of a shot + every 3rd for plates).
- Socks/feet in coloured light get lost: add skin/sock-colour pixels just below the mask bottom that touch the mask.

## Hands & fingers (she spotted 2 missing fingers!)
rembg drops raised fingers. Fix: GrabCut on 960x540 seeded with rembg (eroded >0.8 = FGD, dilated region = PR_FGD, far side = BGD), then remove wall pixels (HSV S<70 & V>150) and plant pixels (G ≥ R−5) in the hand region, keep largest component, blur 1.2. Always zoom-check hands before delivering.

## Text behind her
Draw letters (Titan, lilac + plum shadow), paste the original frame back through the mask. Split words around her body (measure mask x-extent at the text row; leave ~20 px from arms). Letters drop one by one with back-ease (1.2 frames stagger).

## Clean plate (empty room)
1. Temporal nanmedian over the shot with her masked out (compute in 120-row strips to save RAM).
2. Where she never moves (lying on the mat) the median is smeared → LaMa: `pip install simple-lama-inpainting --no-deps` + torch from PyPI (download.pytorch.org may be blocked). Hole = area covered in >25 % of frames, dilated 10–14 px; run at 960x540, paste back only inside the feathered hole.
3. If the wide hole erases furniture (armchair), use the narrow "always covered" hole in that region.
4. Inspect the plate; small missing props are OK if she covers them when she lands.

## Effects using it
- **Placed down**: 6 frames empty plate → her live cut-out descends from above (ease-out cubic 27 frames, scale 1.10→1, vertical motion blur when fast, growing soft floor shadow), last 4 frames blend to the original, lilac ripple ring at the feet.
- **Sticker flies into her** (chosen "B"): see carina-creative-transitions.
