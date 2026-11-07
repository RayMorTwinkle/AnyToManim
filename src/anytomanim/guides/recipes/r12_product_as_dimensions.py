# 卡 12：把乘積拆成長和寬。取出面積單元，標出因子，再鋪回總面積。
from manim import *


class ProductAsDimensions(Scene):
    def construct(self):
        heading = Text("Area is width times height", font_size=38).to_edge(UP)
        tiles = VGroup(*[
            Rectangle(width=1.1, height=1.6, color=BLUE, fill_opacity=0.35)
            for _ in range(4)
        ]).arrange(RIGHT, buff=0).shift(LEFT * 2.5)
        self.play(FadeIn(heading), Create(tiles), run_time=1.2)
        unit = tiles[0].copy().move_to(RIGHT * 3)
        self.play(TransformFromCopy(tiles[0], unit), run_time=1.2)

        width_brace = Brace(unit, DOWN, color=YELLOW)
        height_brace = Brace(unit, RIGHT, color=GREEN)
        width_label = MathTex("w", color=YELLOW).next_to(width_brace, DOWN, buff=0.15)
        height_label = MathTex("h", color=GREEN).next_to(height_brace, RIGHT, buff=0.15)
        product = MathTex("A_1=", "w", "h").next_to(unit, UP, buff=0.6)
        product[1].set_color(YELLOW)
        product[2].set_color(GREEN)
        self.play(Create(width_brace), Write(width_label), run_time=0.7)
        self.play(Create(height_brace), Write(height_label), run_time=0.7)
        self.play(Write(product), run_time=0.8)
        self.wait(0.7)

        self.play(
            Transform(unit, tiles[0].copy()),
            FadeOut(VGroup(width_brace, height_brace, width_label, height_label, product)),
            run_time=1.2,
        )
        self.remove(unit)  # The returned copy must not double-fill the original tile.
        total = MathTex("A=4wh").next_to(tiles, DOWN, buff=0.8)
        self.play(Write(total), run_time=0.8)
        self.wait(1.3)
