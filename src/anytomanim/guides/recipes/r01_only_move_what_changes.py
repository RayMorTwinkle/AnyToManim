# 卡 1：只動變的部分。整條式子留在畫面上，只有被移項的常數跨過等號。
from manim import *


class OnlyMoveWhatChanges(Scene):
    def construct(self):
        heading = Text("Move one term", font_size=38).to_edge(UP)
        before = MathTex("x", "+3", "=", "7").scale(1.8)
        after = MathTex("x", "=", "7", "-3").scale(1.8)
        before[0].set_color(BLUE)
        after[0].set_color(BLUE)
        before[1].set_color(YELLOW)
        after[3].set_color(YELLOW)
        self.play(FadeIn(heading), Write(before), run_time=1.2)
        self.wait(0.6)

        box = SurroundingRectangle(before[1], color=YELLOW, buff=0.12)
        self.play(Create(box), run_time=0.6)
        self.play(
            TransformMatchingTex(
                before,
                after,
                key_map={"+3": "-3"},
                path_arc=-PI / 3,
            ),
            FadeOut(box),
            run_time=1.8,
        )
        self.wait(1.0)  # Let the viewer compare it with the same equation.
        note = Text("Subtract 3 from both sides", font_size=28)
        note.next_to(after, DOWN, buff=0.8)
        self.play(FadeIn(note), run_time=0.6)
        self.wait(1.0)
