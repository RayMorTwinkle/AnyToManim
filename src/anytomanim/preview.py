"""Look at what you rendered: per-beat contact sheet + audit report.

    anytomanim preview media/videos/scene/1080p60/MyScene.mp4

With the `<Scene>.audit.json` that NarratedScene writes next to the mp4, the
sheet shows two frames per beat (mid-beat and the last frame of the beat) and
the report lists, per beat: what is on screen (and since which beat — leftovers
from earlier beats are the classic bug), overlapping/small/off-frame text,
animation overrunning the narration, and frozen time. Without an audit it
falls back to one frame every `every` seconds.

Pixel layout warnings run with or without an audit. Timing falls back to a
nearby beats.json, then equal time segments. Warnings do not add to issue count.

The host agent is expected to READ sheet.png (it is an image) and the report
after every render, then fix what it sees — see guides/WORKFLOW.md.
"""
from __future__ import annotations

import json
import math
import subprocess
import tempfile
from pathlib import Path

from .tts import audio_duration

TILE_W = 640
COLS = 3


def _grab(video: Path, t: float, out: Path) -> bool:
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(t, 0):.3f}",
                        "-i", str(video), "-frames:v", "1",
                        "-vf", f"scale={TILE_W}:-2", str(out)],
                       capture_output=True)
    return r.returncode == 0 and out.exists()


def _sheet(frames: list[tuple[Path, str]], out: Path, *, label_band: int = 0) -> Path:
    from PIL import Image, ImageDraw, ImageFont
    imgs = [(Image.open(p).convert("RGB"), label) for p, label in frames]
    if not imgs:
        raise RuntimeError("no frames extracted")
    w, h = imgs[0][0].size
    tile_h = h + label_band
    rows = (len(imgs) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * w, rows * tile_h), (40, 40, 40))
    try:
        font = ImageFont.load_default(size=22)
    except TypeError:  # Pillow < 10.1
        font = ImageFont.load_default()
    for i, (im, label) in enumerate(imgs):
        x, y = (i % COLS) * w, (i // COLS) * tile_h
        sheet.paste(im, (x, y + label_band))
        d = ImageDraw.Draw(sheet)
        tb = d.textbbox((x + 8, y + 6), label, font=font)
        d.rectangle((tb[0] - 4, tb[1] - 3, tb[2] + 4, tb[3] + 3), fill=(0, 0, 0))
        d.text((x + 8, y + 6), label, fill=(255, 230, 80), font=font)
        d.rectangle((x, y, x + w - 1, y + tile_h - 1), outline=(90, 90, 90))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def report_text(audit: dict) -> tuple[str, int]:
    lines, n_issues = [f"scene {audit.get('scene', '?')}"], 0
    for b in audit["beats"]:
        lines.append(f"\n[{b['beat']}] {b['start']:.2f}–{b['end']:.2f}s "
                     f"(audio {b['audio_seconds']:.2f}s, static {b['static_fraction']:.0%})")
        for it in b["on_screen"]:
            if not it["visible"]:
                continue
            tag = "" if it["since"] == b["beat"] else f"   ← since {it['since']}"
            lines.append(f"    {it['label']}{tag}")
        for iss in b["issues"]:
            lines.append(f"  ! {iss}")
            n_issues += 1
    return "\n".join(lines), n_issues


def _layout_beats(video: Path, data: dict | None, total: float, every: float):
    if data and data.get("beats"):
        return data["beats"], "audit (rendered beat boundaries)"
    for parent in (video.parent, video.parent.parent):
        path = parent / "beats.json"
        if not path.is_file():
            continue
        doc = json.loads(path.read_text())
        rows = doc.get("beats", [])
        if not rows:
            continue
        durations = [b.get("audio_seconds", b.get("est_seconds", 0)) for b in rows]
        measured = all(isinstance(d, (int, float)) and math.isfinite(d) and d > 0
                       for d in durations)
        if not measured:
            durations = [1] * len(rows)
        scale = total / sum(durations)
        windows, t = [], 0.0
        for i, (row, d) in enumerate(zip(rows, durations), 1):
            end = t + d * scale
            windows.append(dict(beat=row.get("id", f"b{i:02}"), start=t, end=end))
            t = end
        return windows, f"estimated from {path} ({'duration-weighted' if measured else 'equal'}; scaled to video)"
    count = max(1, math.ceil(total / every))
    return [dict(beat=f"segment{i+1:02}", start=total * i / count,
                 end=total * (i + 1) / count) for i in range(count)], "estimated equal time segments (no beat metadata)"


def _layout_report(layout: dict, source: str) -> str:
    lines = [f"\nLayout review (warnings only; bottom {layout['excluded_bottom_share']:.0%} excluded)\nTiming: {source}"]
    for warning in layout["warnings"]:
        lines.append(f"warning all: {warning}")
    for beat in layout["beats"]:
        lines.append(f"\n[{beat['beat']}] {beat['start']:.2f}–{beat['end']:.2f}s layout")
        if beat["sample_count"]:
            bands = "/".join(f"{ink:.1%}" for ink in beat["band_ink"])
            lines.append(f"    box median {beat['box_width']:.0%} wide × {beat['box_height']:.0%} high; "
                         f"upper/middle/lower ink {bands}; longest frozen {beat['longest_frozen_seconds']:.2f}s")
        for warning in beat["warnings"]:
            lines.append(f"warning {beat['beat']}: {warning}")
    return "\n".join(lines)


def preview(video: Path, out_dir: Path | None = None, audit: Path | None = None,
            every: float = 3.0) -> tuple[Path, Path | None, int]:
    """-> (sheet.png, report.txt, audit issue count excluding pixel warnings)."""
    if not math.isfinite(every) or every <= 0:
        raise ValueError("preview interval must be finite and positive")
    video = Path(video).resolve()
    out_dir = Path(out_dir) if out_dir else video.with_name(video.stem + "_preview")
    out_dir.mkdir(parents=True, exist_ok=True)
    audit = Path(audit) if audit else video.with_suffix(".audit.json")
    data = json.loads(audit.read_text()) if audit.exists() else None
    total = audio_duration(video)

    marks: list[tuple[float, str]] = []
    if data:
        for b in data["beats"]:
            mid = b["start"] + 0.5 * (b["end"] - b["start"])
            marks.append((mid, f"{b['beat']} mid {mid:.1f}s"))
            marks.append((b["end"] - 0.1, f"{b['beat']} end {b['end']:.1f}s"))
    else:
        t = 0.0
        while t < total:
            marks.append((t + 0.05, f"{t:.1f}s"))
            t += every

    with tempfile.TemporaryDirectory() as d:
        frames = []
        for i, (t, label) in enumerate(marks):
            p = Path(d) / f"f{i:03d}.png"
            if _grab(video, t, p):
                frames.append((p, label))
        sheet = _sheet(frames, out_dir / "sheet.png")

    text, n = report_text(data) if data else (f"video {video.name} (no scene audit)", 0)
    from .layout import analyze_layout
    try:
        windows, source = _layout_beats(video, data, total, every)
        layout = analyze_layout(video, windows, total)
        layout["timing_source"] = source
        (out_dir / "layout.json").write_text(json.dumps(layout, indent=2) + "\n")
        text += "\n" + _layout_report(layout, source)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        text += f"\nwarning all: pixel layout review unavailable: {exc}"
        (out_dir / "layout.json").write_text(json.dumps(dict(available=False, reason=str(exc))) + "\n")
    rep = out_dir / "report.txt"
    rep.write_text(text + "\n")
    return sheet, rep, n
