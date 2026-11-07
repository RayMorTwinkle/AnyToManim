"""Render both NarratedScene spellings with prerecorded audio and camera motion."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import wave

from manim import MovingCameraScene, Rectangle, Restore, RIGHT, Text, tempconfig

from anytomanim.evaluate import probe
from anytomanim.voiceover import MiMoService, NarratedScene


class NarratedCameraTests(unittest.TestCase):
    def test_default_and_legacy_camera_render_audio_audit_and_add(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with wave.open(str(root / "beat.wav"), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                wav.writeframes(b"\0\0" * 24000)
            manifest = root / "beats.json"
            manifest.write_text(json.dumps({"beats": [
                dict(id=f"b{i:02}", narration=f"camera beat {i}", audio_file="beat.wav")
                for i in (1, 2)]}))

            def construct(scene):
                scene.set_speech_service(MiMoService(beats_file=manifest,
                                                    cache_dir=str(root / "voiceovers")))
                box = Rectangle(width=3, height=2, fill_opacity=0.35).shift(RIGHT)
                label = Text("retained", font_size=32).move_to(box)
                self.assertIs(scene.add(box, label), scene)
                self.assertEqual(scene.mobjects, [box, label])
                frame = scene.camera.frame
                frame.save_state()
                with scene.voiceover(beat="b01") as tracker:
                    scene.play(frame.animate.scale(0.65).shift(RIGHT), run_time=0.4)
                    scene.wait(tracker.get_remaining_duration())
                scene.zoomed_width = frame.width
                with scene.voiceover(beat="b02") as tracker:
                    scene.play(Restore(frame), run_time=0.4)
                    scene.wait(tracker.get_remaining_duration())
                self.assertIn(box, scene.mobjects)
                self.assertIn(label, scene.mobjects)

            for name, bases in (("DefaultCamera", (NarratedScene,)),
                                ("LegacyCamera", (NarratedScene, MovingCameraScene))):
                with self.subTest(scene=name), tempconfig({
                        "media_dir": str(root / name), "pixel_width": 320,
                        "pixel_height": 180, "frame_rate": 15, "disable_caching": True,
                        "write_to_movie": True, "save_last_frame": False, "dry_run": False,
                        "verbosity": "ERROR", "progress_bar": "none"}), \
                     patch("anytomanim.voiceover.synthesize", side_effect=AssertionError("no live TTS")):
                    scene = type(name, bases, {"construct": construct})()
                    initial_width = scene.camera.frame.width
                    scene.render()
                    self.assertAlmostEqual(scene.zoomed_width, initial_width * 0.65)
                    self.assertAlmostEqual(scene.camera.frame.width, initial_width)
                    movie = Path(scene.renderer.file_writer.movie_file_path)
                    meta = probe(movie)
                    self.assertTrue(meta["has_audio"])
                    # Manim quantizes each wait to frames; allow one frame per beat.
                    self.assertAlmostEqual(meta["duration"], 2, delta=2/15 + 0.01)
                    audit = json.loads(movie.with_suffix(".audit.json").read_text())
                    self.assertEqual([b["beat"] for b in audit["beats"]], ["b01", "b02"])
                    for i, beat in enumerate(audit["beats"]):
                        self.assertEqual(len(beat["on_screen"]), 2)  # No camera control frame.
                        expected_start = audit["beats"][i-1]["end"] if i else 0
                        self.assertEqual(beat["start"], expected_start)
                        self.assertAlmostEqual(beat["end"]-beat["start"], 1, delta=1/15 + 0.01)
                        self.assertAlmostEqual(beat["audio_seconds"], 1, delta=0.05)
                        label = next(m for m in beat["on_screen"] if "retained" in m["label"])
                        self.assertEqual(label["since"], "b01")
                        self.assertTrue(label["visible"])
                        self.assertFalse(any("overrun" in issue for issue in beat["issues"]))
                    # Only the camera moves: rendered pixels must change too.
                    frames = []
                    for time in (0.1, 0.8):
                        frames.append(subprocess.run([
                            "ffmpeg", "-v", "error", "-ss", str(time), "-i", str(movie),
                            "-frames:v", "1", "-vf", "scale=160:90,format=gray",
                            "-f", "rawvideo", "pipe:1"], capture_output=True, check=True).stdout)
                    self.assertEqual(len(frames[0]), 160*90)
                    self.assertGreater(sum(abs(a-b) > 20 for a, b in zip(*frames)), 100)
