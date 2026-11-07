# 卡 10：例子長成一般式。保留等長重複單位，將中間項壓成省略號並標明 n 個。
from manim import *


class ExampleToGeneral(Scene):
    def construct(self):
        heading = Text("Repeated lengths become a formula", font_size=36).to_edge(UP)
        cells = VGroup(*[
            Rectangle(width=1.3, height=0.6, color=BLUE, fill_opacity=0.35)
            for _ in range(4)
        ]).arrange(RIGHT, buff=0).shift(UP * 0.6)
        labels = VGroup(*[
            MathTex("d", color=BLUE).move_to(cell) for cell in cells
        ])
        concrete = MathTex("L=", "d+d+d+d", "=4d").shift(DOWN * 1.1)
        concrete[1:].set_color(BLUE)
        self.play(FadeIn(heading), Create(cells), Write(labels), run_time=1.2)
        self.play(Write(concrete), run_time=1)
        self.wait(0.6)

        # Preserve endpoints and equal units: n means the number of such units.
        ellipsis = MathTex(r"\cdots", color=BLUE)
        ellipsis.move_to(VGroup(cells[1], cells[2]))
        self.play(
            FadeOut(VGroup(cells[1], cells[2], labels[1], labels[2])),
            FadeIn(ellipsis), run_time=0.9,
        )
        brace = Brace(VGroup(cells[0], cells[3]), UP)
        count = MathTex(r"n\text{ equal lengths}", font_size=32).next_to(brace, UP, buff=0.15)
        general = MathTex("L=", r"\underbrace{d+\cdots+d}_{n\text{ terms}}", "=nd")
        general[1:].set_color(BLUE)
        general.move_to(concrete)
        self.play(TransformMatchingTex(concrete, general), Create(brace), Write(count), run_time=1.5)
        self.wait(1.5)
