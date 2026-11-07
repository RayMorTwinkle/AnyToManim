"""3b1b idiom library — building blocks for lively ManimCE scenes.

Independently implemented CE building blocks for narrated animation.
Two layers:

- MOVES: one-call animations/effects a scene author plays inside a voiceover
  block (emphasis, morphs, camera, continuous motion).
- ENTITIES: reusable mobject builders (waves, graphs...).

Everything is plain functions returning Mobjects/Animations — nothing here
knows about voiceover; pacing is the scene's job (SCENE_GUIDE.md).
"""
from manim import *
import numpy as np

from .stylelib import (BG, ACCENT, WARN, GOOD, MUTED,  # noqa: F401
                       set_bg, card, takeaway_line)


def pulse(mob, color=YELLOW, scale_factor=1.12, run_time=0.8):
    """The canonical 3b1b 'look here' — brief scale+color pop."""
    return Indicate(mob, color=color, scale_factor=scale_factor,
                    run_time=run_time)


def box_tour(box, target, run_time=0.6):
    """Retarget an existing SurroundingRectangle onto a new object —
    the 'highlight travels' move 3b1b uses constantly."""
    return Transform(box, SurroundingRectangle(
        target, color=box.get_color(), buff=0.18, corner_radius=0.1),
        run_time=run_time)


def make_box(target, color=WARN):
    return SurroundingRectangle(target, color=color, buff=0.18,
                                corner_radius=0.1)


def flash_on(mob, color=YELLOW, run_time=0.7):
    return Circumscribe(mob, color=color, run_time=run_time,
                        stroke_width=4, fade_out=True)


def swoosh(mob, color=ACCENT, run_time=1.0):
    return ShowPassingFlash(mob.copy().set_stroke(color, 6),
                            time_width=0.4, run_time=run_time)


def wobble(mob, run_time=0.8):
    return Wiggle(mob, run_time=run_time)


def draw_on(mob, run_time=1.2):
    """Outlines first, then fill — classier than FadeIn for diagrams."""
    return DrawBorderThenFill(mob, run_time=run_time)


def morph(src, dst, run_time=1.0):
    """THE 3b1b move: turn one object into another instead of swapping.
    `dst` REPLACES `src` on screen — afterwards animate/FadeOut `dst`, not
    `src` (a plain Transform would leave `src` on stage wearing dst's shape,
    and FadeOut(dst) would then do nothing: the classic leftover bug)."""
    return ReplacementTransform(src, dst, run_time=run_time, rate_func=smooth)


def piece_morph(src, dst, run_time=1.0, key_map=None):
    """Morph that keeps shared sub-pieces in place (equations, text): pieces
    with the same tex/glyphs glide to their new spot, the rest fade.
    `dst` replaces `src` on screen (same rule as morph)."""
    tex = (MathTex, Tex)
    if isinstance(src, tex) and isinstance(dst, tex):
        return TransformMatchingTex(src, dst, key_map=key_map or {},
                                    run_time=run_time)
    return TransformMatchingShapes(src, dst, run_time=run_time)


def text_to(src_text_mob, new_string, run_time=0.8, **kw):
    """Retype a Text object into a new string via morph (keeps position).
    Unlike morph(), `src_text_mob` stays the on-screen object (it just looks
    like the new string), so keep using that same variable afterwards."""
    new = Text(new_string, font_size=src_text_mob.font_size,
               **{k: v for k, v in kw.items() if k in
                  ("color", "weight", "slant", "font")})
    new.move_to(src_text_mob)
    return Transform(src_text_mob, new, run_time=run_time)


def zoom_in(scene, target, factor=0.5, run_time=1.2):
    """Push in on a detail. factor <1 = closer."""
    return scene.camera.frame.animate(run_time=run_time).scale(factor).move_to(target)


def pan_to(scene, point, run_time=1.0):
    return scene.camera.frame.animate(run_time=run_time).move_to(point)


def widen_view(scene, width, about_edge=LEFT, run_time=2.0):
    """Pull the camera back to `width`, ANCHORED at an edge — the classic
    3b1b 'zoom out to reveal' where existing content stays pinned on one
    side and new content slides in on the other."""
    frame = scene.camera.frame
    factor = width / frame.width
    return frame.animate(run_time=run_time).scale(factor, about_edge=about_edge)


