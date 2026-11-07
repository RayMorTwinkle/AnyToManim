# 卡 2：框住來源，再帶到結果。來源留著，複製框飛抵代入位置後才揭曉答案。
from manim import *
from anytomanim.idioms import copy_box_to


class BoxSourceToResult(Scene):
    def construct(self):
        heading = Text("Where does the 3 come from?", font_size=38).to_edge(UP)
        source = MathTex("x=", "3").move_to(LEFT * 3 + UP * 1.4)
        source[1].set_color(YELLOW)
        rule = MathTex("p(x)=x^2").move_to(RIGHT * 2 + UP * 1.4)
        target = MathTex("p(", "3", ")=3^2").move_to(DOWN * 0.6)
        target[1].set_color(YELLOW)
        self.play(FadeIn(heading), Write(source), Write(rule), run_time=1.2)
        source_box = SurroundingRectangle(source[1], color=YELLOW, buff=0.18)
        self.play(Create(source_box), run_time=0.6)

        # Lay out the destination first, but reveal only its non-source parts.
        self.play(Write(target[0]), Write(target[2]), run_time=0.8)
        flying, flight = copy_box_to(source_box, target[1], run_time=1.5)
        self.play(
            flight,
            TransformFromCopy(source[1], target[1]),
            source_box.animate.set_stroke(opacity=0.4),
            run_time=1.5,
        )
        self.wait(0.5)
        answer = MathTex("=9", color=GREEN).next_to(target, RIGHT, buff=0.35)
        self.play(Write(answer), run_time=0.8)
        self.play(Circumscribe(answer, color=GREEN), run_time=0.8)
        self.wait(1.2)
