# AnyToManim — agent workflow contract

Seven stages, two kinds. The **host model** (you — Claude Code, Codex, Devin,
any agent that can run shell commands) performs the four creative stages by
following the prompt specs in this directory. The **`anytomanim` CLI** performs
the deterministic stages. You never need an LLM API key — you ARE the LLM.

```
input (topic/paper/repo notes)
   │ ① write brief.md          — follow guides/DIGEST.md
   │ ② write beats.json        — follow guides/SCRIPT.md + beats-schema.json
   │ ③ write storyboard.json   — follow guides/ORCHESTRATION.md + STORYBOARD.md
   ▼
anytomanim storyboard storyboard.json --beats beats.json
   ▼
anytomanim tts --beats beats.json      (synthesizes every beat → audio/bXX.wav,
                                        writes audio_file + audio_seconds back;
                                        re-run after editing narration: only
                                        changed beats are resynthesized)
   │ ④ write scenes/*.py       — follow guides/SCENE_GUIDE.md; recipes/ and
   │                             recipes/ demonstrate the cards your storyboard uses
   ▼
anytomanim render scenes/MyScene.py --quality ql      (→ mp4 + MyScene.audit.json)
anytomanim preview media/videos/MyScene/480p15/MyScene.mp4
   │ ⑤ LOOK: read preview sheet.png + the report; fix leftovers, overlaps,
   │   overruns, frozen beats, weak composition → re-render. Errors → fix,
   │   retry (≤3 rounds). Repeat until the sheet looks like a finished video.
   ▼
anytomanim render scenes/MyScene.py --quality qh      (final quality)
anytomanim assemble scene1.mp4 scene2.mp4 -o final.mp4
anytomanim subtitles beats.json --mux final.mp4       (timing from the audit)
anytomanim bgm final.mp4 bgm.mp3 -o final_bgm.mp4     (optional music bed)
   ▼
final.mp4 (+ final_subs.mp4 with selectable en/zh/bilingual subtitle tracks)
```

All paths may be relative to where you run the command. `render` puts media
in `<scene dir>/../media` (i.e. `workdir/media`) unless `--media-dir` is given.
Each render isolates its movie outputs and succeeds only if that invocation
produces a movie at the requested quality. A scene with no animations fails;
previous movies are never used as evidence of success. LaTeX, Text and speech
caches persist between renders. Render disables Manim's online version check.

## Contracts

- **beats.json** is THE interface between planning and rendering. Public,
  stable, schema in `beats-schema.json`. Hand-write it, LLM-write it, edit
  it — the downstream tools only read it.
- **Audio-first A/V sync**: synthesize narration FIRST (`tts --beats`), then
  every animation is paced by `tr.duration`, and the scene's
  `MiMoService(beats_file=...)` plays exactly those measured wavs — see
  SCENE_GUIDE.md. Never invent durations.
- **Draft voice**: `ANYTOMANIM_TTS=draft` swaps MiMo for the local macOS
  voice (no key, no cost) while you iterate on script and layout. To switch
  to real voice, unset it and run `tts --beats`: draft audio is
  automatically invalidated. `--force` always regenerates, even when inputs
  are unchanged.
- **Resume**: `tts --beats` and the embedded pipeline share input
  fingerprints. Older manifests without `audio_fingerprint` resynthesize
  once on their next TTS run; prerecorded scene replay continues to accept
  their existing audio. Successful beats are checkpointed even if others
  fail; the command exits nonzero and names failures. Concurrent TTS runs on
  one manifest serialize, and manifest/WAV replacements are atomic.
- **Voices**: `anytomanim tts --voice baihua|moli|milo` presets
  (default: beats.json `voice`, else `baihua` for zh, `milo` for en);
  users can clone their own voice
  by
  dropping a ≤10MB sample under `assets/voice/` + a voices.json entry.
- **Preview**: `--every` must be finite and positive. Failed narrated
  renders retain `<Scene>.partial.audit.json` (`partial: true`, `error`, and
  failed-beat status). The render error names this diagnostic's path. The
  last good `<Scene>.audit.json` stays paired with its movie; preview and
  subtitles do not auto-select partial audits. The next successful render
  removes any stale partial audit.
- **Long inputs**: split beats into ~8-beat scenes, render each, `assemble`.
- **Subtitles**: optional per-beat `subtitle: {"en": ..., "zh": ...}` in
  beats.json (the host writes the translations). `anytomanim subtitles`
  emits `beats.<lang>.srt` + `beats.bilingual.srt` (long lines split into
  several cues, including unpunctuated CJK and long Latin segments);
  audit-timed cues follow scene chronology even if beats.json has a
  different order. `--mux` embeds them as selectable mov_text tracks in the
  mp4. Timing comes from the render's `<Scene>.audit.json` (auto-found next
  to the `--mux`/`--burn` video, or `--audit`), else `--ref-srt`; with
  neither it is estimated and will drift — the command warns. For a
  multi-scene `assemble`d video, subtitle each scene's mp4 before
  assembling, or pass the estimated route knowingly.
