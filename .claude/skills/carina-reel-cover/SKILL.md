---
name: "carina-reel-cover"
description: "Use whenever Carina makes or gets a Reel/Short (or asks for a reel cover / 'coperti reels' / cover photo): deliver a 1080x1920 cover with her photo in her Canva cover style, one format per reel, rotating."
---

# Carina's reel covers ("Coperti reels")

Every reel Claude makes or edits for Carina also gets a cover picture. Her template is the Canva design "Coperti reels" (Instagram Story size, 1080x1920, 3 pages = 3 formats). Recreate it exactly; do not invent new layouts.

## Workflow (her rules, 6 Oct 2026)
1. Pick ONE frame of her from the reel video (looking good, face clear, ideally with free space above her head). Crop it to 9:16 and SEND HER THE PHOTO FIRST. Wait for her OK before building the cover.
2. Make only ONE format per reel. Rotate the formats from reel to reel in this order: purple -> light -> olive -> purple ... (check the project doc claude/video-edit-workflow.md for which format the last cover used, and note the new one there).
3. Deliver the cover PNG (cover_<reel>_<format>.png in /mnt/user-data/outputs/reel-covers/) with SendUserFile.

## The 3 formats (measured from her Canva design)
All use the font **Noto Serif Display, Regular 400**, centred, no shadow, no extra elements. Her photo fills the whole frame, colour overlay on top at **60% opacity**.

1. **purple**: overlay #835DC0 @ 60%. Text WHITE #FFFFFF, large (~155 px, line step ~218 px), short words stacked (2-3 lines, like "Cornell / case"), upper part (top ~120-170 px).
2. **light**: overlay pale cream #EBEECA @ 60% (washed-out look). Text purple #6845A0, smaller (~93 px, line step ~129 px), 2-5 lines.
3. **olive**: overlay olive #75733B @ 60%. Text soft lilac-pink #D1B4D1 (~117 px, line step ~161 px), ONE word per line stacked (like "Not / All / At / Once"), upper part (top ~150 px).

## Text
- 3-4 words max, a hook matching the reel (e.g. "Stop checking your pulse", "Replaying every conversation?").
- Never cover her face: text above her head. Auto-shrink a line if wider than ~940 px.

## Photo
- Extract several frames with ffmpeg and LOOK at them; prefer frames with her hands/gesture or looking at camera, and headroom above her head.
- 16:9 source: crop a 608x1080 portrait slice around her, scale to 1080x1920. If there is no room above her head, place the photo ~380 px lower and fill the top with a heavily blurred copy of the same image (soft gradient on the seam).
- 9:16 source: use the frame directly.

## Build
- HTML + Playwright at 1080x1920, Noto Serif Display woff2 (fetch via the browser pane from Google Fonts; the cloud can't reach Google Fonts directly).
- Check the cover image (Read it): text not over her face, no overflow, overlay colour right.
## Added 15 Nov 2026
- She may send her own photo instead of a video frame (mirror selfie) – use it. If no headroom: move the photo down ~290 px and fill the top with a blurred stretch of the top 80 px strip.
- Landscape YouTube videos also get a 16:9 thumbnail (1280x720) in the same format: blurred photo background, sharp photo on the right, olive overlay, text left ("My day / in stats").
- German version of the same reel = same format, German words ("Mein / Tag / in / Zahlen").
- Rotation log lives in the project doc claude/video-edit-workflow.md (last: olive on 15 Nov → next purple).
