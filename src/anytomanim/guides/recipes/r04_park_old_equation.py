# 卡 4：舊式退到角落，新式接上。保留低亮度通式，複製它展開特例。
from manim import *
from anytomanim.idioms import park_in_corner, copy_box_to


class ParkOldEquation(Scene):
    def construct(self):
        heading = Text("Use the determinant rule", font_size=38).to_edge(UP)
        old = MathTex(r"\det A=", "ad", "-bc").shift(UP * 0.7)
        old[1].set_color(BLUE)
        old[2].set_color(ORANGE)
        self.play(FadeIn(heading), Write(old), run_time=1.2)
        self.play(park_in_corner(old, corner=DL, scale=0.65), run_time=1.2)

        matrix = Matrix([[2, 1], [3, 4]]).scale(0.8)
        matrix.move_to(LEFT * 3.3 + UP * 0.7)
        new = MathTex(r"\det A=", r"2\cdot4", r"-1\cdot3")
        new.move_to(RIGHT * 1.3 + UP * 0.7)
        new[1].set_color(BLUE)
        new[2].set_color(ORANGE)
        self.play(Create(matrix), TransformFromCopy(old, new), run_time=1.5)

        # A second use of the travelling box links the retained rule to its use.
        box = SurroundingRectangle(old[1], color=BLUE, buff=0.18)
        self.play(Create(box), run_time=0.5)
        flying, flight = copy_box_to(box, new[1], run_time=1.2)
        self.play(flight, box.animate.set_stroke(opacity=0.4), run_time=1.2)
        label = Text("main diagonal", font_size=28, color=BLUE)
        label.next_to(new[1], DOWN, buff=0.7)
        self.play(FadeIn(label), run_time=0.6)
        self.wait(1.5)