- **Burned subtitles**: `anytomanim subtitles ... --burn final.mp4
  --burn-srt bilingual` hard-burns one track (default bilingual). Uses the
  imageio_ffmpeg bundled ffmpeg (has libass); zh needs a CJK font — default
  "Hiragino Sans GB" (macOS). Subtitle filenames may contain punctuation.
  Keep the bottom ~15% of the frame clear, and use everything above it.
- **BGM**: `anytomanim bgm final.mp4 music.mp3 -o out.mp4` mixes a music bed
  with sidechain ducking (narration pushes music down, bed swells in
  pauses). `--level -18` makes it quieter, `--no-duck` keeps a constant
  level. Music source: any local file — e.g. ace-step-mac
  (`~/repos/ace-step-mac`, `DURATION=90 CAPTION="..." ./ace-step.sh --cli`,
  writes /tmp/ace-req*.mp3).
- Start every session with `anytomanim doctor` — it reports missing deps
  (latex/ffmpeg/manim) with fix hints.

## Evaluate any video, including external baselines

The product combines a creation skill, media tools, and an independent
evaluator. Evaluation takes an MP4; beats and Manim audits are not required.

```bash
anytomanim eval final.mp4 --json
anytomanim eval final.mp4 --audit Scene.audit.json --spoiler '42:30' '答案:60'
anytomanim judge ours.mp4 baseline.mp4 --topic 'Bayes theorem' --runs 3 --seed 0
anytomanim blind ours.mp4 baseline.mp4 -o blind-review --seed 0
```

`eval` reports duration/resolution/fps/audio, freeze, silence, black frames,
edge contact, scene-score changes, offline macOS Vision OCR, and optional
spoiler/audit diagnostics. It never synthesizes an overall score. Flags exit
0: review them in context. Corrupt inputs exit nonzero. OCR/compiler failure
is reported without dropping the other metrics; spoiler checks then remain
unverified. Vision is compiled once in the system temp cache, configurable
with `ANYTOMANIM_CACHE_DIR` (no downloads or API keys).

Thresholds live as named constants in `evaluate.py`: freezes use noise 0.001
and minimum 2s; silence uses -35dB and minimum 1s; black uses minimum 0.1s,
pixel threshold 0.10 and picture threshold 0.98. Scene changes use score
>0.01. Flags review freeze >30%, silence >20%, black >10%, edge contact >10%
of samples, and fewer than 2 scene changes/min. Edge sampling is 2 fps at
width <=320: compare pixels with the median corner color (distance >35),
then flag a 2% edge ring when >2% of its pixels differ. This is a clipping
proxy; full-bleed graphics, backgrounds and subtitles can trigger it.
Static diagrams need not be bad, and gradual builds may miss scene detection.
OCR samples at 1 fps in zh-Hant, zh-Hans and English; first appearance means
first observed sample, not exact reveal time. Text coverage weights each
sample by up to one second, including the final partial second.

`judge` uses a logged-in Codex CLI, with network access to its model. It
attaches equally sized 12-frame sheets with timestamp labels and untrusted
OCR data. Only generic Video 1/2 labels reach the prompt. A seeded starting
order alternates; odd run counts leave one extra starting-order presentation.
Scores (1-5 plus timestamp evidence) cover accuracy, explanation, legibility,
pacing and polish. The judge cannot hear audio: narration correctness and
audio pacing remain unverified, and sparse sheets limit motion judgments.
Failures remain in the JSON; at least one run must succeed. Means and wins
map back to A/B. Agreement is the largest winner-category fraction among
successful runs, treating ties as a category, not statistical confidence.

`blind` copies bytes under shuffled opaque names. Give reviewers only the
MP4s; keep the separate `key.json` private. File blinding cannot conceal
branding or stylistic clues visible inside a video.

## File layout in a workdir

```
workdir/
  brief.md            # stage 1 output (host writes)
  beats.json          # stage 2 output (host writes) — THE contract
  storyboard.json     # stage 3 output (host writes) — every object's fate
  audio/bXX.wav       # anytomanim tts --beats output
  scenes/*.py         # stage 4 output (host writes)
  media/videos/**.mp4 # anytomanim render output (+ .audit.json, _preview/)
  final.mp4           # anytomanim assemble output
```
