# 卡 3：結論放大，其他退下。舊推導壓暗仍留場，結論放大並閃框。
from manim import *
from anytomanim.idioms import spotlight, unspotlight


class EnlargeConclusion(Scene):
    def construct(self):
        heading = Text("A geometric sum", font_size=38).to_edge(UP)
        first = MathTex(r"S=1+r+r^2+\cdots").shift(UP * 1.7)
        second = MathTex(r"rS=r+r^2+r^3+\cdots").shift(UP * 0.6)
        difference = MathTex(r"(1-r)S=1").shift(DOWN * 0.5)
        conclusion = MathTex(r"S=\frac{1}{1-r}", color=YELLOW)
        conclusion.shift(DOWN * 2)
        condition = MathTex(r"|r|<1", font_size=30)
        condition.to_corner(UR, buff=0.7).shift(DOWN * 0.8)
        self.play(FadeIn(heading), Write(first), Write(condition), run_time=1)
        self.play(TransformFromCopy(first, second), run_time=1.2)
        self.play(Write(difference), run_time=0.8)
        self.play(TransformFromCopy(difference, conclusion), run_time=1)

        # Keep the algebra available for checking; change only its salience.
        context = [first, second, difference, condition]
        self.play(
            spotlight(context),
            conclusion.animate.scale(1.3),
            run_time=1,
        )
        self.play(Circumscribe(conclusion, color=YELLOW), run_time=0.8)
        self.wait(3)
        self.play(unspotlight(context), run_time=0.8)
        self.wait(0.5)
