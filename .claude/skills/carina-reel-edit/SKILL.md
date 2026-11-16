---
name: "carina-reel-edit"
description: "Use when Carina sends a video (CapCut export, Drive link, raw clip) for a Reel, YouTube Short or YouTube video and wants text, highlights or animations added, or asks for a reel idea/hook."
---

# Carina's Reels / Shorts editing

Carina cuts her own videos in CapCut and posts to Instagram Reels, YouTube Shorts and YouTube. Claude adds polish on top; Claude does NOT re-edit her video.

## Always deliver with every reel (her rule, 8 Oct 2026)
Every finished reel comes with ALL of these, without her asking:
1. The reel video.
2. A caption (in the reel's language; German for @carinadorca.coach, English for @carina.dorca) with save/share CTA, a comment question and the follow line.
3. Exactly 5 hashtags (not more).
4. A reel cover, made with skill carina-reel-cover (send the cover photo first, wait for OK, then the cover PNG).

## Golden rules (never break unless she asks)
- Never change format, length, speed or the course of the video. No cutting words/pauses, no cropping to 9:16, no stretching, no slow-mo/reverse, no zoom punches.
- No colour filter / grading. Keep her original look. Keep black bars from the CapCut export.
- Only add/improve on-screen text and text backgrounds, in her brand colours.
- Text cards must NEVER cover her (face, hair, hands, watch). Check frames first.
- No subtitles (she adds them in CapCut). Audio untouched; at most a subtle whoosh/pop on transitions. She adds trending music in the Instagram app.

## Input
- Ideal: her finished CapCut cut (1080p, under 400 MB) + the CapCut auto-caption SRT (English) from the same cut, dropped in her folder or Google Drive (folder "Selbständigkeit").
- Drive connector only downloads files <10 MB; for bigger files ask her to put it in the connected folder or use a public Drive link.
- Use SRT cue times to time highlights per word.

## Brand text style
- Cream card #F4EEE4 (slightly transparent, rounded corners, soft shadow), dark brown text #4A3A30.
- Lilac #CDBFE0 for highlight / pill / answer box; darker lilac #7A649E for italic key phrase and strike-through lines; olive #6B6F3A for a small divider line.
- Fonts: SAME as her carousels (she wants one font system everywhere): Cormorant Garamond for headlines/hooks, with lilac Cormorant Garamond Italic for the key phrase; plain regular sans (Arial/Helvetica style) for supporting lines. Do NOT use Poppins or Lora anymore. Cormorant is thin, so use it large (and SemiBold/Bold weight) on video so it stays readable.
- Favourite device: statement → animated strike-through → answer revealed in a lilac box (e.g. "that's not your intuition" → "it's an intrusive thought.").
- Title/hook card visible from frame 0 (a hook that's on screen too briefly or in a thin font over a bright sky flopped).
- Only put words she actually says on cards (unless it's a hook/title).
- Safe zone for vertical Reels/Shorts: text centred, max ~780 px wide, roughly y 1180–1540, nothing on the right edge (UI buttons). For 16:9 footage, place cards in empty areas of the frame, with a margin (~100 px) from the edge, centred and professional.

## Pipeline
1. Probe the video (ffprobe), grab frames at several timestamps and LOOK at them to find free space.
2. Plan cards + timings; for anything bigger than a small tweak, send her the plan in 3–5 lines first.
3. Render overlays (PIL/HTML → PNG sequence or ffmpeg drawtext/overlay), composite with ffmpeg, copy audio stream untouched.
4. Export H.264, crf 20, maxrate 5M, under 30 MB, same resolution/fps as the input. Name: <source>_<topic>_v<N>.mp4.
5. Check: extract frames at each text change and look at them. Duration must equal the input.
6. Deliver the video together with caption, 5 hashtags and cover (see "Always deliver"), commit to her folder if connected, and add a line to the project doc claude/video-edit-workflow.md with what she liked/rejected.

## Reel ideas & hooks
When she asks for a reel idea: give 3 hooks max, specific and relatable (anxiety, burnout, overwhelm, her book "Not All At Once"), with on-screen text lines and a caption. Text-on-screen reels need the quote on screen long enough to read (~1 s per 3–4 words) and a large, readable font.