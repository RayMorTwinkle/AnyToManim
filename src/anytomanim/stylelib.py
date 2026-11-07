"""Style lib v1 — 3b1b-flavored tokens + helpers for generated scenes.

Generated scene code does `from anytomanim.stylelib import *` (after manim import)
to get a consistent look without re-deriving colors/layout each time.
"""
import os

from manim import (
    BOLD, DOWN, LEFT, RIGHT, UP, VGroup,
    SurroundingRectangle, Text, WHITE, config,
)

from .env import render_env

# Scenes may be launched by plain `manim` too: make sure MathTex finds latex.
os.environ["PATH"] = render_env()["PATH"]

BG = "#0e0e10"            # near-black background
ACCENT = "#58c4dd"        
ACCENT2 = "#ffff66"       # warm yellow highlight
WARN = "#e07a5f"          # orange-red for warnings / surprising results
GOOD = "#81b29a"          # soft green for confirmations
MUTED = "#9a9a9a"         # grey secondary text

DEFAULT_FONT_SIZE = 40


def set_bg(scene, color=BG):
    scene.camera.background_color = color


def card(text, color=WHITE, font_size=36):
    """Bordered fact card — the workhorse info chip."""
    t = Text(text, color=color, weight=BOLD, font_size=font_size)
    box = SurroundingRectangle(t, color=color, buff=0.25, corner_radius=0.12)
    return VGroup(t, box)


def title(text, font_size=52, color=WHITE):
    return Text(text, font_size=font_size, color=color, weight=BOLD).to_edge(UP, buff=1.2)


def subtitle(text, font_size=30, color=MUTED):
    return Text(text, font_size=font_size, color=color)


def takeaway_line(text, font_size=40, color=ACCENT):
    return Text(text, font_size=font_size, color=color)


def layout_cards(items, anchor_edge=UP, buff=0.55):
    """Stack fact cards vertically."""
    cards = [card(t, c) for t, c in items]
    g = VGroup(*cards).arrange(DOWN, buff=buff).to_edge(anchor_edge, buff=1.4)
    return g