def drift_cam(scene, vect=UP * 0.4, run_time=6.0):
    """Slow ambient camera drift — fills dead air without drawing attention."""
    return scene.camera.frame.animate(run_time=run_time, rate_func=smooth).shift(vect)


def breathe(mob, run_time=3.0):
    """Gentle there-and-back scale — keeps a static object alive."""
    return mob.animate(run_time=run_time, rate_func=there_and_back).scale(1.04)


def bob(mob, vect=UP * 0.12, run_time=2.5):
    return mob.animate(run_time=run_time, rate_func=there_and_back).shift(vect)


def spin(mob, angle=TAU, run_time=8.0):
    return Rotate(mob, angle, run_time=run_time, rate_func=linear)


def orbit(mob, about_point=ORIGIN, run_time=10.0):
    return Rotate(mob, TAU, about_point=about_point,
                  run_time=run_time, rate_func=linear)


def wave_text(mob, run_time=1.6):
    return ApplyWave(mob, run_time=run_time)


def traveling_dot(path_mob, run_time=2.0, color=YELLOW):
    """A dot that runs along an existing path (energy/packet/data)."""
    return MoveAlongPath(Dot(color=color, radius=0.08), path_mob,
                         run_time=run_time, rate_func=linear)


def park_in_corner(mob, corner=UL, scale=0.6, opacity=0.35, buff=0.5,
                   run_time=1.2):
    """Shrink and dim an old result at a frame corner without removing it.

    Opacity is a multiplier of the original fill/stroke alphas.

    Uses the default scene frame; for a moving camera, position relative to
    its frame explicitly instead. The original mobject keeps its identity.
    """
    return mob.animate(run_time=run_time).scale(scale).to_corner(
        corner, buff=buff).fade(1 - opacity)


def copy_box_to(source_box, target, color=None, buff=0.18, run_time=1.2):
    """Return (flying_box, animation) carrying a source outline to a target.

    Play the returned animation; the source box stays on stage. The flying
    copy remains at the target afterwards. Dim the source separately if needed.
    """
    flying = source_box.copy()
    destination = SurroundingRectangle(
        target, color=color or source_box.get_color(), buff=buff)
    return flying, Transform(flying, destination, run_time=run_time)


def lag_in(mobs, shift=UP * 0.2, lag_ratio=0.15, run_time=1.0):
    """Staggered entrance — 3b1b default for groups."""
    return LaggedStart(*[FadeIn(m, shift=shift) for m in mobs],
                       lag_ratio=lag_ratio, run_time=run_time)


def lag_out(mobs, lag_ratio=0.1, run_time=0.8):
    return LaggedStart(*[FadeOut(m) for m in mobs],
                       lag_ratio=lag_ratio, run_time=run_time)


def tour_boxes(scene, box, targets, per=0.6):
    """Highlight-tour a list of targets, narrating 'this, then this'."""
    for t in targets:
        scene.play(box_tour(box, t), run_time=per)


def others_of(scene, *focus):
    """Top-level scene mobjects that are not (and do not contain) `focus`."""
    keep = set()
    for f in focus:
        keep.update(id(m) for m in f.get_family())
    return [m for m in scene.mobjects
            if not any(id(x) in keep for x in m.get_family())]


def spotlight(others, opacity=0.4, run_time=0.8):
    """Dim `others` proportionally (save_state first), preserving empty fills.
    Typical: self.play(spotlight(others_of(self, subject))).
    always_redraw mobjects rebuild each frame and won't stay dimmed."""
    others = list(others)
    if not others:
        return Wait(run_time)
    for m in others:
        m.save_state()
    return AnimationGroup(*[m.animate.fade(1 - opacity) for m in others],
                          run_time=run_time)


def unspotlight(others, run_time=0.8):
    """Undo spotlight(): Restore every dimmed mobject."""
    others = list(others)
    if not others:
        return Wait(run_time)
    return AnimationGroup(*[Restore(m) for m in others], run_time=run_time)


