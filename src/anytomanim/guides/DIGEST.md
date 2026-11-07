# DIGEST — stage 1 spec (host model executes this)

Distill the input into a **teaching brief** (markdown, saved as `brief.md`).

Input: a topic phrase, a textbook chapter, an arXiv paper (text or notes), or a
repo README/structure. Output must contain:

1. **Core question** — the single question the video answers (the hook).
2. **Key concepts in teaching order** — dependency-sorted; each builds on prior.
3. **The ONE main insight** — the "aha" the viewer must leave with.
4. **Required math notation** — formulas the video will show (LaTeX).
5. **Natural visual analogies** — what to draw for each concept (concrete,
   drawable: shapes, axes, flow arrows, labeled objects — not stock-photo ideas).
6. **Audience assumptions** — what the viewer already knows.

Rules:
- Keep it under ~500 words; a brief is a map, not the script.
- Prefer ONE worked example over three vague ones.
- If the input is a repo, the "concepts" are the system's story: what problem,
  what trick solves it, how the pieces connect — not API listings.
