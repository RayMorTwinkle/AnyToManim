# 卡 8：舊的量留在新圖裡。保留數線、原點和讀值點，從同一原點長出座標平面。
from manim import *


class EmbedOldQuantity(Scene):
    def construct(self):
        heading = Text("A number becomes an x-coordinate", font_size=36).to_edge(UP)
        # Build axes first for exact coordinate agreement, but show only x initially.
        axes = Axes(
            x_range=[-3, 3, 1], y_range=[-2, 2, 1],
            x_length=9, y_length=4, tips=False,
        ).shift(DOWN * 0.4)
        x_axis, y_axis = axes.x_axis, axes.y_axis
        point = Dot(axes.c2p(2, 0), color=YELLOW)
        value = MathTex("2", color=YELLOW).next_to(point, DOWN, buff=0.25)
        origin = MathTex("0", font_size=28).next_to(axes.c2p(0, 0), DL, buff=0.2)
        self.play(FadeIn(heading), Create(x_axis), Write(origin), run_time=1.1)
        self.play(FadeIn(point), Write(value), run_time=0.7)
        self.wait(0.6)

        # Reuse the exact same x-axis and point; no new number line is drawn.
        self.play(GrowFromPoint(y_axis, axes.c2p(0, 0)), run_time=1.2)
        horizontal = DashedLine(axes.c2p(-3, 1), axes.c2p(3, 1), color=GREY_D)
        self.play(Create(horizontal), run_time=0.7)
        pair = MathTex("(2,0)", color=YELLOW).move_to(value)
        self.play(ReplacementTransform(value, pair), run_time=0.9)
        note = Text("The x-value is still 2", font_size=28)
        note.to_edge(DOWN, buff=0.5)
        self.play(FadeIn(note), run_time=0.7)
        self.wait(1.4)
