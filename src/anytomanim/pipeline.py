"""Pipeline stages: digest -> script -> audio -> codegen -> render -> assemble.

All artifacts live under a workdir:
    workdir/brief.md          stage 1
    workdir/beats.json        stage 2  (public IR — narration + visual intent)
    workdir/audio/bXX.wav stage 3  (timing manifest embedded in beats.json)
    workdir/scenes/scene_*.py stage 4  (LLM-generated VoiceoverScene)
    workdir/media/...mp4      stage 5
    workdir/final.mp4         stage 6
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import llm
from .env import render_env

REPO = Path(__file__).resolve().parents[2]
VENV_PY = REPO / ".venv/bin/python"
VENV_MANIM = REPO / ".venv/bin/manim"

NARRATION_STYLE = """3b1b narration rules (from real transcripts):
- Hook first: concrete action, then a question the viewer is now asking.
- Second person, warm, precise; withhold answers to build suspense.
- Connectors mark beats: "Now,", "But here's the thing", "So you might wonder".
- Numbers spelled out ("one in six", not "1/6") — this text is spoken.
- Big claim first, mechanism after. Sentence-per-breath pacing, 1 idea/beat.
- Curious teacher persona; occasional honest aside ("I don't know about you, but…")."""

SCENE_GUIDE = """You write ONE manim scene covering ALL beats. Hard rules:
- Imports exactly:
    import sys
    from pathlib import Path
    REPO = Path("{repo}")
    sys.path.insert(0, str(REPO / "src"))
    from manim import *
    from anytomanim.voiceover import NarratedScene, MiMoService
    from anytomanim.stylelib import *
    from anytomanim.idioms import *
- class {class_name}(NarratedScene):  (add MovingCameraScene as a 2nd base for camera moves)
- construct() begins:
    set_bg(self)
    self.set_speech_service(MiMoService(mode="{mode}"{service_args},
        beats_file="{beats_path}"))
- Per beat EXACTLY this pattern (narration drives timing; never invent durations):
    with self.voiceover(beat="b01") as tr:
        ...build mobjects...
        self.play(<anim>, run_time=tr.duration * FRACTION)
        self.wait(tr.get_remaining_duration())
  - fractions of one beat sum <= 0.75; end every beat with wait(get_remaining_duration())
  - a short FadeOut AFTER the with-block (~0.6s) clears the stage between beats.
- morph(a, b) REPLACES a with b on screen: afterwards refer to b, never a.
- Visual idioms: Write/FadeIn for text, card() chips for facts, MathTex for formulas,
  Indicate/Circumscribe for emphasis, layout via to_edge/next_to/arrange only —
  no raw .move_to(x*RIGHT) guessing, no overlapping text, font_size >= 32 for
  anything the viewer must read.
- BEFORE drawing anything new where an old mobject sits, FadeOut the old one first —
  never Write text on top of still-visible text. Track every mobject you create.
