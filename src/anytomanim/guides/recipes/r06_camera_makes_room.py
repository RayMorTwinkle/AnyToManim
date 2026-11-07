# 卡 6：鏡頭讓出空間。以下緣為基準拉遠，保留拋物線，在新增上方空間放問題。
from manim import *
from anytomanim.idioms import widen_view


class CameraMakesRoom(MovingCameraScene):
    def construct(self):
        axes = Axes(
            x_range=[-2, 2, 1], y_range=[0, 4, 1],
            x_length=7, y_length=3.6, tips=False,
        ).shift(DOWN * 0.7)
        curve = axes.plot(lambda x: x * x, color=BLUE)
        label = MathTex("y=x^2", color=BLUE).next_to(axes, RIGHT, buff=0.3)
        point = Dot(axes.c2p(1, 1), color=YELLOW)
        guide = DashedLine(axes.c2p(1, 0), point, color=YELLOW)
        self.play(Create(axes), Create(curve), Write(label), run_time=1.3)
        self.play(Create(guide), FadeIn(point), run_time=0.7)
        self.wait(0.5)

        # Frame height grows 8 -> 10; its lower world-space edge stays fixed.
        frame = self.camera.frame
        bottom = frame.get_bottom().copy()
        width = frame.width * 1.25
        self.play(widen_view(self, width, about_edge=DOWN), run_time=1.8)
        assert np.allclose(frame.get_bottom(), bottom)
        question = MathTex(r"\text{Slope at }x=1\;=\;???")
        question.move_to([frame.get_x(), frame.get_top()[1] - 1.0, 0])
        self.play(Write(question), run_time=1)
        self.play(Indicate(point, color=YELLOW), run_time=0.8)
        self.wait(1.5)
