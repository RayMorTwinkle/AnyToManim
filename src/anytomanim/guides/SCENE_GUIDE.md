# SCENE_GUIDE — stage 3 spec (host model executes this)

Write ONE Manim `NarratedScene` per scene covering its beats. Class name:
match the filename (`SceneFoo.py` → `class SceneFoo`).

`storyboard.json` is your plan: use its object ids as variable names, and do
what it says with each object. Start from the `recipes/` for the cards it names.

## Required imports & setup

```python
import sys
from pathlib import Path
REPO = Path("<repo_root>")          # repo containing src/ + assets/
RUN = Path("<workdir>")             # holds beats.json + audio/
sys.path.insert(0, str(REPO / "src"))
from manim import *
from anytomanim.voiceover import NarratedScene, MiMoService
from anytomanim.stylelib import *    # set_bg, card, title, ACCENT, WARN, ...
from anytomanim.idioms import *      # the 3b1b vocabulary — USE IT

class MyScene(NarratedScene):        # self.camera.frame is available
    def construct(self):
        set_bg(self)
        self.set_speech_service(MiMoService(
            mode="preset", voice="白桦",          # same voice you ran `tts --beats` with
            beats_file=RUN / "beats.json"))      # ← reuses the measured wavs
        # ...beats below
```

- `beats_file=` makes every voiceover reuse the wav that `anytomanim tts
  --beats` already synthesized and measured — the audio in the video IS the
  audio whose `audio_seconds` you planned with (MiMo is not deterministic, a
  second synthesis would have a different length, and would cost twice). If a
  voiceover's text matches no beat, it synthesizes live and logs a warning.
- `with self.voiceover(beat="b03") as tr:` takes the narration from
  beats.json, so the scene never drifts from the script.
  It also selects that ID's exact WAV, including repeated narration.
  `self.voiceover(text=...)` still works when the normalized text identifies
  one beat; ambiguous text raises `ValueError`, so use `beat=`.
- `NarratedScene` is a `VoiceoverScene` that also writes `<Scene>.audit.json`
  next to the mp4 — what `anytomanim preview` reports from (see the end).
  Failed renders write `<Scene>.partial.audit.json` with `partial: true` and
  an `error`; failed beats add `status: "failed"` and `error`. The last good
  `<Scene>.audit.json` is preserved, so preview and subtitles still use the
  matching movie's timings. The render error names the partial audit's path;
  the next successful render deletes that partial file. Successful audit
  fields stay unchanged. `MiMoService(design="A low whisper", style="slow")`
  combines the voice design and style in its synthesis directive and cache
  identity.
- The camera can move in any `NarratedScene`: animate `self.camera.frame`.
- Voice-clone preset: `MiMoService(mode="voiceclone", clone_sample=REPO /
  "assets/voice/your-own-sample.wav", beats_file=...)`.

## The pacing pattern — NON-NEGOTIABLE

```python
with self.voiceover(beat="b01") as tr:
    self.play(Create(curve), run_time=tr.duration * 0.3)
    self.play(MoveAlongPath(dot, curve), Write(formula), run_time=tr.duration * 0.55)
    self.wait(tr.get_remaining_duration())
```

- `tr.duration` = the real measured seconds of THIS beat's narration.
- Fractions inside one beat should sum to about 0.85–0.9, never above 0.9; end
  every beat with `self.wait(tr.get_remaining_duration())`. A lower sum leaves
  the end of every beat frozen, and that adds up to a static video.
- NEVER write `run_time=2` or a guessed constant — durations come from audio.
- Beat-boundary transitions (~0.6s FadeOut etc.) may run after the block ends.

## Motion carries the explanation

Keep the picture moving by continuing the explanation. A 10 s beat usually wants
3–5 animation events, and pauses between them of about a second. That pause
lets the viewer check what changed, so it is not dead time.

A long pause while the viewer reads or studies a result is fine when the
narration is pointing at it. A frame frozen with nothing to look at is not.
Do not fill gaps with idle motion such as breathing, bobbing or camera drift
unless it reinforces what is being said (rings keep dripping while you talk
about drips). Add the next step of the explanation instead.

The best motion lasts as long as the sentence. While the narration describes a
process, run the process: a point travels the curve, a counter climbs, a wave
sweeps across, a tracker drives the shape. Give that one animation most of the
beat rather than finishing early and holding. `preview` warns about stretches
over 3 s with no change; each one needs the narration to be pointing at a result.

