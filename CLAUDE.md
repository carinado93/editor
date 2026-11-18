# Carina Video Studio – instructions for Claude Code

You are working on Carina Dorca's video editor app (this repo). See BAUPLAN.md, PROGRESS.md and README.md.
All editing know-how lives in `.claude/skills/`. Before any video task, read
`.claude/skills/carina-studio-workflow/SKILL.md`, then the skill(s) it points to.

Rules that always apply:
- Ideas first (2–4 options), then preview (1280 px), final render only on her go.
- Text wording: propose, she approves, first person. Second language = translation table first.
- Never change her originals; never colour-grade her footage (exception, her decision 18 Nov 2026: Video Studio /
  Drone Cutter grades all clips, auto-grade on by default, skin tones protected, adjustable/off); never use other
  creators' footage.
- Prevention only: no healing promises, no diagnoses.
- Check every output by tiling frames (faces, hands/fingers, text edges) before showing it.
- Every reel ships with caption + exactly 5 hashtags + cover.
- Talk to her in simple German (she writes German or English; answer in her language).

The `scripts/` folders contain the real, tested Python renderers from the
"Day in my life" reel (Nov 2026). They have hard-coded paths/frame numbers:
turn them into parameterised effect modules (effect name + params + timing → frames),
keeping the approved default values.

Studio effects already in the app: `backend/editor_app/fx_studio.py` (group "E" in the effects panel).
New effects from the skills go there (or fx.py), registered in TYPES + effects.DESCRIBE, with a test frame in
tests/test_effects.py. Ask Carina before rebuilding or removing anything. Notes in PROGRESS.md are in English.
