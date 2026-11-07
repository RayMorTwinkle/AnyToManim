# 卡 5：數量邊長邊數。每加一個方塊，整數讀值同拍增加一次。
from manim import *
from anytomanim.idioms import tracker_readout


class CountAsItGrows(Scene):
    def construct(self):
        heading = Text("Count the selected outcomes", font_size=38).to_edge(UP)
        count = ValueTracker(0)
        display = tracker_readout("selected", count, decimals=0)
        display.move_to(UP * 1.8)
        cells = VGroup(*[
            Square(0.85, color=BLUE, fill_opacity=0.35)
            for _ in range(6)
        ]).arrange(RIGHT, buff=0.32)
        labels = VGroup(*[
            Integer(i + 1, font_size=30).move_to(cell)
            for i, cell in enumerate(cells)
        ])
        self.play(FadeIn(heading), Create(cells), Write(labels), run_time=1.2)
        self.play(FadeIn(display), run_time=0.6)

        # Integer endpoints and a step rate function prevent fractional counts.
        boxes = VGroup()
        for i, cell in enumerate(cells):
            box = SurroundingRectangle(cell, color=YELLOW, buff=0.06)
            boxes.add(box)
            self.play(
                Create(box),
                count.animate(rate_func=lambda t: 0 if t < 0.5 else 1)
                .set_value(i + 1),
                run_time=0.5,
            )
        self.wait(1.2)
