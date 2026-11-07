# ORCHESTRATION — how objects relate from shot to shot

Good explanations are not lists of good animations. They are chains: each shot
grows out of the last one. Study this before you storyboard. Every rule here
is illustrated by the 14 runnable examples in `recipes/`.

## The one question

Before anything leaves the screen, ask: **can it become the next thing?**

Our weakest videos fail the same way: fade out, redraw. The viewer has to work
out for themselves how the new picture relates to the old one. In long 3b1b
scenes, objects stay about twice as long as ours (median 13 s vs 6–7 s), and 63%
derive new objects from existing ones (ours: 0–11%).

In order of preference, an object that is finished should:

1. **Become** the next thing (transform, copy from it, grow out of it).
2. **Step back**, still readable: dim it, shrink it, or move it to an edge. Do
   this only for something a later beat uses, or that the current beat refers to.
3. **Leave**, when nothing later refers to it, and say why in the storyboard.
   Keeping everything is its own failure: a faded label nobody needs again is
   residue, and the stage should grow into the room it leaves.

## Pick a card by situation

| Situation | Card |
|---|---|
| Simplifying or rewriting an expression | [01](recipes/r01_only_move_what_changes.py) only move what changes |
| "This value came from there" | [02](recipes/r02_box_source_to_result.py) box the source, carry it over |
| Reaching a conclusion with earlier work on screen | [03](recipes/r03_enlarge_conclusion.py) enlarge it, dim the rest |
| New form needed, old form still useful | [04](recipes/r04_park_old_equation.py) retire the old form to an edge |
| "How many" or "this quantity changes" | [05](recipes/r05_count_as_it_grows.py) count while it grows |
| Main picture stays but something must be added | [06](recipes/r06_camera_makes_room.py) move the camera to make room |
| The same quantity appears as shape and symbol | [07](recipes/r07_color_follows_meaning.py) color follows meaning |
| Adding a dimension or changing representation | [08](recipes/r08_embed_old_quantity.py) keep the old quantity inside the new picture *(tentative)* |
| A detail needs a temporary change | [09](recipes/r09_detour_and_return.py) detour, then return |
| A worked example becomes the general rule | [10](recipes/r10_example_to_general.py) the example grows into the formula |
| Comparing several cases | [11](recipes/r11_keep_comparison_baseline.py) keep one baseline fixed |
| A product, square or integral feels abstract | [12](recipes/r12_product_as_dimensions.py) turn factors into dimensions |
| The whole is too complex to take in at once | [13](recipes/r13_one_then_whole.py) study one, then return to all |
| A parameter drives a shape or behaviour | [14](recipes/r14_parameter_drives_result.py) turn a knob and watch *(tentative)* |

Choose each recipe according to the relationship it demonstrates. These are patterns, not quotas. Do not
force a card onto a beat that does not need it.

Combine recipes while preserving the identity of objects across transitions.

## Concreteness

Before you write a label such as "more overlap gives a larger coefficient", ask
whether the relation itself can be drawn. Prefer showing the quantity as length,
area, position or motion. Text on screen should name what is visible, not stand
in for what is missing.

## Attention

- One focus at a time. If more than three things are on stage, the storyboard
  must name the focus, and everything else recedes by brightness or size.
  Color alone does not direct the eye when everything is equally bright.
- After a change, leave about a second so the viewer can check it. In long 3b1b
  scenes the median gap between animations is 0–1 s, so do not stack long pauses
  either. Keep the picture moving by continuing the explanation, not by adding
  idle motion.
- Move the camera for a reason: to make room, to follow the question, or to look
  closer. Most long 3b1b scenes do this (about one move per minute). Decide it
  in the storyboard; `camera: "none"` on every beat is a warning sign.

## Use the whole frame

A frame that feels empty loses the viewer faster than one that feels full. Plan
each shot so the main picture takes up most of the stage, and let the camera or
a rescale take up any room that opens. There is no permanent title. See "Fill the
frame" in `SCENE_GUIDE.md`.

## What these numbers are

They describe 3b1b scenes over 30 seconds, from code that ran with placeholders.
They show differences, not targets. Do not tune a video to hit them. Causal interpretations of these observations remain inferences.
