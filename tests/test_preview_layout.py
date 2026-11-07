"""Pixel preview regressions: real ffmpeg clips, no OCR, Manim or credentials."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from anytomanim import layout, preview


class LayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.beats = [dict(beat=f"b{i+1:02}", start=4*i, end=4*i+4) for i in range(3)]
        binary = layout.ffmpeg_binary(("overlay", "freezedetect"))
        base = "color=black:s=160x90:r=10:d=12"
        title = ",drawbox=x=30:y=2:w=100:h=6:color=white:t=fill"
        body = ",drawbox=x=8:y=23:w=65:h=12:color=white:t=fill"
        sources = {
            "still": base + title + body + "[bg];color=white:s=12x4:r=10:d=12[sub];"
                     "[bg][sub]overlay=x='8+8*t':y=84:shortest=1",
            "moving": base + title + "[bg];color=white:s=40x30:r=10:d=12[obj];"
                      "[bg][obj]overlay=x='5+8*t':y=30:shortest=1",
            "black": base,
        }
        try:
            cls.results = {}
            for name, source in sources.items():
                path = cls.root / f"{name}.mp4"
                subprocess.run([binary, "-v", "error", "-y", "-f", "lavfi", "-i", source,
                                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
                               capture_output=True, check=True, timeout=30)
                cls.results[name] = layout.analyze_layout(path, cls.beats, 12)
        except BaseException:
            cls.tmp.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_small_box_empty_band_and_subtitles_do_not_hide_freeze(self):
        result = self.results["still"]
        self.assertIn("persistent header", result["warnings"][0])
        self.assertEqual(result["header_beats"], ["b01", "b02", "b03"])
        for beat in result["beats"]:
            self.assertEqual(beat["sample_count"], 7)
            self.assertLess(beat["box_width"], layout.MIN_BOX_WIDTH)
            self.assertLess(beat["box_height"], layout.MIN_BOX_HEIGHT)
            self.assertEqual(beat["empty_bands"], ["lower"])
            self.assertGreater(beat["longest_frozen_seconds"], 3.8)
            self.assertTrue(any("frozen:" in w for w in beat["warnings"]))

    def test_actual_movement_is_not_frozen(self):
        for beat in self.results["moving"]["beats"]:
            self.assertFalse(any("frozen:" in w for w in beat["warnings"]))

    def test_black_top_does_not_count_as_a_persistent_header(self):
        self.assertEqual(self.results["black"]["warnings"], [])
        self.assertEqual(self.results["black"]["header_beats"], [])
        self.assertEqual(self.results["black"]["beats"][0]["box_width"], 0)

    def test_header_similarity_compares_ink_and_rejects_changed_content(self):
        self.assertFalse(layout._same_header(set(), set()))
        self.assertTrue(layout._same_header(set(range(100)), set(range(100))))
        self.assertFalse(layout._same_header(set(range(100)), set(range(100, 200))))

    def test_modal_background_ignores_nonblack_background(self):
        frame = bytearray([30] * (160 * 72))
        frame[160*30+20:160*30+50] = bytes([200] * 30)
        stats = layout._frame_stats(frame)
        self.assertAlmostEqual(stats["width"], 30/160)
        self.assertAlmostEqual(stats["height"], 1/72)
        self.assertFalse(stats["header"])

    def test_frozen_intervals_are_clipped_to_each_beat_and_strictly_over_three(self):
        raw = bytes([0] * (160 * 72))
        with patch.object(layout, "_decode", return_value=({i: raw for i in range(48)}, [(0, 6)])):
            result = layout.analyze_layout(self.root / "unused", self.beats, 12)
        self.assertEqual([b["longest_frozen_seconds"] for b in result["beats"]], [4, 2, 0])
        with patch.object(layout, "_decode", return_value=({i: raw for i in range(48)}, [(1, 4)])):
            result = layout.analyze_layout(self.root / "unused", self.beats, 12)
        self.assertFalse(any("frozen:" in w for b in result["beats"] for w in b["warnings"]))

    def test_preview_with_and_without_audit_reports_warnings_without_new_issues(self):
        for audited in (False, True):
            out = self.root / f"preview-{audited}"
            audit = self.root / "input.audit.json"
            if audited:
                rows = [dict(b, audio_seconds=4, static_fraction=0, on_screen=[],
                             issues=["existing audit issue"] if i == 0 else [])
                        for i, b in enumerate(self.beats)]
                audit.write_text(json.dumps(dict(scene="Input", beats=rows)))
            else:
                audit.unlink(missing_ok=True)
            with patch.object(preview, "_grab", return_value=False), \
                 patch.object(preview, "_sheet", return_value=out / "sheet.png"):
                _, report, count = preview.preview(self.root / "still.mp4", out, audit, every=4)
            self.assertEqual(count, int(audited))
            self.assertIn("warning all: persistent header", report.read_text())
            self.assertIn("warnings only", report.read_text())
            self.assertTrue((out / "layout.json").is_file())

    def test_timing_prefers_audit_then_manifest_then_equal_segments(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "video.mp4"
            windows, source = preview._layout_beats(video, {"beats": self.beats}, 12, 3)
            self.assertEqual(windows, self.beats)
            self.assertIn("audit", source)
            windows, source = preview._layout_beats(video, None, 12, 4)
            self.assertEqual(len(windows), 3)
            self.assertIn("equal time segments", source)
            manifest = video.with_name("beats.json")
            manifest.write_text(json.dumps({"beats": [dict(id="x", audio_seconds=2),
                                                       dict(id="y", audio_seconds=1)]}))
            windows, source = preview._layout_beats(video, None, 12, 4)
            self.assertEqual(windows[0], dict(beat="x", start=0, end=8))
            self.assertIn("duration-weighted", source)
            manifest.write_text(json.dumps({"beats": [dict(id="x"), dict(id="y")]}))
            windows, source = preview._layout_beats(video, None, 12, 4)
            self.assertEqual(windows[-1], dict(beat="y", start=6, end=12))

    def test_unavailable_pixel_review_remains_a_warning(self):
        out = self.root / "unavailable"
        with patch.object(preview, "_grab", return_value=False), \
             patch.object(preview, "_sheet", return_value=out / "sheet.png"), \
             patch.object(layout, "analyze_layout", side_effect=RuntimeError("decoder unavailable")):
            _, report, count = preview.preview(self.root / "still.mp4", out)
        self.assertEqual(count, 0)
        self.assertIn("warning all: pixel layout review unavailable", report.read_text())