- ManimCE v0.22 API only. No external assets/images. Subcaptions are automatic.
- Class name: {class_name}."""


# ---------------------------------------------------------------- stage 1
def digest(input_text: str, *, language: str = "en") -> Path | str:
    """Input (topic/chapter/paper text/repo notes) -> knowledge brief."""
    msgs = [
        {"role": "system", "content":
         "You distill educational source material into a teaching brief for a "
         "3Blue1Brown-style explainer video. Output markdown with: core question, "
         "key concepts in teaching order, the ONE main insight, required math "
         "notation, natural visual analogies, audience assumptions."},
        {"role": "user", "content":
         f"Language of the brief: {language}\n\nSOURCE:\n{input_text[:30000]}"},
    ]
    return llm.chat(msgs)


# ---------------------------------------------------------------- stage 2
def script(brief: str, *, language: str = "en",
           target_seconds: int | None = None, max_beats: int = 14) -> dict:
    """Brief -> beats.json IR."""
    hint = (f"Target total narration ~{target_seconds}s (soft hint; let content decide)."
            if target_seconds else "Let content complexity decide length.")
    msgs = [
        {"role": "system", "content":
         "You write narration+storyboard JSON for a 3b1b-style explainer.\n"
         + NARRATION_STYLE +
         "\nOutput ONLY JSON: {\"title\": str, \"language\": str, \"beats\": ["
         "{\"id\": \"b01\".., \"narration\": str, \"visual\": str, \"est_seconds\": int}]}\n"
         "Each beat: 1 idea, narration 1-3 sentences (~5-15s speech). "
         "visual = short imperative description of what is on screen during that beat. "
         "8-14 beats typical."},
        {"role": "user", "content":
         f"Language: {language}. {hint} Max {max_beats} beats.\n\nBRIEF:\n{brief}"},
    ]
    return llm.chat_json(msgs)


# ---------------------------------------------------------------- stage 3
def audio(beats: dict, workdir: Path, *, mode: str, voice: str,
          clone_sample: str | None, style: str) -> dict:
    """Synthesize every beat -> wav + manifest durations written back into beats."""
    from .beats import synthesize_beats
    workdir = Path(workdir).resolve()
    beats.setdefault("audio_manifest", {})["style"] = style
    doc, _ = synthesize_beats(beats, workdir / "beats.json", workdir / "audio",
                              mode=mode, voice=voice, clone_sample=clone_sample,
                              style=style)
    # Chunks have their own manifests; absolute paths remain valid in every chunk.
    for b in doc["beats"]:
        p = Path(b["audio_file"])
        b["audio_file"] = str(p if p.is_absolute() else workdir / p)
    return doc


# ---------------------------------------------------------------- stage 4
def gen_scene(beats: dict, workdir: Path, *, mode: str, voice: str,
              clone_sample: str | None, style: str,
              class_name: str = "GenScene") -> Path:
    """LLM -> VoiceoverScene source covering all beats."""
    workdir = Path(workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    beats_path = workdir / "beats.json"
    from .beats import manifest_lock, write_manifest
    with manifest_lock(beats_path):
        write_manifest(beats_path, beats)
    service_args = f", voice={voice!r}" if mode == "preset" else \
        f", clone_sample={str(clone_sample)!r}" if clone_sample else ""
    guide = SCENE_GUIDE.format(repo=REPO, beats_path=beats_path,
                             mode=mode, service_args=service_args,
                             class_name=class_name)
    msgs = [
        {"role": "system", "content": guide},
        {"role": "user", "content":
         "beats.json (narration + visual intent per beat):\n"
         + json.dumps(beats["beats"], indent=2, ensure_ascii=False)
         + "\n\nWrite the complete scene file."},
    ]
    code = _strip_fences(llm.chat(msgs, max_tokens=12288))
    scene_path = workdir / "scenes" / f"{class_name.lower()}.py"
    scene_path.parent.mkdir(parents=True, exist_ok=True)
    scene_path.write_text(code)
    return scene_path


def fix_scene(scene_path: Path, error: str, beats: dict,
              max_ctx: int = 6000) -> Path:
    """Scope-guided-lite repair: send code + traceback back to the LLM."""
    code = scene_path.read_text()
    msgs = [
        {"role": "system", "content":
         "Fix the Manim scene so it runs. Keep the same structure/imports/class "
         "name. Return ONLY the full corrected file. Error:\n" + error[-max_ctx:]},
        {"role": "user", "content": code},
    ]
    scene_path.write_text(_strip_fences(llm.chat(msgs, max_tokens=12288)))
    return scene_path


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        t = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    return t


# ---------------------------------------------------------------- stage 5
def render(scene_path: Path, class_name: str, media_dir: Path,
           quality: str = "qm") -> tuple[Path | None, str]:
    """manim render -> (mp4 path, stderr tail). Paths may be relative to cwd."""
    scene_path, media_dir = Path(scene_path).resolve(), Path(media_dir).resolve()
    if not scene_path.exists():
        return None, f"scene file not found: {scene_path}"
    qualities = {"ql": "480p15", "qm": "720p30", "qh": "1080p60",
                 "qp": "1440p60", "qk": "2160p60"}
    if quality not in qualities:
        return None, f"unsupported quality: {quality}"
    media_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="render-", dir=media_dir) as d:
        fresh = Path(d)
        # Manim defaults: tex_dir={media_dir}/Tex, text_dir={media_dir}/texts.
        # Share asset caches while keeping movie output private to this invocation.
        for name in ("voiceovers", "Tex", "texts"):
            cache = media_dir / name
            cache.mkdir(exist_ok=True)
            (fresh / name).symlink_to(cache, target_is_directory=True)
        proc = subprocess.run(
            [str(VENV_MANIM) if VENV_MANIM.exists() else "manim", f"-{quality}",
             "--disable_caching", "--silent", str(scene_path), class_name,
             "--media_dir", str(fresh)],
            capture_output=True, text=True, cwd=REPO, env=render_env(),
            timeout=1200)
        relative = Path("videos") / scene_path.stem / qualities[quality] / f"{class_name}.mp4"
        made = fresh / relative
        err = (proc.stderr or proc.stdout)[-4000:]
        if proc.returncode == 0 and made.is_file() and made.stat().st_size:
            shutil.copytree(fresh / "videos", media_dir / "videos", dirs_exist_ok=True)
            output = media_dir / relative
            output.with_suffix(".partial.audit.json").unlink(missing_ok=True)
            if not made.with_suffix(".audit.json").exists():
                output.with_suffix(".audit.json").unlink(missing_ok=True)
            return output, err
        # A failed invocation must never change the last good movie's audit.
        audit = made.with_suffix(".partial.audit.json")
        if not audit.exists():
            audit = made.with_suffix(".audit.json")
        if audit.exists():
            from .beats import write_manifest
            dst = (media_dir / relative).with_suffix(".partial.audit.json")
            dst.parent.mkdir(parents=True, exist_ok=True)
            data = json.loads(audit.read_text())
            data["partial"] = True
            write_manifest(dst, data)
            err += f"\nPartial audit: {dst}"
        return None, err + "\nNo movie produced by this render at the requested quality."


# ---------------------------------------------------------------- stage 6
def assemble(scene_mp4s: list[Path], out_path: Path) -> Path:
    """Concat scene mp4s (1+ scenes) -> final.mp4."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if len(scene_mp4s) == 1:
        out_path.write_bytes(Path(scene_mp4s[0]).read_bytes())
        return out_path
    lst = out_path.parent / "concat.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in scene_mp4s))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", str(out_path)], check=True)
    return out_path


