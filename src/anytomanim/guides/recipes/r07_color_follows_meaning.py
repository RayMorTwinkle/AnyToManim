# 卡 7：顏色跟著意思走。直角三角形的邊與平方項保持同一組語意配色。
from manim import *


class ColorFollowsMeaning(Scene):
    def construct(self):
        heading = Text("Lengths become symbols", font_size=38).to_edge(UP)
        a, b, c = BLUE, GREEN, ORANGE
        p = LEFT * 4 + DOWN * 1.5
        q = p + RIGHT * 3
        r = q + UP * 2.4
        base = Line(p, q, color=a, stroke_width=7)
        side = Line(q, r, color=b, stroke_width=7)
        hyp = Line(r, p, color=c, stroke_width=7)
        right_angle = RightAngle(Line(q, p), Line(q, r), length=0.25)
        la = MathTex("a", color=a).next_to(base, DOWN, buff=0.2)
        lb = MathTex("b", color=b).next_to(side, RIGHT, buff=0.2)
        lc = MathTex("c", color=c).next_to(hyp.get_center(), UL, buff=0.2)
        self.play(FadeIn(heading), Create(VGroup(base, side, hyp)), run_time=1.2)
        self.play(Create(right_angle), Write(VGroup(la, lb, lc)), run_time=0.8)

        formula = MathTex("a^2", "+", "b^2", "=", "c^2")
        formula.move_to(RIGHT * 2.8)
        for part, color in zip(formula[::2], (a, b, c)):
            part.set_color(color)
        self.play(Write(formula[1]), Write(formula[3]), run_time=0.5)
        # Separate flights and arcs keep the moving symbols from colliding.
        for source, target, arc in (
            (la, formula[0], PI / 3),
            (lb, formula[2], PI / 2),
            (lc, formula[4], -PI / 2),
        ):
            self.play(TransformFromCopy(source, target, path_arc=arc), run_time=1)
        self.wait(1.5)
