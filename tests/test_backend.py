"""Backend regressions: local stubs only, no credentials or network."""
import argparse
from contextlib import ExitStack, contextmanager
import io
from contextlib import redirect_stdout, redirect_stderr
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
import wave
from unittest.mock import patch

from anytomanim import pipeline


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.addCleanup(patch.stopall)
        patch("anytomanim.tts.load_key", side_effect=AssertionError("no API keys in tests")).start()
        from manim import tempconfig
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(tempconfig({"media_dir": str(self.root / "media")}))

    def doc(self, n=2):
        return {"title": "test", "language": "en", "beats": [
            {"id": f"b{i+1:02d}", "narration": f"text {i}", "visual": "dot"}
            for i in range(n)]}

    def test_03_chunk_directory(self):
        with patch.object(pipeline.llm, "chat", return_value="class GenScene: pass"):
            scene = pipeline.gen_scene(self.doc(), self.root / "scene1",
                                       mode="preset", voice="x", clone_sample=None, style="")
        self.assertTrue(scene.exists())
        from anytomanim import tts, voiceover
        names = []
        def render_chunk(scene, name, media, quality):
            names.append(name)
            manifest = scene.parent.parent / "beats.json"
            doc = json.loads(manifest.read_text())
            svc = self.service(beats_file=manifest)
            for b in doc["beats"]:
                self.assertTrue(Path(b["audio_file"]).is_absolute())
                result = svc.generate_from_text(b["narration"], beat_id=b["id"])
                self.assertTrue((Path(svc.cache_dir) / result["original_audio"]).exists())
            return self.root / (name + ".mp4"), ""
        with patch.object(pipeline, "digest", return_value="brief"), \
             patch.object(pipeline, "script", return_value=self.doc(9)), \
             patch.object(tts, "synthesize", side_effect=self.fake_tts), \
             patch.object(voiceover, "synthesize", side_effect=AssertionError("no live TTS")), \
             patch.object(pipeline.llm, "chat", return_value="pass"), \
             patch.object(pipeline, "render", side_effect=render_chunk), \
             patch.object(pipeline, "assemble", return_value=self.root / "final.mp4"):
            pipeline.run("nine beats", self.root / "nine")
        self.assertEqual(names, ["GenScene1", "GenScene2"])

    def test_05_relative_workdir(self):
        relative = self.root.relative_to(Path.cwd()) / "work"
        def fake_audio(doc, workdir, **kw):
            self.assertTrue(workdir.is_absolute())
            for b in doc["beats"]:
                b["audio_file"] = str(workdir / "audio" / (b["id"] + ".wav"))
            return doc
        with patch.object(pipeline, "digest", return_value="brief"), \
             patch.object(pipeline, "script", return_value=self.doc()), \
             patch.object(pipeline, "audio", side_effect=fake_audio), \
             patch.object(pipeline.llm, "chat", return_value="pass"), \
             patch.object(pipeline, "render", return_value=(self.root / "a.mp4", "")), \
             patch.object(pipeline, "assemble", return_value=self.root / "final.mp4"):
            pipeline.run("topic", relative)
        doc = json.loads((relative / "beats.json").read_text())
        self.assertTrue(Path(doc["beats"][0]["audio_file"]).is_absolute())

    def test_11_render_fresh_quality(self):
        scene = self.root / "Scene.py"
        scene.write_text("pass")
        media = self.root / "media"
        stale = media / "videos/Scene/1080p60/Scene.mp4"
        stale.parent.mkdir(parents=True)
        stale.write_bytes(b"old")
        with patch.object(pipeline.subprocess, "run", return_value=types.SimpleNamespace(
                returncode=0, stderr="", stdout="")):
            result, _ = pipeline.render(scene, "Scene", media, "ql")
        self.assertIsNone(result)
        def produce(cmd, **kw):
            out = Path(cmd[cmd.index("--media_dir") + 1]) / "videos/Scene/480p15/Scene.mp4"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"new")
            return types.SimpleNamespace(returncode=0, stderr="", stdout="")
        with patch.object(pipeline.subprocess, "run", side_effect=produce):
            result, _ = pipeline.render(scene, "Scene", media, "ql")
        self.assertEqual(result.read_bytes(), b"new")
        self.assertEqual(result.parent.name, "480p15")

    def wav(self, path, data=b"\0\0" * 2400):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(data)
        return path

    def manifest(self, doc=None):
        path = self.root / "beats.json"
        path.write_text(json.dumps(doc or self.doc()))
        return path

    def batch(self, path, **kw):
        from anytomanim.cli import _tts_beats
        args = dict(beats=str(path), voice="milo", mode=None, clone=None,
                    style="style", audio_dir=None, force=False, jobs=2)
        args.update(kw)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return _tts_beats(argparse.Namespace(**args))

    def fake_tts(self, text, out, **kw):
        return self.wav(out)

    def test_12_animation_timing_and_return(self):
        from anytomanim import idioms
        from manim import Dot, Rectangle, RIGHT
        import numpy as np
        scene = types.SimpleNamespace(camera=types.SimpleNamespace(frame=Rectangle()))
        for helper, args in [(idioms.zoom_in, (scene, RIGHT)),
                             (idioms.pan_to, (scene, RIGHT)),
                             (idioms.widen_view, (scene, 12)), (idioms.drift_cam, (scene,))]:
            anim = helper(*args, run_time=2.75).build()
            self.assertEqual(anim.run_time, 2.75, helper.__name__)
        for helper in [idioms.breathe, idioms.bob]:
            dot = Dot(RIGHT)
            original = dot.get_all_points().copy()
            anim = helper(dot, run_time=2.75).build()
            self.assertEqual(anim.run_time, 2.75)
            anim.begin()
            anim.interpolate(0.5)
            self.assertFalse(np.allclose(dot.get_all_points(), original))
            anim.finish()
            np.testing.assert_allclose(dot.get_all_points(), original, atol=1e-8)

    def test_13_label_directions(self):
        from anytomanim.idioms import label_arrow
        from manim import Dot, UL, UR, DOWN, LEFT
        for direction in [UL, DOWN, UR, LEFT]:
            self.assertEqual(len(label_arrow("label", Dot(), direction=direction)), 2)

    def test_06_batch_fingerprint(self):
        from anytomanim import tts
        path = self.manifest()
        clone = self.root / "clone.wav"
        self.wav(clone)
        with patch.object(tts, "synthesize", side_effect=self.fake_tts) as synth:
            self.batch(path)
            self.assertEqual(synth.call_count, 2)
            self.batch(path)
            self.assertEqual(synth.call_count, 2)
            self.batch(path, style="new style")
            self.assertEqual(synth.call_count, 4)
            self.batch(path, mode="voiceclone", clone=str(clone))
            self.assertEqual(synth.call_count, 6)
            self.wav(clone, b"\1\0" * 2400)
            self.batch(path, mode="voiceclone", clone=str(clone))
            self.assertEqual(synth.call_count, 8)
            other = self.root / "other.wav"
            self.wav(other, b"\2\0" * 2400)
            self.batch(path, mode="voiceclone", clone=str(other))
            self.assertEqual(synth.call_count, 10)
            with patch.dict(os.environ, {"ANYTOMANIM_TTS": "draft"}):
                self.batch(path, mode="voiceclone", clone=str(other))
            self.assertEqual(synth.call_count, 12)

    def test_07_pipeline_resume_inputs(self):
        from anytomanim import tts
        def audio(doc, **kw):
            args = dict(mode="preset", voice="x", clone_sample=None, style="style")
            args.update(kw)
            return pipeline.audio(doc, self.root, **args)
        with patch.object(tts, "synthesize", side_effect=self.fake_tts) as synth:
            audio(self.doc())
            audio(self.doc())
            self.assertEqual(synth.call_count, 2)
            changed = self.doc()
            changed["beats"][0]["narration"] = "a new topic"
            audio(changed)
            self.assertEqual(synth.call_count, 3)
            audio(changed, voice="y")
            self.assertEqual(synth.call_count, 5)
            audio(changed, voice="y", style="whisper")
            self.assertEqual(synth.call_count, 7)

    def service(self, **kw):
        from anytomanim.voiceover import MiMoService
        return MiMoService(cache_dir=str(self.root / "cache"), **kw)

    def test_08_live_cache_identity(self):
        from anytomanim import voiceover
        clone = self.wav(self.root / "clone.wav")
        svc = self.service(mode="voiceclone", clone_sample=clone)
        with patch.object(voiceover, "synthesize", side_effect=self.fake_tts), \
             patch.object(svc, "get_cached_result", return_value=None):
            with patch.dict(os.environ, {"ANYTOMANIM_TTS": "draft"}):
                draft = svc.generate_from_text("hello")["input_data"]
            with patch.dict(os.environ, {"ANYTOMANIM_TTS": ""}):
                prod = svc.generate_from_text("hello")["input_data"]
                self.wav(clone, b"\2\0" * 2400)
                replaced = svc.generate_from_text("hello")["input_data"]
        self.assertNotEqual(draft, prod)
        self.assertNotEqual(prod, replaced)

    def test_09_atomic_wav(self):
        from anytomanim import tts
        out = self.wav(self.root / "out.wav")
        original = out.read_bytes()
        def interrupted(text, path):
            path.write_bytes(b"partial")
            raise RuntimeError("interrupted")
        with patch.dict(os.environ, {"ANYTOMANIM_TTS": "draft"}), \
             patch.object(tts, "_synthesize_draft", side_effect=interrupted):
            with self.assertRaises(RuntimeError):
                tts.synthesize("hello", out)
        self.assertEqual(out.read_bytes(), original)
        def truncated(text, path):
            self.wav(path)
            path.write_bytes(path.read_bytes()[:-10])
        with patch.dict(os.environ, {"ANYTOMANIM_TTS": "draft"}), \
             patch.object(tts, "_synthesize_draft", side_effect=truncated):
            with self.assertRaises((ValueError, wave.Error)):
                tts.synthesize("hello", out)
        self.assertEqual(out.read_bytes(), original)

    def test_10_partial_batch_progress(self):
        from anytomanim import tts
        path = self.manifest()
        def work(text, out, **kw):
            if text == "text 1":
                raise RuntimeError("stub failure")
            return self.fake_tts(text, out, **kw)
        with patch.object(tts, "synthesize", side_effect=work) as synth:
            with self.assertRaisesRegex(SystemExit, "b02"):
                self.batch(path)
            saved = json.loads(path.read_text())["beats"]
            self.assertEqual(saved[0]["audio_narration"], "text 0")
            self.assertNotIn("audio_narration", saved[1])
            synth.reset_mock()
            with self.assertRaisesRegex(SystemExit, "b02"):
                self.batch(path)
            self.assertEqual(synth.call_count, 1)

    def test_01_atomic_manifest(self):
        from anytomanim import tts
        path = self.manifest()
        original = path.read_bytes()
        real_open = io.open
        class BrokenWriter:
            def __init__(self, file):
                self.file = file
            def __getattr__(self, name):
                return getattr(self.file, name)
            def __enter__(self):
                self.file.__enter__()
                return self
            def __exit__(self, *args):
                return self.file.__exit__(*args)
            def write(self, text):
                self.file.write(text[:10])
                self.file.flush()
                raise OSError("disk failure during write")
        def failing_open(file, mode="r", *args, **kw):
            opened = real_open(file, mode, *args, **kw)
            return BrokenWriter(opened) if "w" in mode else opened
        with patch.object(tts, "synthesize", side_effect=self.fake_tts), \
             patch("io.open", side_effect=failing_open):
            with self.assertRaises(OSError):
                self.batch(path)
        self.assertEqual(path.read_bytes(), original)

    def test_01_concurrent_manifest_resume(self):
        path = self.manifest()
        worker = self.root / "worker.py"
        worker.write_text("""
import argparse
from pathlib import Path
import sys
import time
import wave
from unittest.mock import patch
from anytomanim import cli, tts
root = Path(sys.argv[1])
def synth(text, out, **kw):
    with (root / "calls").open("a") as f:
        f.write(text + "\\n")
    time.sleep(0.1)
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\\0\\0" * 2400)
args = argparse.Namespace(beats=str(root / "beats.json"), voice="milo", mode=None,
    clone=None, style="style", audio_dir=None, force=False, jobs=2)
with patch.object(tts, "synthesize", side_effect=synth), patch.object(
        tts, "load_key", side_effect=AssertionError("no network")):
    cli._tts_beats(args)
""")
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(
            str(Path(p).resolve()) for p in os.environ["PYTHONPATH"].split(os.pathsep)))
        workers = [subprocess.Popen([str(pipeline.sys.executable), str(worker), str(self.root)],
                                    env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True) for _ in range(2)]
        try:
            for proc in workers:
                out, err = proc.communicate(timeout=30)
                self.assertEqual(proc.returncode, 0, err)
        finally:
            for proc in workers:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
        self.assertEqual(sorted((self.root / "calls").read_text().splitlines()),
                         ["text 0", "text 1"])
        self.assertEqual(len(json.loads(path.read_text())["beats"]), 2)

    def test_02_reject_ids_before_synthesis(self):
        from anytomanim import tts
        for ids in [["../outside"], [str(self.root / "outside")], ["b01", "b01"], ["b01\n"]]:
            doc = self.doc(len(ids))
            for b, bid in zip(doc["beats"], ids):
                b["id"] = bid
            path = self.manifest(doc)
            with patch.object(tts, "synthesize", side_effect=self.fake_tts) as synth:
                with self.assertRaisesRegex(SystemExit, "(invalid|duplicate) beat id"):
                    self.batch(path)
                synth.assert_not_called()
        path = self.manifest({**self.doc(1), "beats": [
            {"id": "b00123", "narration": "ok", "visual": "dot"}]})
        with patch.object(tts, "synthesize", side_effect=self.fake_tts):
            self.batch(path)

    def bare_scene(self, svc=None):
        from anytomanim.voiceover import NarratedScene
        scene = object.__new__(NarratedScene)
        scene.renderer = types.SimpleNamespace(
            time=0, camera=types.SimpleNamespace(),
            file_writer=types.SimpleNamespace(movie_file_path=str(self.root / "Scene.mp4")))
        scene.mobjects = []
        scene._audit, scene._first_seen = [], {}
        scene._cur_beat, scene._static = None, 0
        scene.speech_service = svc
        return scene

    def test_04_explicit_beat_and_ambiguous_text(self):
        from anytomanim.voiceover import VoiceoverScene
        doc = self.doc()
        for i, b in enumerate(doc["beats"]):
            b["narration"] = "A B" if i == 0 else "AB"
            b["audio_file"] = str(self.wav(self.root / (b["id"] + ".wav"),
                                                bytes([i, 0]) * 2400))
        svc = self.service(beats_file=self.manifest(doc))
        scene = self.bare_scene(svc)
        @contextmanager
        def parent(scene, text=None, **kw):
            result = svc.generate_from_text(text, **kw)
            yield types.SimpleNamespace(duration=0.1, audio=result["original_audio"])
        with patch.object(VoiceoverScene, "voiceover", parent):
            with scene.voiceover(beat="b01") as tr:
                self.assertEqual((Path(svc.cache_dir) / tr.audio).read_bytes(),
                                 (self.root / "b01.wav").read_bytes())
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            svc.generate_from_text("AB")

    def test_15_audit_chronology(self):
        from anytomanim import subs
        doc = self.doc()
        path = self.manifest(doc)
        audit = self.root / "Scene.audit.json"
        audit.write_text(json.dumps({"beats": [
            {"beat": "b02", "start": 0, "audio_seconds": 5},
            {"beat": "b01", "start": 5, "audio_seconds": 5}]}))
        [out] = subs.generate(path, self.root, audit=audit)
        cues = subs._parse_ref_srt(out)
        self.assertTrue(all(a < b for a, b, text in cues))
        self.assertEqual([c[2] for c in cues], ["text 1", "text 0"])
        self.assertEqual([c[0] for c in cues], sorted(c[0] for c in cues))

    def test_16_voice_design_directive(self):
        from anytomanim import voiceover
        svc = self.service(design="A low whisper", style="slow")
        with patch.object(voiceover, "synthesize", side_effect=self.fake_tts) as synth, \
             patch.object(svc, "get_cached_result", return_value=None):
            first = svc.generate_from_text("hello")["input_data"]
            self.assertIn("A low whisper", synth.call_args.kwargs["style"])
            self.assertIn("slow", synth.call_args.kwargs["style"])
            svc.design = "A bright soprano"
            second = svc.generate_from_text("hello")["input_data"]
        self.assertNotEqual(first, second)

    def test_19_partial_audit(self):
        from anytomanim.voiceover import VoiceoverScene
        scene = self.bare_scene()
        @contextmanager
        def parent(scene, **kw):
            yield types.SimpleNamespace(duration=1)
        with patch.object(VoiceoverScene, "voiceover", parent):
            with scene.voiceover(text="complete"):
                scene.renderer.time = 1
            with self.assertRaisesRegex(RuntimeError, "broken"):
                with scene.voiceover(text="failure"):
                    scene.renderer.time = 1.5
                    raise RuntimeError("broken")
        audit = json.loads((self.root / "Scene.partial.audit.json").read_text())
        self.assertTrue(audit["partial"])
        self.assertEqual(len(audit["beats"]), 2)
        self.assertEqual(audit["beats"][-1]["status"], "failed")
        self.assertIn("broken", audit["error"])

    def test_19_failure_between_beats(self):
        from anytomanim.voiceover import VoiceoverScene
        scene = self.bare_scene()
        scene._record("b01", 0, 1, 1)
        with patch.object(VoiceoverScene, "render", side_effect=RuntimeError("after beat")):
            with self.assertRaisesRegex(RuntimeError, "after beat"):
                scene.render()
        audit = json.loads((self.root / "Scene.partial.audit.json").read_text())
        self.assertTrue(audit["partial"])
        self.assertEqual(audit["beats"][0]["beat"], "b01")

    def test_14_burn_special_paths(self):
        from anytomanim import subs
        ff = subs._ffmpeg_with_libass()
        video = self.root / "in.mp4"
        subprocess.run([ff, "-y", "-v", "error", "-f", "lavfi", "-i",
                        "color=c=black:s=160x90:d=0.4", "-c:v", "libx264", str(video)], check=True)
        folder = self.root / "O'Brien:,[folder]"
        folder.mkdir()
        srt = folder / "O'Brien:,[caption].srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:00,400\nHello\n")
        out = subs.burn(video, srt, folder / "out.mp4", fontname="Arial")
        self.assertGreater(out.stat().st_size, 0)

    def test_17_preview_invalid_interval(self):
        from anytomanim import preview
        for interval in [0, -1, float("inf"), float("nan")]:
            # The duration stub prevents an old-code infinite loop, while still
            # proving invalid input was rejected before probing or sampling.
            with patch.object(preview, "audio_duration", return_value=0), \
                 patch.object(preview, "_sheet", return_value=self.root / "sheet.png"):
                with self.assertRaisesRegex(ValueError, "finite.*positive"):
                    preview.preview(self.root / "in.mp4", every=interval)

    def test_bilingual_cues_stay_split_when_languages_differ(self):
        from anytomanim import subs
        zh = "，".join(["這是一段很長的中文旁白內容"] * 5) + "。"
        path = self.root / "beats.json"
        path.write_text(json.dumps({"language": "zh", "beats": [{
            "id": "b01", "narration": zh, "audio_seconds": 10,
            "subtitle": {"zh": zh, "en": "A short English line."}}]}))
        made = subs.generate(path, self.root / "subs")
        bilingual = next(m for m in made if m.stem.endswith(".bilingual"))
        lines = [ln for ln in bilingual.read_text().splitlines()
                 if ln and "-->" not in ln and not ln.isdigit()]
        self.assertLessEqual(max(map(len, lines)), 30)
        self.assertEqual("".join(ln for ln in lines if not ln.isascii()), zh)

    def test_18_split_oversized_segments(self):
        from anytomanim.subs import split_line
        cjk = "甲" * 45
        pieces = split_line(cjk)
        self.assertTrue(all(len(p) <= 22 for p in pieces))
        self.assertEqual("".join(pieces), cjk)
        latin = " ".join(["several", "words"] * 20)
        pieces = split_line(latin)
        self.assertTrue(all(len(p) <= 84 for p in pieces))
        self.assertEqual(" ".join(pieces), latin)
        self.assertTrue(all(len(p) <= 84 for p in split_line("x" * 200)))

    def test_R1_existing_file_permissions(self):
        from anytomanim import beats, tts
        import stat
        manifest = self.manifest()
        wav = self.wav(self.root / "mode.wav")
        scene = self.bare_scene()
        scene._record("b01", 0, 1, 1)
        audit = self.root / "Scene.audit.json"
        audit.write_text("{}")
        for mode in (0o644, 0o640):
            for path in (manifest, wav, audit):
                path.chmod(mode)
            beats.write_manifest(manifest, self.doc())
            with patch.object(tts, "_synthesize", side_effect=self.fake_tts):
                tts.synthesize("hello", wav)
            scene._flush_audit()
            for path in (manifest, wav, audit):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), mode, path.name)

    def test_R1_new_file_umask(self):
        # Set umask only in a child, never in the threaded test process.
        code = """
import json
import os
from pathlib import Path
import stat
import sys
from unittest.mock import patch
import wave
from anytomanim import beats, tts
os.umask(0o027)
root = Path(sys.argv[1])
beats.write_manifest(root / 'new.json', {})
def synth(text, out, **kw):
    with wave.open(str(out), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b'\\0\\0' * 2400)
with patch.object(tts, '_synthesize', side_effect=synth):
    tts.synthesize('hello', root / 'new.wav')
print(json.dumps([stat.S_IMODE((root / name).stat().st_mode)
                  for name in ('new.json', 'new.wav')]))
"""
        result = subprocess.run([pipeline.sys.executable, "-c", code, str(self.root)],
                                capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), [0o640, 0o640])

    def test_R2_manifest_lock_ignored(self):
        self.assertIn("*.json.lock", (pipeline.REPO / ".gitignore").read_text().splitlines())

    def test_R3_persistent_manim_caches(self):
        scene = self.root / "Cached.py"
        scene.write_text("pass")
        builds = {"Tex": 0, "texts": 0, "voiceovers": 0}
        def produce(cmd, **kw):
            fresh = Path(cmd[cmd.index("--media_dir") + 1])
            for name in builds:
                cache = fresh / name
                cache.mkdir(exist_ok=True)
                artifact = cache / "cached.svg"
                if not artifact.exists():
                    builds[name] += 1
                    artifact.write_text("cached")
            out = fresh / "videos/Cached/480p15/Cached.mp4"
            out.parent.mkdir(parents=True)
            out.write_bytes(b"movie")
            return types.SimpleNamespace(returncode=0, stderr="", stdout="")
        with patch.object(pipeline.subprocess, "run", side_effect=produce):
            for _ in range(2):
                made, err = pipeline.render(scene, "Cached", self.root / "media", "ql")
                self.assertIsNotNone(made, err)
        self.assertEqual(builds, {"Tex": 1, "texts": 1, "voiceovers": 1})

    def test_R4_render_audit_lifecycle(self):
        scene = self.root / "P.py"
        scene.write_text("pass")
        media = self.root / "media"
        out = media / "videos/P/480p15/P.mp4"
        out.parent.mkdir(parents=True)
        out.write_bytes(b"good movie")
        good = out.with_suffix(".audit.json")
        good.write_text('{"scene": "P", "beats": [], "version": "good"}')
        original = good.read_bytes()
        partial = out.with_suffix(".partial.audit.json")
        def fail(cmd, **kw):
            fresh = Path(cmd[cmd.index("--media_dir") + 1]) / "videos/P/480p15"
            fresh.mkdir(parents=True)
            (fresh / "P.partial.audit.json").write_text(
                '{"scene": "P", "beats": [], "partial": true}')
            return types.SimpleNamespace(returncode=1, stderr="broken", stdout="")
        with patch.object(pipeline.subprocess, "run", side_effect=fail):
            made, err = pipeline.render(scene, "P", media, "ql")
        self.assertIsNone(made)
        self.assertEqual(good.read_bytes(), original)
        self.assertTrue(partial.exists())
        self.assertIn(str(partial), err)
        self.assertEqual(out.read_bytes(), b"good movie")
        def succeed(cmd, **kw):
            fresh = Path(cmd[cmd.index("--media_dir") + 1]) / "videos/P/480p15"
            fresh.mkdir(parents=True)
            (fresh / "P.mp4").write_bytes(b"new movie")
            (fresh / "P.audit.json").write_text('{"scene": "P", "beats": []}')
            return types.SimpleNamespace(returncode=0, stderr="", stdout="")
        with patch.object(pipeline.subprocess, "run", side_effect=succeed):
            made, err = pipeline.render(scene, "P", media, "ql")
        self.assertEqual(made.read_bytes(), b"new movie")
        self.assertFalse(partial.exists())
        self.assertNotEqual(good.read_bytes(), original)

    def test_R4_direct_scene_audit_lifecycle(self):
        scene = self.bare_scene()
        scene._record("b01", 0, 1, 1)
        good = self.root / "Scene.audit.json"
        scene._flush_audit()
        original = good.read_bytes()
        scene._flush_audit(partial=True, error="failure")
        partial = self.root / "Scene.partial.audit.json"
        self.assertEqual(good.read_bytes(), original)
        self.assertTrue(json.loads(partial.read_text())["partial"])
        scene._flush_audit()
        self.assertFalse(partial.exists())

    def test_R5_cli_input_errors(self):
        path = self.manifest()
        code = """
from unittest.mock import patch
from anytomanim import cli, tts
with patch.object(tts, 'load_key', side_effect=AssertionError('no keys')):
    cli.main()
"""
        commands = [(["tts", "--beats", str(path), "--voice", "milo",
                      "--mode", "voiceclone", "--clone", str(self.root / "missing.mp3")],
                     "voice-clone sample missing"),
                    (["preview", str(self.root / "missing.mp4"), "--every", "0"],
                     "finite and positive")]
        for args, message in commands:
            result = subprocess.run([pipeline.sys.executable, "-c", code] + args,
                                    env=dict(os.environ, ANYTOMANIM_TTS=""),
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)
            self.assertIn(message, result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_R6_arrow_vertical_direction(self):
        from anytomanim import idioms
        from manim import Dot, UP, UL, UR, DOWN, DL, DR
        import numpy as np
        for direction in (UP, UL, UR, DOWN, DL, DR):
            with patch.object(idioms, "curved_pointer", wraps=idioms.curved_pointer) as pointer:
                label, arrow = idioms.label_arrow("label", Dot(), direction=direction)
            expected = label.get_bottom() if direction[1] > 0 else label.get_top()
            np.testing.assert_allclose(pointer.call_args.args[0], expected)

    def test_R7_batch_progress(self):
        from anytomanim import cli, tts
        args = argparse.Namespace(beats=str(self.manifest()), voice="milo", mode=None,
                                  clone=None, style="", audio_dir=None, force=False, jobs=2)
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(tts, "synthesize", side_effect=self.fake_tts), \
             redirect_stdout(stdout), redirect_stderr(stderr):
            cli._tts_beats(args)
        self.assertEqual(json.loads(stdout.getvalue())["synthesized"], 2)
        self.assertEqual(sorted(stderr.getvalue().splitlines()),
                         ["synthesized b01", "synthesized b02"])

    def test_R8_python310_and_guide_cleanup(self):
        import ast
        source = Path(__file__).read_text()
        tree = ast.parse(source, feature_version=(3, 10))
        self.assertNotIn("enterContext", [n.attr for n in ast.walk(tree)
                                          if isinstance(n, ast.Attribute)])
        cli = (pipeline.REPO / "src/anytomanim/cli.py").read_text()
        self.assertNotIn("\n\n\n\n# ------------------------------------------------------------------ measure", cli)
        guide = (pipeline.REPO / "src/anytomanim/guides/WORKFLOW.md").read_text()
        fenced = False
        for line in guide.splitlines():
            if line.startswith("```"):
                fenced = not fenced
            elif not fenced:
                self.assertLessEqual(len(line), 79, line)
        self.assertIn("automatically", guide)
        self.assertIn("`--force`", guide)


if __name__ == "__main__":
    unittest.main()
