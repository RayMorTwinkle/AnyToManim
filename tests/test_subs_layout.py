"""Real libass burns at delivery resolutions; no OCR, network or model calls."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from anytomanim import evaluate, subs


class SubtitleLayoutTests(unittest.TestCase):
    def test_width_budget_and_paired_languages(self):
        for text in ("這是一段沒有標點而且很長的中文字幕需要完整顯示" * 4,
                     "W" * 84, "An explanation with a long English translation. " * 6):
            pieces = subs.split_line(text)
            self.assertGreater(len(pieces), 1)
            for piece in pieces:
                self.assertEqual(subs._wrap_width(piece), [piece])
            fitted = subs._fit(pieces, len(pieces) + 3)
            self.assertEqual(len(fitted), len(pieces) + 3)
            self.assertTrue(all(subs._wrap_width(p) == [p] for p in fitted))

    def test_real_long_chinese_bilingual_burn_at_720p_and_1080p(self):
        from PIL import Image

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp:
            root = Path(tmp)
            manifest = root / "beats.json"
            manifest.write_text(json.dumps({"language": "zh", "beats": [{
                "id": "b01", "narration": "test", "audio_seconds": 2,
                "subtitle": {
                    "zh": "這是一段很長的中文字幕，用來確認放大字級之後仍然可以安全換行並且完整顯示在畫面之內。",
                    "en": "We follow each change in the diagram to understand how the explanation progresses."}}]},
                ensure_ascii=False))
            files = subs.generate(manifest, root, gap=0)
            bilingual = next(p for p in files if p.name.endswith("bilingual.srt"))
            cues = subs._parse_ref_srt(bilingual)
            self.assertTrue(all(len(text.splitlines()) == 2 for _, _, text in cues))
            # Pick a cue with the longest visible pair, away from cue boundaries.
            a, b, _ = max(cues, key=lambda cue: len(cue[2]))
            ff = subs._ffmpeg_with_libass()
            for width, height in ((1280, 720), (1920, 1080)):
                with self.subTest(height=height):
                    video, out = root / f"in{height}.mp4", root / f"out{height}.mp4"
                    subprocess.run([ff, "-v", "error", "-f", "lavfi", "-i",
                                    f"color=black:s={width}x{height}:r=10:d=2",
                                    "-c:v", "libx264", "-preset", "ultrafast", str(video)],
                                   check=True, capture_output=True)
                    subs.burn(video, bilingual, out)
                    edge = evaluate._edge_contact(out, evaluate.probe(out))
                    self.assertEqual(edge["left_or_right_share"], 0)
                    frame = root / f"frame{height}.png"
                    subprocess.run([ff, "-v", "error", "-ss", str((a + b) / 2),
                                    "-i", str(out), "-frames:v", "1", str(frame)],
                                   check=True, capture_output=True)
                    with Image.open(frame) as image:
                        ink = image.convert("L").point(lambda p: 255 if p > 80 else 0)
                        bbox = ink.getbbox()
                    self.assertIsNotNone(bbox)
                    left, top, right, bottom = bbox
                    self.assertGreater(left, width * 0.02)
                    self.assertLess(right, width * 0.98)
                    self.assertGreater(top, height * 0.80)
                    self.assertLess(bottom, height)
                    # Both subtitle lines must be visible and larger than the old 25px line.
                    self.assertGreater(bottom - top, height * 0.055)


if __name__ == "__main__":
    unittest.main()
