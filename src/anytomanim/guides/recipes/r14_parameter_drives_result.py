# 卡 14：調一個值，看結果跟著變。同一 tracker 驅動讀值、拋物線與標記；座標軸不動。
from manim import *
from anytomanim.idioms import tracker_readout


class ParameterDrivesResult(Scene):
    def construct(self):
        heading = Text("One value controls the curvature", font_size=36).to_edge(UP)
        coefficient = ValueTracker(0.5)
        display = tracker_readout("a", coefficient, decimals=2, color=BLUE)
        display.move_to(LEFT * 4.6 + UP * 1.6)
        axes = Axes(
            x_range=[-2, 2, 1], y_range=[0, 8, 2],
            x_length=7, y_length=4, tips=False,
        ).shift(RIGHT * 1.3 + DOWN * 0.5)
        formula = MathTex("y=ax^2", color=BLUE).next_to(axes, UP, buff=0.3)
        curve = always_redraw(lambda: axes.plot(
            lambda x: coefficient.get_value() * x*x, color=BLUE))
        marker = always_redraw(lambda: Dot(
            axes.c2p(1, coefficient.get_value()), color=YELLOW,
        ))
        reference = DashedLine(axes.c2p(1, 0), axes.c2p(1, 8), color=GREY_D)
        self.play(FadeIn(heading), Create(axes), Write(formula), run_time=1.2)
        self.play(FadeIn(display), Create(reference), Create(curve), FadeIn(marker), run_time=1)

        # Both shape and marker read a, rather than interpolating hand-picked shapes.
        for value in (1.8, 0.3, 1.0):
            self.play(coefficient.animate.set_value(value), run_time=2, rate_func=linear)
            self.wait(0.3)
        curve.clear_updaters()
        marker.clear_updaters()
        display[1].clear_updaters()
        self.wait(1)