## Fill the frame

An underused frame is a worse failure than a busy one. Our weakest frames are a
thin row of small objects with black below it, or a graph in one corner of an
empty stage. A busy frame with a clear focus is fine, so do not thin things out.

- **Make the main picture big.** The usable area is about x from -6.6 to 6.6 and
  y from -2.8 to 3.6. The main picture should span most of that in at least one
  direction: `Axes(x_length=10.5, y_length=5.4)`, not a default-size plot pushed
  to the left. When a formula sits beside it, the picture keeps about 60% of the
  width and the column beside it fills the rest at a readable size.
- **Size to the stage, not to the object.** If a row of cells leaves the lower
  half black, make the cells larger, or put what they hold underneath: the
  chains, the keys, the calculation. Use the whole height.
- **No permanent title.** A title is for the opening at most. Have it leave or
  become something by the second beat. A heading fixed at the top for the whole
  video is a slide habit, and it takes space from the explanation. The same goes
  for a banner formula that is no longer being used.
- **Reframe when the stage changes.** After something leaves, the rest should
  grow into the room, or the camera should come closer. Do not leave the gap.
- **Use the camera to frame.** Move in when the focus is small, pull back when
  something new needs room. A video over a minute usually has a few moves, and
  each has a reason in `storyboard.json`. `self.camera.frame.save_state()` and
  `Restore(self.camera.frame)` bring you back; see `recipes/r06_camera_makes_room.py`.
- **Text is readable.** At 720p keep labels at `font_size` 28 or above and the
  main formula at 40 or above.
- **Dimmed means still readable.** Keep dimmed objects at opacity 0.4 or above.
  Below that it is residue: if nothing later needs it, remove it.

`preview` warns about small content, empty bands and a fixed header. Treat each
warning as a question and look at the frame. A narrow picture that fills the
height is fine; a fixed title or a half-black stage is not.

## Transform-first rule — the 3b1b soul

When object B is "the same thing changed", MORPH — don't swap:

```python
self.play(morph(eqn_v1, eqn_v2))          # Transform
self.play(text_to(label, "new wording"))  # keeps position, retypes
self.play(box_tour(hl_box, next_target))  # highlight travels
```

FadeOut+FadeIn is the last resort, for content with no relation to what is on
screen. See `ORCHESTRATION.md`: become the next thing, step back, then leave.

Use `TransformMatchingTex` when a formula is rewritten, and `TransformFromCopy`
when the source should stay on screen.

