# STORYBOARD — stage 2.5 spec (host model executes this)

Write `storyboard.json` after `beats.json` and before any scene code. This is
where a video gets its continuity. Read `ORCHESTRATION.md` first, then the runnable recipes
for the cards you plan to use.

Decide, for every beat, what happens to everything already on stage. Do not
leave that to the moment you write code.

## Format

Schema: `storyboard-schema.json`.

```json
{
  "beats": [
    {"id": "b01", "card": null, "keep": [],
     "change": [], "add": [{"id": "curve", "from": null}],
     "remove": [], "focus": "curve", "camera": "none", "clear_reason": null},
    {"id": "b02", "card": "only move what changes", "keep": ["curve"],
     "change": [{"from": "eq_v1", "to": "eq_v2", "how": "only the 2 slides out"}],
     "add": [], "remove": [], "focus": "eq_v2",
     "camera": "move in on eq_v2 so it fills the frame", "clear_reason": null}
  ]
}
```

- `id` values match `beats.json`, one entry per beat.
- `keep`: objects that stay as they are.
- `change`: object `from` becomes object `to`; `how` says what the viewer sees.
- `add`: new objects. Set `from` to the object it grows out of whenever you can.
- `remove`: needs a `reason`, naming why nothing later needs it.
- `focus`: where the eye should be at the end of the beat.
- `camera`: what the camera does and why, or `"none"`. Use it to get closer to a
  small focus and to make room for something new. A whole video of `"none"` is
  rarely right, and `storyboard` warns about it.
- `clear_reason`: required only when a beat keeps and changes nothing.

Object ids are short names you will reuse as variables in the scene code.

## Check it

```bash
anytomanim storyboard storyboard.json --beats beats.json
```

Fix errors. Read warnings and either fix them or be able to say why they are
fine. Then read it once more as a chain:

- Can you say how each beat grows out of the one before?
- Does each new symbol appear next to the thing it names?
- Do abstract words in the narration have something visible to point at?
- If a beat needs a clear, can a shrink, a dim or a camera move do the job?
- Does each shot use the whole frame? If the main picture would be small, or
  half the stage would be black, plan it larger or plan what fills the rest.
- Is anything kept or dimmed that no later beat uses? Remove it.

If the plan feels like slides, fix `beats.json` as well. The script may be
causing it, as in parallel points with no link between them.

## From storyboard to code

The storyboard is the contract for the scene. Use the same object ids as
variable names, and treat a divergence as a change to the plan: update
`storyboard.json` first. `preview` reports objects that stay on stage for many
beats; that is what you want when the storyboard keeps them on purpose. It also
warns about small content, empty bands and a fixed header.
