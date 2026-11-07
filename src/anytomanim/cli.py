"""anytomanim CLI — atomic toolchain for agent-driven video generation.

    anytomanim doctor                     # dependency check + fix hints
    anytomanim tts --beats beats.json     # synthesize every beat, write durations back
    anytomanim tts "text" -o beat.wav     # synthesize one line (voice presets)
    anytomanim measure beat.wav           # print real duration (seconds)
    anytomanim render scene.py MyScene    # manim render → mp4 path
    anytomanim preview Scene.mp4          # per-beat contact sheet + audit report
    anytomanim assemble a.mp4 b.mp4 -o out.mp4
    anytomanim export-guides [dir]        # export prompt specs for a host agent
    anytomanim run "<topic>"              # embedded-LLM reference driver (eval)

Fast commands (tts/measure/subtitles/bgm) never import manim.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VENV_PY = REPO / ".venv/bin/python"
VENV_MANIM = REPO / ".venv/bin/manim"
GUIDES_DIR = Path(__file__).resolve().parent / "guides"


def _py() -> str:
    """Python running the toolchain (repo venv if present, else sys.executable)."""
    return str(VENV_PY) if VENV_PY.exists() else sys.executable


def _manim() -> str:
    return str(VENV_MANIM) if VENV_MANIM.exists() else "manim"


# ------------------------------------------------------------------ doctor
def cmd_doctor(a):
    from anytomanim import voices
    from anytomanim.env import read_dotenv, tex_bin
    from anytomanim.tts import draft_mode
    checks = []

    def ok(name, good, detail, fix="", warn_only=False):
        checks.append((name, good, detail, fix, warn_only))

    manim = _manim()
    ok("manim", Path(manim).exists() or shutil.which("manim") is not None,
       manim, "pip install -e . (or use repo .venv)")
    ok("python", True, _py())
    ok("ffmpeg", shutil.which("ffmpeg") is not None, shutil.which("ffmpeg") or "missing",
       "brew install ffmpeg")
    ok("ffprobe", shutil.which("ffprobe") is not None, shutil.which("ffprobe") or "missing",
       "brew install ffmpeg")
    tb = tex_bin()
    ok("latex (dvisvgm)", tb is not None, tb or "missing",
       "brew install --cask basictex && sudo tlmgr install dvisvgm  "
       "(no sudo: TinyTeX — curl -sL https://yihui.org/tinytex/install-bin-unix.sh "
       "| sh -s - --no-path, then tlmgr install dvisvgm standalone preview "
       "doublestroke relsize ragged2e physics ctex)")
    key = read_dotenv("MIMO_API_KEY")
    ok("MIMO_API_KEY", bool(key) or draft_mode(),
       "set" if key else ("draft mode (ANYTOMANIM_TTS=draft)" if draft_mode() else "missing"),
       "put MIMO_API_KEY=... in .env, or ANYTOMANIM_TTS=draft to iterate with a local voice")
    try:
        import imageio_ffmpeg  # noqa: F401
        ok("imageio-ffmpeg", True, "ok (libass for --burn)")
    except ImportError:
        ok("imageio-ffmpeg", False, "missing", "pip install imageio-ffmpeg (needed by subtitles --burn)",
           warn_only=True)
    try:
        reg = voices.load_registry()
        ok("voices", True, f"{len(reg)} presets; default en={voices.default_for('en')}, "
                           f"zh={voices.default_for('zh')}")
        for name in voices.missing_samples():
            ok(f"voice '{name}'", False, f"clone sample missing: {reg[name]['clone_sample']}",
               "drop a clean <=10MB clip there, or use a preset voice", warn_only=True)
    except Exception as e:  # noqa: BLE001
        ok("voices", False, str(e))
    bad = [c for c in checks if not c[1] and not c[4]]
    for name, good, detail, fix, warn_only in checks:
        mark = "ok  " if good else ("warn" if warn_only else "MISS")
        line = f"[{mark}] {name:16} {detail}"
        if not good and fix:
            line += f"  -> {fix}"
        print(line)
    sys.exit(1 if bad else 0)


# ------------------------------------------------------------------ tts
def _voice_args(name, mode, clone, style, language="en"):
    """CLI flags + preset registry -> (mode, voice, clone_sample, style)."""
    from anytomanim import voices
    name = name or voices.default_for(language)
    reg = voices.load_registry()
    preset = voices.resolve(name) if name in reg else {
        "mode": mode or "preset", "voice": name, "clone_sample": clone, "style": ""}
    mode = mode or preset["mode"]
    clone = clone or preset.get("clone_sample")
    return (mode, preset["voice"], clone if mode == "voiceclone" else None,
            style if style is not None else preset.get("style") or "")


def cmd_tts(a):
    from anytomanim.tts import audio_duration, synthesize
    if a.beats:
        return _tts_beats(a)
    if not a.text or not a.out:
        sys.exit("tts: give TEXT -o OUT.wav, or --beats beats.json")
    mode, voice, clone, style = _voice_args(a.voice, a.mode, a.clone, a.style)
    out = Path(a.out)
    synthesize(a.text, out, style=style, mode=mode, voice=voice, clone_sample=clone)
    print(json.dumps({"audio_file": str(out),
                      "audio_seconds": round(audio_duration(out), 3)}))


def _tts_beats(a):
    """Synthesize/resume beats with atomic, per-success manifest checkpoints."""
    from anytomanim.beats import synthesize_beats
    from anytomanim.tts import draft_mode
    path = Path(a.beats).resolve()
    doc = json.loads(path.read_text())
    mode, voice, clone, style = _voice_args(
        a.voice or doc.get("voice"), a.mode, a.clone,
        a.style if a.style is not None else doc.get("style"), doc.get("language", "en"))
    adir = Path(a.audio_dir) if a.audio_dir else Path("audio")
    if not adir.is_absolute():
        adir = path.parent / adir
    try:
        doc, made = synthesize_beats(None, path, adir, mode=mode, voice=voice,
                                     clone_sample=clone, style=style,
                                     force=a.force, jobs=a.jobs)
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        sys.exit(str(exc))
    tag = "draft" if draft_mode() else f"{mode}:{voice}"
    total = sum(b.get("audio_seconds", 0) for b in doc["beats"])
    print(json.dumps({"beats": len(doc["beats"]), "synthesized": made,
                      "voice": tag, "total_seconds": round(total, 2),
                      "per_beat": {b["id"]: b.get("audio_seconds") for b in doc["beats"]}},
                     ensure_ascii=False))


# ------------------------------------------------------------------ measure
def cmd_measure(a):
    from anytomanim.tts import audio_duration
    for f in a.files:
        print(f"{f} {audio_duration(f):.3f}")


# ------------------------------------------------------------------ render
def cmd_render(a):
    from anytomanim import pipeline
    media = Path(a.media_dir) if a.media_dir else Path(a.scene).resolve().parent.parent / "media"
    mp4, err = pipeline.render(Path(a.scene), a.class_name or _cls_name(a.scene),
                               media, a.quality)
    if mp4 is None:
        print(err, file=sys.stderr)
        sys.exit(1)
    print(mp4)
    audit = mp4.with_suffix(".audit.json")
    if audit.exists():
        n = sum(len(b["issues"]) for b in json.loads(audit.read_text())["beats"])
        print(f"audit: {audit}  ({n} issue(s)) — run `anytomanim preview {mp4}`",
              file=sys.stderr)


def _cls_name(path: str) -> str:
    return Path(path).stem[0].upper() + Path(path).stem[1:]


# ------------------------------------------------------------------ preview
def cmd_preview(a):
    from anytomanim.preview import preview
    try:
        sheet, report, n = preview(
            Path(a.video), Path(a.out_dir) if a.out_dir else None,
            Path(a.audit) if a.audit else None, every=a.every)
    except ValueError as exc:
        sys.exit(f"preview: {exc}")
    if report:
        print(report.read_text())
    print(f"sheet:  {sheet}\nreport: {report or '(no audit — render with NarratedScene)'}\n"
          f"issues: {n}")


# ------------------------------------------------------------------ evaluation
def _spoiler_arg(value):
    import math
    try:
        token, seconds = value.rsplit(":", 1)
        seconds = float(seconds)
        if not token.strip() or not math.isfinite(seconds) or seconds < 0:
            raise ValueError
        return {"token": token, "not_before": seconds}
    except ValueError:
        raise argparse.ArgumentTypeError("spoiler must be TOKEN:SECONDS (nonnegative)") from None


def cmd_eval(a):
    from anytomanim.evaluate import evaluate
    try:
        result = evaluate(a.video, audit=a.audit, spoilers=a.spoiler)
    except (OSError, ValueError, RuntimeError) as exc:
        sys.exit(f"eval: {exc}")
    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    meta = result["meta"]
    print(f"{meta['duration']:.2f}s | {meta['width']}×{meta['height']} | "
          f"{meta['fps']:.2f} fps | audio: {'yes' if meta['has_audio'] else 'absent'}")
    for name in ("freeze", "silence", "black"):
        metric = result[name]
        detail = (f"{metric['total_seconds']:.2f}s ({metric['share']:.1%})"
                  if metric["share"] is not None else metric["reason"])
        if name == "freeze":
            detail += f", {metric['count']} intervals, longest {metric['longest_seconds']:.2f}s"
        print(f"{name}: {detail}")
    motion = result["motion"]
    print("motion: " + (f"{motion['still_share']:.1%} still pairs, "
                        f"mean changed-pixel share {motion['mean_change']:.5f}"
                        if motion["still_share"] is not None else "too short for an adjacent pair"))
    edge = result["edge_contact"]
    print(f"edge contact: sides {edge['left_or_right_share']:.1%}, "
          f"top {edge['top_share']:.1%}, bottom {edge['bottom_share']:.1%} "
          f"({edge['sample_count']} samples)")
    pacing = result["pacing"]
    print(f"pacing: {pacing['changes_per_minute']:.1f} scene-score changes/min "
          f"(threshold {pacing['scene_threshold']})")
    ocr = result["ocr"]
    print("OCR: " + (f"text in {ocr['text_seconds_share']:.1%} of sampled time"
                     if ocr["available"] else f"unavailable: {ocr['reason']}"))
    for item in result["spoilers"]:
        print(f"spoiler {item['token']!r}: first sampled {item['first_on_screen']}, "
              f"too early: {item['too_early']}")
    if result["audit"] is not None:
        print("audit: " + json.dumps(result["audit"], ensure_ascii=False))
    for flag in result["flags"]:
        print(f"! {flag}")


def cmd_judge(a):
    from anytomanim.judge import judge
    try:
        result = judge(a.a, a.b, a.topic, runs=a.runs, model=a.model,
                       effort=a.effort, seed=a.seed)
    except (OSError, ValueError, RuntimeError) as exc:
        sys.exit(f"judge: {exc}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_blind(a):
    from anytomanim.judge import blind_pack
    try:
        result = blind_pack(a.videos, a.out, a.seed)
    except (OSError, ValueError) as exc:
        sys.exit(f"blind: {exc}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


# ------------------------------------------------------------------ assemble
def cmd_assemble(a):
    from anytomanim import pipeline
    print(pipeline.assemble([Path(p) for p in a.inputs], Path(a.out)))


# ------------------------------------------------------------------ guides
def cmd_guides(a):
    dest = Path(a.dir)
    dest.mkdir(parents=True, exist_ok=True)
    for f in GUIDES_DIR.iterdir():
        if f.is_dir():
            shutil.copytree(f, dest / f.name, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(f, dest / f.name)
    voices = REPO / "voices.json"
    if voices.exists():
        shutil.copy2(voices, dest / "voices.json")
    print(f"exported {len(list(dest.iterdir()))} files -> {dest}")


# ------------------------------------------------------------------ subtitles
def cmd_storyboard(a):
    from anytomanim.storyboard import check_storyboard
    try:
        board = json.loads(Path(a.storyboard).read_text())
        beats = json.loads(Path(a.beats).read_text())
        issues = check_storyboard(board, beats)
    except (OSError, ValueError) as exc:
        sys.exit(f"storyboard: {exc}")
    for issue in issues:
        print(f"{issue['level']} {issue['beat']}: {issue['message']}")
    if any(i["level"] == "error" for i in issues):
        sys.exit(1)
    if not issues:
        print(f"storyboard: ok ({len(board['beats'])} beats)")


def cmd_subtitles(a):
    from anytomanim import subs
    beats = Path(a.beats)
    out_dir = Path(a.out_dir) if a.out_dir else beats.parent / "subs"
    audit = Path(a.audit) if a.audit else None
    if audit is None:
        for v in (a.mux, a.burn):
            if v and Path(v).with_suffix(".audit.json").exists():
                audit = Path(v).with_suffix(".audit.json")
    made = subs.generate(beats, out_dir,
                         ref_srt=Path(a.ref_srt) if a.ref_srt else None,
                         gap=a.gap, audit=audit)
    for m in made:
        print(m)
    if a.mux:
        out = Path(a.mux_out) if a.mux_out else \
            Path(a.mux).with_name(Path(a.mux).stem + "_subs.mp4")
        print(subs.mux(Path(a.mux), made, out))
    if a.burn:
        want = a.burn_srt or "bilingual"
        src = next((m for m in made if m.stem.endswith(f".{want}")),
                   made[0])
        out = Path(a.burn_out) if a.burn_out else \
            Path(a.burn).with_name(Path(a.burn).stem + "_burned.mp4")
        print(subs.burn(Path(a.burn), src, out))


# ------------------------------------------------------------------ bgm
def cmd_bgm(a):
    from anytomanim import bgm
    print(bgm.mix(Path(a.video), Path(a.music), Path(a.out),
                  level_db=a.level, duck=not a.no_duck))


# ------------------------------------------------------------------ run
def cmd_run(a):
    from anytomanim import pipeline
    mode, voice, clone, style = _voice_args(
        a.voice, a.mode, a.clone, a.style, a.language)
    inp = Path(a.input)
    text = inp.read_text() if inp.exists() and inp.is_file() else a.input
    out = pipeline.run(text, Path(a.workdir), language=a.language,
                       target_seconds=a.target_seconds, mode=mode,
                       voice=voice, clone_sample=clone,
                       style=style or "Calm, curious teacher. Measured pace, warm.",
                       quality=a.quality, fix_attempts=a.fix_attempts)
    print("DONE:", out)


# ------------------------------------------------------------------ bench
def cmd_bench(a):
    from anytomanim.bench import run_suite
    only = {"topic": a.topic, "model": a.model, "arm": a.arm}
    results = run_suite(Path(a.suite), Path(a.root), jobs=a.jobs, only=only)
    print(json.dumps(results, indent=2, ensure_ascii=False))


def cmd_bench_report(a):
    from anytomanim.bench import report
    try:
        result = report(Path(a.suite), Path(a.root), runs=a.runs, jobs=a.jobs,
                        judge_pairs=not a.metrics_only)
    except (OSError, ValueError, RuntimeError) as exc:
        sys.exit(f"bench-report: {exc}")
    print(json.dumps(result, indent=2, ensure_ascii=False))


# ------------------------------------------------------------------ main
def main():
    sys.path.insert(0, str(REPO / "src"))
    p = argparse.ArgumentParser(
        prog="anytomanim",
        description="Agent-callable toolchain: narrated 3b1b-style videos. "
                    "Start with `anytomanim doctor`, then read exported guides.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor").set_defaults(f=cmd_doctor)

    s = sub.add_parser("storyboard", help="check object continuity across narration beats")
    s.add_argument("storyboard")
    s.add_argument("--beats", required=True, help="reference beats.json (same IDs and order)")
    s.set_defaults(f=cmd_storyboard)

    s = sub.add_parser("tts", help="synthesize narration: one line, or every beat of beats.json")
    s.add_argument("text", nargs="?")
    s.add_argument("-o", "--out")
    s.add_argument("--beats", help="beats.json: synthesize all beats, write "
                                   "audio_file/audio_seconds back")
    s.add_argument("--audio-dir", help="with --beats: wav dir (default <beats dir>/audio)")
    s.add_argument("--force", action="store_true", help="with --beats: resynthesize all")
    s.add_argument("--jobs", type=int, default=4, help="with --beats: parallel requests")
    s.add_argument("--voice", default=None,
                   help="preset name (default: beats.json voice, else milo for en, baihua for zh)")
    s.add_argument("--mode", choices=["preset", "voicedesign", "voiceclone"])
    s.add_argument("--clone", default=None, help="path to your own voice sample")
    s.add_argument("--style", default=None)
    s.set_defaults(f=cmd_tts)

    s = sub.add_parser("measure", help="print wav/mp3 duration in seconds")
    s.add_argument("files", nargs="+")
    s.set_defaults(f=cmd_measure)

    s = sub.add_parser("render", help="render a scene file to mp4")
    s.add_argument("scene")
    s.add_argument("class_name", nargs="?", default=None)
    s.add_argument("--quality", default="ql", choices=["ql", "qm", "qh"])
    s.add_argument("--media-dir", default=None,
                   help="manim media dir (default: <scene dir>/../media)")
    s.set_defaults(f=cmd_render)

    s = sub.add_parser("preview", help="per-beat contact sheet + audit report of a render")
    s.add_argument("video")
    s.add_argument("--audit", default=None, help="default: <video>.audit.json")
    s.add_argument("--out-dir", default=None, help="default: <video>_preview/")
    s.add_argument("--every", type=float, default=3.0,
                   help="seconds between frames when there is no audit")
    s.set_defaults(f=cmd_preview)

    s = sub.add_parser("eval", help="video-only diagnostics for any MP4 (no overall score)")
    s.add_argument("video")
    s.add_argument("--audit", default=None, help="optional NarratedScene audit JSON")
    s.add_argument("--spoiler", nargs="+", action="extend", type=_spoiler_arg, default=[],
                   metavar="TOKEN:SECONDS", help="flag tokens sampled before their reveal time")
    s.add_argument("--json", action="store_true")
    s.set_defaults(f=cmd_eval)

    s = sub.add_parser("judge", help="blind visual-only pairwise judge via Codex CLI")
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("--topic", required=True)
    s.add_argument("--runs", type=int, default=3)
    s.add_argument("--model", default="gpt-6.1-sol")
    s.add_argument("--effort", default="high")
    s.add_argument("--seed", type=int, default=0)
    s.set_defaults(f=cmd_judge)

    s = sub.add_parser("blind", help="copy videos to opaque names for human review")
    s.add_argument("videos", nargs="+")
    s.add_argument("-o", "--out", required=True)
    s.add_argument("--seed", type=int, default=0)
    s.set_defaults(f=cmd_blind)

    s = sub.add_parser("assemble", help="concat mp4s")
    s.add_argument("inputs", nargs="+")
    s.add_argument("-o", "--out", required=True)
    s.set_defaults(f=cmd_assemble)

    s = sub.add_parser("export-guides",
                       help="copy WORKFLOW/DIGEST/SCRIPT/SCENE_GUIDE + schema")
    s.add_argument("dir", nargs="?", default="./anytomanim-guides")
    s.set_defaults(f=cmd_guides)

    s = sub.add_parser("subtitles",
                       help="generate per-language + bilingual .srt from beats.json; "
                            "optionally mux as selectable tracks into an mp4")
    s.add_argument("beats", help="beats.json path")
    s.add_argument("-o", "--out-dir", default=None)
    s.add_argument("--audit", default=None,
                   help="<Scene>.audit.json for exact beat timing "
                        "(auto-detected next to --mux/--burn video)")
    s.add_argument("--ref-srt", default=None,
                   help="manim-voiceover .srt (cues matched to beats by text)")
    s.add_argument("--gap", type=float, default=0.7,
                   help="inter-beat gap estimate when no audit/ref-srt")
    s.add_argument("--mux", default=None, help="mp4 to mux subtitle tracks into")
    s.add_argument("--mux-out", default=None)
    s.add_argument("--burn", default=None,
                   help="mp4 to hard-burn one srt into (font size 14 on a 512x288 canvas)")
    s.add_argument("--burn-srt", default=None,
                   help="which generated srt to burn: e.g. bilingual (default), en, zh")
    s.add_argument("--burn-out", default=None)
    s.set_defaults(f=cmd_subtitles)

    s = sub.add_parser("run", help="embedded-LLM reference driver (eval/batch)")
    s.add_argument("input")
    s.add_argument("--workdir", default="runs/last")
    s.add_argument("--language", default="en", choices=["en", "zh"])
    s.add_argument("--target-seconds", type=int, default=None)
    s.add_argument("--voice", default=None)
    s.add_argument("--mode", choices=["preset", "voicedesign", "voiceclone"])
    s.add_argument("--clone", default=None, help="path to your own voice sample")
    s.add_argument("--style", default=None)
    s.add_argument("--quality", default="qm", choices=["ql", "qm", "qh"])
    s.add_argument("--fix-attempts", type=int, default=3)
    s.set_defaults(f=cmd_run)

    s = sub.add_parser("bgm", help="mix a music bed under the video with voice ducking")
    s.add_argument("video", help="narrated mp4")
    s.add_argument("music", help="music file (e.g. ace-step output mp3/wav)")
    s.add_argument("-o", "--out", required=True)
    s.add_argument("--level", type=float, default=-12.0,
                   help="music gain in dB after ducking (default -12)")
    s.add_argument("--no-duck", action="store_true",
                   help="constant music level instead of sidechain ducking")
    s.set_defaults(f=cmd_bgm)

    s = sub.add_parser("bench", help="run a benchmark suite through Codex CLI")
    s.add_argument("suite", help="suite json, e.g. bench/suite.json")
    s.add_argument("--root", required=True, help="results dir, outside any repo")
    s.add_argument("--jobs", type=int, default=3)
    s.add_argument("--topic", action="append", help="repeatable filter")
    s.add_argument("--model", action="append", help="repeatable filter")
    s.add_argument("--arm", action="append", help="repeatable filter")
    s.set_defaults(f=cmd_bench)

    s = sub.add_parser("bench-report", help="summarize benchmark metrics and pairwise judgments")
    s.add_argument("suite", help="suite json, e.g. bench/suite.json")
    s.add_argument("--root", required=True, help="benchmark results dir")
    s.add_argument("--runs", type=int, default=2)
    s.add_argument("--jobs", type=int, default=3)
    s.add_argument("--metrics-only", action="store_true", help="skip pairwise judging")
    s.set_defaults(f=cmd_bench_report)

    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