**Who is on stage after a morph** (the #1 source of leftover junk):

| call | afterwards the on-screen object is |
|---|---|
| `morph(a, b)` / `piece_morph(a, b)` | **`b`** — FadeOut/animate `b`, never `a` |
| `text_to(label, "…")` | **`label`** (same variable, new look) |
| raw `Transform(a, b)` | **`a`** wearing b's shape — avoid; `b` is NOT on stage |

## Make every change VISIBLE

If the quantity you are animating changes by less than ~10% of its on-screen
size, the viewer sees nothing (a bar shrinking 365/365 → 362/365 is 0.8%).
Then: zoom in on the edge that moves (`zoom_in`), show the
change as its own object (a growing "gap" bar, a running counter), jump to a
later step where the difference is big, or exaggerate the scale and say so.

## The idiom vocabulary (`anytomanim.idioms`)

Emphasis: `pulse` `flash_on` `swoosh` `wobble` `make_box`+`box_tour`
(touring highlight) `draw_on`.
Transforms: `morph` `piece_morph` `text_to`.
Camera: `zoom_in` `pan_to` `widen_view` `drift_cam`;
to undo a zoom, `frame.save_state()` first and `Restore(frame)` after.
Continuous: `breathe` `bob` `spin` `orbit` `wave_text` `traveling_dot`

Choreography: `lag_in` `lag_out` `tour_boxes` `curved_pointer`
`label_arrow` `write_pair`.
Focus: `others_of(self, subject)` + `spotlight` / `unspotlight` (dim the
crowd to ~0.4 opacity instead of removing it; restore after).
Continuity: `park_in_corner` (retire an object to an edge, dimmed),
`copy_box_to` (a box travels from source to destination), `tracker_readout`
(a ValueTracker shown on screen). See `recipes/`.
Entities: `gauge` `sine_wave` `crest_lines` `flow` `array_cells` `network`
`dot_field` `concentric` `takeaway_card` `question_mark` `big_brace`
`axes_simple`.

Read `src/anytomanim/idioms.py` — signatures and docstrings are the spec.

## More idiom ideas (not a straitjacket)

For orchestration, `ORCHESTRATION.md` and `recipes/` come first. These are
smaller idioms for specific subjects.

- Hook question → subject `lag_in` + `zoom_in` + `question_mark`
- Explaining a mechanism → `morph` chains + `box_tour` across parts
- Comparison → two entities side by side, `swoosh` the winner/difference
- "Watch what happens" → continuous emission/loop while narration runs
- Key number/formula → `flash_on` or `Circumscribe`, then `zoom_in`
- Takeaway → return to the opening object with what was learned; dim the rest
  rather than clearing it (case 03)
- Equation reasoning → `piece_morph` term-by-term, `big_brace` annotations
- One item among many → `spotlight(others_of(self, item))`, talk about it,
  `unspotlight(...)` before moving on (keep the list in a variable)

## Rate functions — vary them

- default `smooth` is fine for most plays
- `linear` ONLY for rotations/loops/travel (`spin`, `traveling_dot`)
- `rush_into`/`rush_from` for punchy entrances/exits
- `there_and_back` for pulses, probes, pings
- `wiggle` for "this is weird" emphasis
- compose: `squish_rate_func(smooth, 0.6, 1)`, `smooth(smooth(t))` for
  extra-slow cinematic moves

## Layout rules

- Layout ONLY via `to_edge`, `next_to`, `arrange`, `align_to`, `VGroup` — no
  raw `.move_to(x*RIGHT)` guessing.
- Font sizes: anything the viewer must READ ≥ 32 (headline numbers 48–96);
  tick labels / minor annotations ≥ 24. The audit flags text under 24.
- Fill the frame: the main subject should span roughly half the frame width;
  a lone small object in a sea of black reads as a slide, not a 3b1b shot.
- When subtitles will be burned in, keep the bottom ~20% of the frame clear.
- Never Write on top of still-visible text. Make room first: move, shrink or
  dim what is there, or move the camera. Remove it only if the storyboard does.
  Track every mobject.
- stylelib tokens: `BG #0e0e10`, `ACCENT #58c4dd`, `ACCENT2`, `WARN #e07a5f`,
  `GOOD #81b29a`, `MUTED`. Use them, don't invent palettes.
- ManimCE v0.22 API only. No external assets/images. Subcaptions are automatic
  (manim-voiceover writes the .srt).

## Render, LOOK, fix — every time

```bash
anytomanim render workdir/scenes/MyScene.py --quality ql     # → mp4 + audit
anytomanim preview workdir/media/videos/MyScene/480p15/MyScene.mp4
```

A clean render is not a finished scene. `preview` writes `sheet.png` (two
frames per beat: mid-beat and the beat's last frame) and prints a per-beat
report. **Open sheet.png and read it like a viewer**, then fix and re-render
until both are clean:

- `← since b02` next to an object on a later beat = it is still on stage.
  Check it against the storyboard. A kept diagram is what you want. Old text or
  a morph source that the storyboard does not keep is a leftover.
- `! overlap`, `! off-frame`, `! small text` — layout errors.
- `! overrun` — the visuals in that beat take longer than its narration; the
  next sentence starts while this beat's animation is still playing. Lower
  the fractions.
- `! static NN%` — the frame is frozen for that share of the beat. Fine if the
  narration is pointing at something on screen; otherwise add the next step of
  the explanation (see "Motion carries the explanation").
- Things only the sheet shows: cramped or empty composition, elements
  colliding with non-text shapes, a change too small to see, a beat whose
  picture does not match what the narration says.

Iterate with `--quality ql` (and `ANYTOMANIM_TTS=draft` while the script is
still changing — local voice, no API cost); render `qh` once at the end.

On a render ERROR read the traceback tail, fix, retry — max 3 rounds. Known traps:

- **`Cannot open a video segment while another segment is still open`** —
  usually an EMPTY AnimationGroup/LaggedStart (e.g. built from a filter that
  matched nothing) or scheduled play times exceeding the tracker's duration.
- Fractions above 0.9 in one beat leave no headroom, and a transition after the
  block can still run past it.

Long videos: split beats into ~8-beat chunks → `SceneA.py`, `SceneB.py` →
`anytomanim assemble a.mp4 b.mp4 -o final.mp4`.
