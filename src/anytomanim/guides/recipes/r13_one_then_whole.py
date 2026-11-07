# 卡 13：先看一個，再放回全部。聚焦一個試驗，完成正反機率後恢復整組。
from manim import *
from anytomanim.idioms import spotlight, unspotlight


class OneThenWhole(Scene):
    def construct(self):
        heading = Text("One trial inside six trials", font_size=38).to_edge(UP)
        coins = VGroup(*[
            Circle(0.48, color=BLUE, fill_opacity=0.35)
            for _ in range(6)
        ]).arrange(RIGHT, buff=0.7).shift(DOWN * 0.6)
        labels = VGroup(*[
            Text(str(i+1), font_size=28).move_to(coin)
            for i, coin in enumerate(coins)
        ])
        self.play(FadeIn(heading), Create(coins), Write(labels), run_time=1.2)
        selected = VGroup(coins[2], labels[2])
        others = [m for i in range(6) if i != 2 for m in (coins[i], labels[i])]
        selected.save_state()
        self.play(
            spotlight(others),
            selected.animate.scale(1.5).shift(UP * 1.3), run_time=1.2,
        )
        outcomes = MathTex(r"P(H)=\tfrac12,\quad P(T)=\tfrac12")
        outcomes.next_to(selected, UP, buff=0.7)
        self.play(Write(outcomes), run_time=1)
        self.wait(0.8)
        self.play(
            Restore(selected), unspotlight(others), FadeOut(outcomes), run_time=1.2,
        )
        note = Text("Each trial uses this same rule", font_size=28)
        note.next_to(coins, DOWN, buff=0.8)
        self.play(FadeIn(note), run_time=0.7)
        self.wait(1.3)
