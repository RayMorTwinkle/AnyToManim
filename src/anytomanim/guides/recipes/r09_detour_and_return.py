# 卡 9：岔開一下，再回到原處。記錄圖形狀態，暫時剪切正方形，復原後才往下講。
from manim import *


class DetourAndReturn(Scene):
    def construct(self):
        heading = Text("A temporary shear", font_size=38).to_edge(UP)
        square = Square(2.4, color=BLUE, fill_opacity=0.35)
        base = Line(square.get_corner(DL), square.get_corner(DR), color=YELLOW)
        label = MathTex("A=bh").shift(DOWN * 2.3)
        self.play(FadeIn(heading), Create(square), Create(base), Write(label), run_time=1.3)
        square.save_state()
        original = square.get_all_points().copy()
        temporary = Text("Suppose we shear it...", font_size=28, color=YELLOW)
        temporary.next_to(square, UP, buff=0.5)
        self.play(FadeIn(temporary), run_time=0.6)

        # Shear around the bottom edge so base and height retain their meaning.
        bottom = square.get_bottom()[1]
        sheared = square.copy().apply_function(
            lambda p: p + RIGHT * 0.5 * (p[1] - bottom)
        )
        self.play(Transform(square, sheared), run_time=1.5)
        self.wait(0.8)
        self.play(Restore(square), FadeOut(temporary), run_time=1.5)
        assert np.allclose(square.get_all_points(), original)
        self.wait(0.7)  # Recognize the original before advancing the main thread.
        next_step = Text("Back to the square", font_size=28)
        next_step.next_to(square, UP, buff=0.5)
        self.play(FadeIn(next_step), run_time=0.6)
        self.wait(1)
