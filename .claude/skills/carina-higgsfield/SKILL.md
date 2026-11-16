---
name: "carina-higgsfield"
description: "Use when Carina wants AI-generated footage, an ad/promo video (e.g. for her book Not All At Once), a shot she didn't film, or asks whether Higgsfield is needed for a video."
---

# When and how to use Higgsfield for Carina's videos

## Decide first: Higgsfield or not?
Use Higgsfield ONLY when the video needs something that was not filmed:
- Ads/promos with movement that doesn't exist in her footage (e.g. throwing/catching the book, a hand grabbing it).
- Extending a clip, bridging two real clips (start frame + end frame → Seedance), clean plates (remove person/chair from a frame via image edit).
- Product shots / AI B-roll for the book "Not All At Once" or her coaching.
- Upscaling or reframing when she explicitly asks.

Do NOT use Higgsfield for:
- Adding text, highlights or animations to her own videos → use the carina-reel-edit skill (ffmpeg/PIL, free).
- Book pages / readable text / flip-throughs — AI can't do pages. Render them with Python/PIL from the real PDF pages.
- Anything she says should stay 100% her real footage.

Always tell her in one line WHY Higgsfield is needed and the credit cost BEFORE generating.

## Her rules for AI shots
- 100% realistic. No pauses, no camera jerks, no frame-by-frame stutter, no repeated or unreadable AI pages, correct scale.
- AI only for people/hands/motion, always guided by start and end frames from her real footage.
- Colour-match AI clips to the real footage; short crossfades (~0.3 s). Footage is not graded.
- Ads: max 20 s, 1080x1920. Music she adds later in Instagram.
- Check details: no visible feet/props that shouldn't be there, clean hands/nails, no slow awkward close-ups at the end.

## Book ad style (Not All At Once)
Cormorant Garamond (italic for the hook), cream card #F6EFE5, burgundy #6B1E3A, magenta #C2185B, terracotta #B5623E. Hook cards like "overwhelmed?" → "too many tasks?" → "this one is / for you." Current state and job IDs: project doc claude/book-ad-not-all-at-once.md (read it first for anything book-related).

## Workflow
1. Read get_workflow_instructions for multi-step videos; use models_explore(action:'recommend') if unsure about the model.
2. Costs (Seedance): 720p 4 s = 28 credits, 1080p 4 s = 48, draft 10 s = 24, finalize 1080p 10 s = 60. Check balance first. Draft at 720p, finalize only after she approves.
3. Source files: Google Drive "Selbständigkeit" (e.g. "test" subfolder). Drive connector only downloads <10 MB → import big videos into Higgsfield via public Drive link (media_import_url).
4. The Higgsfield sandbox resets fast: store scripts as files in Higgsfield (media_upload) and curl them back; never pkill with a pattern that matches your own command.
5. After each version, update the project doc with the version, job IDs and her feedback.