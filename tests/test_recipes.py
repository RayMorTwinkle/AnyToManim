"""Importable standalone recipes and reusable choreography contracts."""
import argparse
import ast
from contextlib import redirect_stdout
import importlib.util
import inspect
import io
from pathlib import Path
import tempfile
import types
import unittest

import numpy as np
from manim import (BLUE, DOWN, Dot, MovingCameraScene, Rectangle, RIGHT, Text,
                   Scene, SurroundingRectangle, UL, ValueTracker, tempconfig)
from anytomanim import idioms
from anytomanim.cli import GUIDES_DIR, cmd_guides


class RecipeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = tempconfig({"media_dir": self.tmp.name})
        self.config.__enter__()
        self.addCleanup(self.config.__exit__, None, None, None)

    def test_all_fourteen_import_with_one_local_scene(self):
        files = sorted((GUIDES_DIR / "recipes").glob("r*.py"))
        self.assertEqual(len(files), 14)
        for i, path in enumerate(files, 1):
            with self.subTest(recipe=path.name):
                self.assertTrue(path.name.startswith(f"r{i:02}_"))
                lines = path.read_text().splitlines()
                self.assertTrue(30 <= len(lines) <= 80)
                self.assertIn(f"卡 {i}：", lines[0])
                spec = importlib.util.spec_from_file_location(path.stem, path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                scenes = [value for value in vars(module).values() if inspect.isclass(value)
                          and issubclass(value, Scene) and value.__module__ == module.__name__]
                self.assertEqual(len(scenes), 1)
                if i == 6:
                    self.assertTrue(issubclass(scenes[0], MovingCameraScene))

    def test_export_guides_copies_recipes_and_schema_without_bytecode(self):
        with redirect_stdout(io.StringIO()):
            cmd_guides(argparse.Namespace(dir=self.tmp.name))
        out = Path(self.tmp.name)
        self.assertTrue((out/"storyboard-schema.json").exists())
        self.assertTrue((out/"recipes/README.md").exists())
        self.assertEqual(len(list((out/"recipes").glob("r*.py"))), 14)
        self.assertFalse(list(out.rglob("*.pyc")))

    def test_removed_symbols_are_actually_gone(self):
        removed = ("zoom_out emitter_step stream_arrows blackbox SweepSearch sweep_search "
                   "HeatGrid heat_grid person ear car set_gauge wave_packet matrix_2x2 vect_chain "
                   "Retune retune train_on_data").split()
        for name in removed + ['ACCENT2', 'ProbStrip', 'SpringMass', 'TEXT_COLOR', '_safe_arrow', 'angle_arc', 'context_arcs', 'context_flow', 'dial', 'flip_across', 'follow_marker', 'found', 'live_graph', 'live_path', 'mirror_line', 'param_dial', 'param_dot', 'prob_strip', 'probe_strip', 'sighting_lines', 'spring_mass', 'time_trace', 'token_row', 'track_on_line', 'zoom_strips']:
            self.assertFalse(hasattr(idioms, name), name)

    def test_copy_box_keeps_source_and_finishes_at_target(self):
        source = SurroundingRectangle(Dot(RIGHT * -3), color=BLUE, buff=0.18)
        target = Rectangle(width=2, height=1).shift(RIGHT * 3)
        points = source.get_all_points().copy()
        flying, anim = idioms.copy_box_to(source, target, run_time=1.7)
        anim.begin()
        anim.interpolate(0.5)
        self.assertLess(flying.get_x(), target.get_x())
        anim.finish()
        self.assertEqual(anim.run_time, 1.7)
        self.assertIsNot(flying, source)
        np.testing.assert_allclose(source.get_all_points(), points)
        np.testing.assert_allclose(flying.get_center(), target.get_center(), atol=1e-8)
        self.assertAlmostEqual(flying.width, target.width + 0.36)

    def test_park_changes_position_size_and_opacity_without_replacement(self):
        mob = Rectangle(width=3, height=1)
        anim = idioms.park_in_corner(mob, corner=UL, scale=0.5, run_time=1.7).build()
        anim.begin()
        anim.finish()
        self.assertIs(anim.mobject, mob)
        self.assertAlmostEqual(mob.width, 1.5)
        self.assertLess(mob.get_x(), 0)
        self.assertGreater(mob.get_y(), 0)
        self.assertAlmostEqual(float(mob.get_stroke_opacity()), 0.35)
        self.assertAlmostEqual(float(mob.get_fill_opacity()), 0)

    def test_readout_tracks_existing_value_and_stays_next_to_moved_label(self):
        tracker = ValueTracker(0)
        display = idioms.tracker_readout("a", tracker, decimals=2)
        label, number = display
        display.shift(RIGHT * 2)
        for value in (0.75, 12, -100.5, 0):
            tracker.set_value(value)
            display.update(0)
            self.assertAlmostEqual(number.get_value(), value)
            self.assertAlmostEqual(number.get_left()[0] - label.get_right()[0], 0.15)
            self.assertAlmostEqual(number.get_y(), label.get_y())

    def test_camera_widen_preserves_bottom_edge(self):
        frame = Rectangle(width=14, height=8)
        scene = types.SimpleNamespace(camera=types.SimpleNamespace(frame=frame))
        bottom = frame.get_bottom().copy()
        anim = idioms.widen_view(scene, 17.5, about_edge=DOWN, run_time=1.7).build()
        anim.begin()
        anim.finish()
        np.testing.assert_allclose(frame.get_bottom(), bottom)
        self.assertAlmostEqual(frame.height, 10)

    def test_save_restore_is_reversible_camera_zoom(self):
        frame = Rectangle(width=14, height=8)
        frame.save_state()
        original = frame.get_all_points().copy()
        frame.scale(0.5).shift(RIGHT)
        from manim import Restore
        anim = Restore(frame, run_time=1.7)
        anim.begin()
        anim.finish()
        np.testing.assert_allclose(frame.get_all_points(), original)

    def test_spotlight_preserves_fill_proportions_and_restores(self):
        outline = Rectangle(fill_opacity=0, stroke_opacity=0.8)
        filled = Rectangle(fill_opacity=0.6, stroke_opacity=1)
        anim = idioms.spotlight([outline, filled], opacity=0.2)
        anim.begin()
        anim.finish()
        self.assertAlmostEqual(float(outline.get_fill_opacity()), 0)
        self.assertAlmostEqual(float(outline.get_stroke_opacity()), 0.16)
        self.assertAlmostEqual(float(filled.get_fill_opacity()), 0.12)
        restore = idioms.unspotlight([outline, filled])
        restore.begin()
        restore.finish()
        self.assertAlmostEqual(float(outline.get_stroke_opacity()), 0.8)
        self.assertAlmostEqual(float(filled.get_fill_opacity()), 0.6)

    def test_default_dimming_keeps_text_readable(self):
        text = Text("retained result")
        anim = idioms.spotlight([text])
        anim.begin()
        anim.finish()
        self.assertAlmostEqual(float(text[0].get_fill_opacity()), 0.4)
        restore = idioms.unspotlight([text])
        restore.begin()
        restore.finish()
        self.assertAlmostEqual(float(text[0].get_fill_opacity()), 1)
        anim = idioms.park_in_corner(text).build()
        anim.begin()
        anim.finish()
        self.assertGreaterEqual(float(text[0].get_fill_opacity()), 0.35 - 1e-8)

    def test_recipes_have_no_fixed_opacity_below_readability_floor(self):
        for path in (GUIDES_DIR / "recipes").glob("r*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.keyword) and node.arg in (
                        "opacity", "fill_opacity", "stroke_opacity"):
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, (int, float)):
                        self.assertGreaterEqual(node.value.value, 0.35, f"{path.name}:{node.lineno}")