def tracker_readout(name, tracker, decimals=2, font_size=36, color=ACCENT):
    """A label and reusable DecimalNumber bound to an existing ValueTracker.

    Returns a VGroup(label, number). Move the group freely; the number stays
    next to its label even when its digit count changes. Zero decimals rounds
    the display; use integer tracker endpoints when counting discrete objects.
    """
    label = Text(f"{name} =", font_size=font_size, color=color)
    number = DecimalNumber(tracker.get_value(), num_decimal_places=decimals,
                           font_size=font_size, color=WHITE)

    def update(m):
        m.set_value(tracker.get_value()).next_to(label, RIGHT, buff=0.15)

    number.add_updater(update)
    update(number)
    return VGroup(label, number)


def scene_clock(rate=1.0):
    """ValueTracker that counts scene seconds by itself. self.add(clock)
    to start it; clock.clear_updaters() to stop."""
    clock = ValueTracker(0)
    clock.add_updater(lambda m, dt: m.increment_value(rate * dt))
    return clock


def value_color(v, vmax=1.0, pos=(BLUE_E, BLUE_B), neg=(RED_E, RED_B)):
    """3b1b weight colouring: sign picks blue/red, |v|/vmax picks dark→light."""
    a = float(np.clip(abs(v) / vmax, 0, 1))
    lo, hi = pos if v >= 0 else neg
    return interpolate_color(ManimColor(lo), ManimColor(hi), a)


def curved_pointer(start, end, color=WARN, arc=-PI / 3, thickness=4):
    return Arrow(start, end, path_arc=arc, color=color,
                 stroke_width=thickness, buff=0.12)


def label_arrow(label, target, direction=UR, color=None, font_size=28):
    """Text label + curved arrow pointing at a mobject."""
    lab = Text(label, font_size=font_size,
               color=color or GREY_A).next_to(target, direction, buff=0.7)
    arr = curved_pointer(lab.get_bottom() if direction[1] > 0
                         else lab.get_top(), target.get_edge_center(direction))
    return VGroup(lab, arr)


def write_pair(text_mob, note_mob=None, run_time=1.0):
    anims = [Write(text_mob)]
    if note_mob is not None:
        anims.append(GrowArrow(note_mob))
    return AnimationGroup(*anims, run_time=run_time)


def gauge(label="value", lo="LOW", hi="HIGH", value=0.7,
          color=ACCENT):
    """A vertical meter that reads lo..hi; returns (group, bar)."""
    track = Rectangle(height=2.4, width=0.26, color=GREY_D, stroke_width=2)
    bar = Rectangle(height=2.0 * value, width=0.18, color=color,
                    fill_opacity=1, stroke_width=0).align_to(track, DOWN)
    hi_t = Text(hi, font_size=22, color=color).next_to(track, UP, buff=0.15)
    lo_t = Text(lo, font_size=22, color=GREY_A).next_to(track, DOWN, buff=0.15)
    lab = Text(label, font_size=24, color=GREY_A).next_to(track, RIGHT, buff=0.2)
    return VGroup(track, bar, hi_t, lo_t, lab), bar


def sine_wave(amplitude=0.5, wavelength=1.2, length=8.0, color=ACCENT,
             stroke_width=3, n=160):
    """One wavelength-styled sine curve; length in units."""
    xs = np.linspace(-length / 2, length / 2, n)
    return VMobject(color=color, stroke_width=stroke_width).set_points_smoothly(
        [np.array([x, amplitude * np.sin(TAU * x / wavelength), 0]) for x in xs])


def crest_lines(n=7, spacing=0.5, height=1.6, color=ACCENT, x0=0.0):
    """Vertical crest bars, as in a side-view of wavefronts."""
    return VGroup(*[Line(UP * height / 2, DOWN * height / 2,
                         color=color, stroke_width=3)
                    .move_to(RIGHT * (x0 + i * spacing))
                    for i in range(n)])