# ---------------------------------------------------------------- driver
def run(input_text: str, workdir: Path, *, language: str = "en",
        target_seconds: int | None = None, mode: str = "voiceclone",
        voice: str = "mimo_default", clone_sample: str | None = None,
        style: str = "Calm, curious teacher. Measured pace, warm.",
        quality: str = "qm", fix_attempts: int = 3,
        beats_per_scene: int = 8) -> Path:
    """Long inputs: beats split into chunks -> one scene each -> concat."""
    workdir = Path(workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    brief = digest(input_text, language=language)
    (workdir / "brief.md").write_text(str(brief))
    beats = script(str(brief), language=language, target_seconds=target_seconds)
    beats = audio(beats, workdir, mode=mode, voice=voice,
                  clone_sample=clone_sample, style=style)

    all_beats = beats["beats"]
    chunks = [all_beats[i:i + beats_per_scene]
              for i in range(0, len(all_beats), beats_per_scene)]
    mp4s = []
    for si, chunk in enumerate(chunks):
        sub = dict(beats, beats=chunk)
        name = "GenScene" if len(chunks) == 1 else f"GenScene{si + 1}"
        subdir = workdir if len(chunks) == 1 else workdir / f"scene{si + 1}"
        scene = gen_scene(sub, subdir, mode=mode, voice=voice,
                          clone_sample=clone_sample, style=style,
                          class_name=name)
        mp4, err = render(scene, name, subdir / "media", quality)
        tries = 0
        while mp4 is None and tries < fix_attempts:
            tries += 1
            scene = fix_scene(scene, err, sub)
            mp4, err = render(scene, name, subdir / "media", quality)
        if mp4 is None:
            raise RuntimeError(f"scene {si + 1} failed after {tries} fixes:\n{err}")
        mp4s.append(mp4)
    return assemble(mp4s, workdir / "final.mp4")
