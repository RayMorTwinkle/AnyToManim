---
name: anytomanim
description: Generate narrated 3Blue1Brown-style explainer videos from any topic, text, paper, or repo — via the `anytomanim` CLI toolchain. Audio-first pipeline — narration drives animation timing, so voice and visuals stay in beat-level sync. Use when asked to explain a concept as a video, animate a paper, make a tutorial, or produce a 3b1b-style clip.
---

# AnyToManim — CLI toolchain for narrated 3b1b-style videos

The product is a **CLI**, not an API harness. You (the host agent) do the
creative stages — write the brief, the beat sheet, the storyboard, the scene
code — guided by
the spec files shipped in the package. The CLI does everything deterministic:
TTS, duration measurement, rendering, concatenation.

## Install & check

```bash
pipx install anytomanim          # or: pip install -e . in a venv
anytomanim doctor                # reports missing deps + fix hints
```

## Workflow — export the spec, follow it

```bash
anytomanim export-guides ./guides   # WORKFLOW/DIGEST/SCRIPT/SCENE_GUIDE + schema
```

Then follow `guides/WORKFLOW.md`:
1. Write `brief.md` per `DIGEST.md`
2. Write `beats.json` per `SCRIPT.md` (+ `beats-schema.json`). Read
   `SCRIPT.md` first: narration has to chain, not list.
3. Read `ORCHESTRATION.md`, then write `storyboard.json` per `STORYBOARD.md`.
   Open the runnable recipes for the cards you pick. Run
   `anytomanim storyboard storyboard.json --beats beats.json` and fix it.
4. `anytomanim tts --beats beats.json` — synthesizes every beat, writes
   `audio_file` + real `audio_seconds` back (re-run after edits: only changed beats)
5. Write `scenes/*.py` per `SCENE_GUIDE.md` (`NarratedScene` +
   `MiMoService(beats_file=...)`, `with self.voiceover(beat="b01") as tr`).
   Follow the storyboard; start from the matching `recipes/`.
6. `anytomanim render scenes/X.py --quality ql` — fix & retry on error
7. `anytomanim preview <mp4>` — READ sheet.png and the per-beat report
   (overlaps, overruns, frozen beats, small content, empty bands, a fixed
   header, stage changes the storyboard does not mention); fix and re-render
   until clean
8. Render `--quality qh`, `anytomanim assemble a.mp4 b.mp4 -o final.mp4`,
   `anytomanim subtitles beats.json --mux final.mp4`

Iterate without a key / without cost: `ANYTOMANIM_TTS=draft` (local voice).

`anytomanim run "<topic>"` also exists — an embedded-LLM reference driver for
automated batch eval (requires an LLM API key; interactive agents should use
the guide-driven flow instead).

## Contracts

- `beats.json` is THE interface — public IR (narration + visual + audio_seconds).
- Audio-first sync: synthesize → measure → every `run_time` derives from
  `tr.duration`, and the render replays exactly those wavs. Never invent durations.
- A clean render is not done — look at the preview sheet every time.
- Continuity comes first. Before an object leaves, ask whether it can become
  the next thing. Fade out and redraw is the last resort.
- Draw the relation when you can, instead of writing it as a label.
- Voices: `--voice baihua|moli|milo`; clone your own voice via
  `assets/voice/<name>.mp3` + voices.json entry. zh + en supported.
- See `examples/` in the repo for golden end-to-end runs.