def flow(steps, colors=None, font_size=26, buff=0.6, direction=RIGHT):
    """Boxed step chain: 'input -> process -> output'."""
    boxes = VGroup(*[
        VGroup(RoundedRectangle(width=max(1.4, 0.35 * len(s)), height=0.7,
                                corner_radius=0.12,
                                color=(colors[i] if colors else ACCENT),
                                fill_opacity=0.1),
               Text(s, font_size=font_size))
        for i, s in enumerate(steps)])
    for b in boxes:
        b[1].move_to(b[0])
    boxes.arrange(direction, buff=buff + 0.4)
    arrows = VGroup(*[
        Arrow(boxes[i].get_right(), boxes[i + 1].get_left(), buff=0.08,
              color=GREY_B, stroke_width=3)
        for i in range(len(boxes) - 1)]) if np.allclose(direction, RIGHT) \
        else VGroup()
    return VGroup(boxes, arrows)


def array_cells(values, color=ACCENT, font_size=28, cell=0.8):
    """An array/list as numbered cells (CS topics)."""
    g = VGroup()
    for i, v in enumerate(values):
        c = Square(side_length=cell, color=color, stroke_width=2)
        t = Text(str(v), font_size=font_size).move_to(c)
        g.add(VGroup(c, t))
    g.arrange(RIGHT, buff=0)
    return g


def network(n=8, radius=1.8, color=ACCENT, p_edge=0.4, seed=7):
    """Random-ish node graph for networks/graph topics."""
    rng = np.random.default_rng(seed)
    nodes = VGroup(*[Dot(radius=0.1, color=color).move_to(
        radius * np.array([np.cos(TAU * i / n), np.sin(TAU * i / n), 0]))
        for i in range(n)])
    edges = VGroup()
    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < p_edge:
                edges.add(Line(nodes[i].get_center(), nodes[j].get_center(),
                              color=GREY_C, stroke_width=1.5))
    return VGroup(edges, nodes)


def dot_field(n=60, area=(10, 5), seed=3, color=GREY_B, r=0.035):
    """Scatter of dots — crowds, particles, data points."""
    rng = np.random.default_rng(seed)
    return VGroup(*[Dot(radius=r, color=color).move_to(
        [rng.uniform(-area[0] / 2, area[0] / 2),
         rng.uniform(-area[1] / 2, area[1] / 2), 0])
        for _ in range(n)])


def concentric(center, radii, color=ACCENT, width=3):
    return VGroup(*[Circle(radius=r, color=color, stroke_width=width)
                    .move_to(center) for r in radii])


def takeaway_card(lines, color=WHITE, font_size=40):
    """Final-beat card: rounded box + centered takeaway text."""
    t = Text("\n".join(lines) if isinstance(lines, (list, tuple)) else lines,
             font_size=font_size, color=color, line_spacing=1.2)
    box = RoundedRectangle(width=t.width + 0.8, height=t.height + 0.6,
                           corner_radius=0.15, color=ACCENT,
                           fill_color=ACCENT, fill_opacity=0.08)
    return VGroup(box, t)


def question_mark(color=YELLOW, font_size=80):
    return Text("?", font_size=font_size, color=color, weight=BOLD)


def big_brace(mob, direction=DOWN, color=GREY_B):
    return Brace(mob, direction=direction, color=color)


def axes_simple(x_range=(-4, 4, 1), y_range=(-2, 4, 1), size=(8, 4),
                numbers=True, x_label=None, y_label=None, font_size=24):
    """Plain axes with tick numbers (numbers=False for a bare sketch) and
    optional axis labels (str -> MathTex if it contains '\\' or '$', else Text).
    Returns Axes; labels (if any) are added as submobjects so they move with it."""
    ax = Axes(x_range=list(x_range), y_range=list(y_range),
              x_length=size[0], y_length=size[1],
              axis_config={"color": GREY_B, "stroke_width": 2,
                           "include_numbers": numbers,
                           "font_size": font_size},
              tips=False)

    def lab(s):
        return (MathTex(s.strip("$"), font_size=font_size + 8)
                if ("\\" in s or "$" in s) else Text(s, font_size=font_size + 4,
                                                       color=GREY_A))
    if x_label:
        ax.add(lab(x_label).next_to(ax.x_axis.get_end(), RIGHT, buff=0.25))
    if y_label:
        ax.add(lab(y_label).next_to(ax.y_axis.get_end(), LEFT, buff=0.25))
    return ax


