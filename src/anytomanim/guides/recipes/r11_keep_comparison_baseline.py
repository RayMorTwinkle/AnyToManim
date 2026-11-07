# 卡 11：比較時基準不動。三個相同比例座標，基準拋物線從頭留到尾。
from manim import *


class KeepComparisonBaseline(Scene):
    def construct(self):
        heading = Text("Compare curvature on the same scale", font_size=36).to_edge(UP)
        panels = []
        for x in (-4.4, 0, 4.4):
            axes = Axes(
                x_range=[-2, 2, 1], y_range=[0, 8, 2],
                x_length=3.5, y_length=3.6, tips=False,
            ).move_to([x, -0.3, 0])
            panels.append(axes)
        self.play(FadeIn(heading), Create(panels[0]), run_time=1)
        baseline = panels[0].plot(lambda x: x*x, color=BLUE)
        baseline_label = MathTex("y=x^2", color=BLUE)
        baseline_label.next_to(panels[0], DOWN, buff=0.45)
        self.play(Create(baseline), Write(baseline_label), run_time=1)
        points = baseline.get_all_points().copy()

        # Same ranges and physical dimensions: only the coefficient differs.
        for axes, coefficient, color, tex in (
            (panels[1], 0.5, GREEN, r"y=\tfrac12 x^2"),
            (panels[2], 2, ORANGE, "y=2x^2"),
        ):
            curve = axes.plot(lambda x, a=coefficient: a*x*x, color=color)
            label = MathTex(tex, color=color).next_to(axes, DOWN, buff=0.45)
            self.play(Create(axes), Create(curve), Write(label), run_time=1.5)
            self.wait(0.5)
        assert np.allclose(baseline.get_all_points(), points)
        self.wait(1.5)
