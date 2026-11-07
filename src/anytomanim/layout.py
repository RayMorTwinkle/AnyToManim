"""Pixel-based preview warnings, independent of Manim's object inventory.

These are review prompts, not render failures. Decode once at low resolution;
keep seven interior samples per beat and reuse evaluation's freeze parser.
"""
from __future__ import annotations

from collections import Counter
import math
from pathlib import Path
from statistics import median
import subprocess
import tempfile

from .evaluate import FREEZE_NOISE, _intervals, ffmpeg_binary

SAMPLE_WIDTH = 160
SAMPLE_HEIGHT = 90
SAMPLE_FPS = 4
EXCLUDE_BOTTOM = 0.15       # Burned bilingual subtitles reach about 14%.
SAMPLES_PER_BEAT = 7
CONTENT_DELTA = 20          # Luma difference from modal background; ignore codec noise.
MIN_BOX_WIDTH = 0.80        # Calibration: gradient b06–b08 span only 73–74%.
MIN_BOX_HEIGHT = 0.75       # Calibration: hash b01–b02 / Fourier b01 are shallow.
SMALL_SAMPLE_SHARE = 0.50   # A brief entrance alone must not flag the whole beat.
EMPTY_INK_SHARE = 0.005     # <0.5% ink in a third is effectively an empty band.
EMPTY_SAMPLE_SHARE = 0.80  # Tolerate one transient sample of seven.
HEADER_HEIGHT = 0.14       # Top 14% of original frame, above the working area.
HEADER_MIN_INK = 0.01      # Black/solid backgrounds never count as headers.
HEADER_MIN_IOU = 0.90      # Compare foreground masks, not mostly-black rectangles.
HEADER_SAMPLE_SHARE = 0.80 # Tolerate a title's entrance in the first beat.
HEADER_BEAT_SHARE = 0.90   # Nearly all beats must share the same visible header.
HEADER_MIN_BEATS = 3
FROZEN_SECONDS = 3.0       # Warn only for a contiguous interval strictly over 3s.


def _decode(video: Path, duration: float, wanted: set[int]):
    """Selected gray frames and all frozen intervals (including EOF)."""
    height = int(SAMPLE_HEIGHT * (1 - EXCLUDE_BOTTOM))
    size = SAMPLE_WIDTH * height
    binary = ffmpeg_binary(("scale", "format", "crop", "fps", "freezedetect"))
    filters = (f"scale={SAMPLE_WIDTH}:{SAMPLE_HEIGHT},format=gray,"
               f"crop={SAMPLE_WIDTH}:{height}:0:0,"
               f"freezedetect=n={FREEZE_NOISE}:d={FROZEN_SECONDS},"
               f"fps={SAMPLE_FPS}:start_time=0:round=up")
    args = [binary, "-hide_banner", "-nostdin", "-i", str(video), "-map", "0:v:0",
            "-vf", filters, "-an", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"]
    frames, index = {}, 0
    with tempfile.TemporaryFile() as err:
        with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=err) as proc:
            try:
                while True:
                    raw = proc.stdout.read(size)
                    if not raw:
                        break
                    if len(raw) != size:
                        raise ValueError("incomplete decoded layout frame")
                    if index in wanted:
                        frames[index] = raw
                    index += 1
                proc.wait(timeout=30)
            except BaseException:
                proc.kill()
                proc.wait()
                raise
            err.seek(0)
            log = err.read().decode(errors="replace")
            if proc.returncode:
                raise ValueError("cannot sample layout: " + log[-1000:])
    if not frames:
        raise ValueError("video has no decodable layout samples")
    return frames, _intervals(log, "freeze", duration)


def _frame_stats(raw: bytes) -> dict:
    height = len(raw) // SAMPLE_WIDTH
    background = Counter(raw).most_common(1)[0][0]
    ink = {i for i, value in enumerate(raw) if abs(value - background) > CONTENT_DELTA}
    if ink:
        xs, ys = [i % SAMPLE_WIDTH for i in ink], [i // SAMPLE_WIDTH for i in ink]
        width, box_height = ((max(xs) - min(xs) + 1) / SAMPLE_WIDTH,
                             (max(ys) - min(ys) + 1) / height)
    else:
        width, box_height = 0.0, 0.0
    bands = []
    for k in range(3):
        lo, hi = (k * height // 3) * SAMPLE_WIDTH, ((k + 1) * height // 3) * SAMPLE_WIDTH
        bands.append(sum(lo <= i < hi for i in ink) / (hi - lo))
    header_size = SAMPLE_WIDTH * int(SAMPLE_HEIGHT * HEADER_HEIGHT)
    return dict(width=width, height=box_height, bands=bands,
                header={i for i in ink if i < header_size})


def _same_header(a: set[int], b: set[int]) -> bool:
    minimum = HEADER_MIN_INK * SAMPLE_WIDTH * int(SAMPLE_HEIGHT * HEADER_HEIGHT)
    return (min(len(a), len(b)) >= minimum
            and len(a & b) / len(a | b) >= HEADER_MIN_IOU)


def analyze_layout(video: Path, beats: list[dict], duration: float) -> dict:
    """Return measured per-beat warnings plus a video-level persistent header."""
    indices = []
    last = max(0, math.ceil(duration * SAMPLE_FPS) - 1)
    for beat in beats:
        start, end = max(0, beat["start"]), min(duration, beat["end"])
        # Interior samples avoid cuts and end-of-beat fades. Deduplicate short beats.
        indices.append(sorted({min(last, max(0, round((start + (end - start) *
            (0.1 + 0.8 * k / (SAMPLES_PER_BEAT - 1))) * SAMPLE_FPS)))
            for k in range(SAMPLES_PER_BEAT)}) if end > start else [])
    raw, frozen = _decode(video, duration, {i for group in indices for i in group})
    result, headers = [], []
    for beat, group in zip(beats, indices):
        samples = [_frame_stats(raw[i]) for i in group if i in raw]
        warnings = []
        if not samples:
            warnings.append("no layout samples within this beat")
        for axis, threshold in (("width", MIN_BOX_WIDTH), ("height", MIN_BOX_HEIGHT)):
            small = sum(s[axis] < threshold for s in samples)
            if samples and small / len(samples) >= SMALL_SAMPLE_SHARE:
                warnings.append(f"small content box: {axis} < {threshold:.0%} "
                                f"in {small}/{len(samples)} samples "
                                f"(median {median(s[axis] for s in samples):.0%})")
        empty = []
        for k, name in enumerate(("upper", "middle", "lower")):
            count = sum(s["bands"][k] < EMPTY_INK_SHARE for s in samples)
            if samples and count / len(samples) >= EMPTY_SAMPLE_SHARE:
                empty.append(name)
                warnings.append(f"empty {name} band: <{EMPTY_INK_SHARE:.1%} ink "
                                f"in {count}/{len(samples)} samples")
        intervals = [(max(a, beat["start"]), min(b, beat["end"])) for a, b in frozen]
        longest = max((max(0, b - a) for a, b in intervals), default=0)
        if longest > FROZEN_SECONDS:
            warnings.append(f"frozen: {longest:.2f}s continuously (>{FROZEN_SECONDS:g}s, subtitles excluded)")
        headers.append([s["header"] for s in samples])
        result.append(dict(beat=beat["beat"], start=beat["start"], end=beat["end"],
                           sample_count=len(samples),
                           box_width=median(s["width"] for s in samples) if samples else None,
                           box_height=median(s["height"] for s in samples) if samples else None,
                           band_ink=[median(s["bands"][k] for s in samples) for k in range(3)]
                           if samples else None, empty_bands=empty,
                           longest_frozen_seconds=longest, warnings=warnings))
    warnings, matching = [], []
    if len(beats) >= HEADER_MIN_BEATS:
        # A candidate may come from any beat: an introductory black frame cannot
        # prevent detection. Each beat votes once, regardless of its length.
        for group in headers:
            if not group:
                continue
            candidate = group[len(group) // 2]
            matched = [b["beat"] for b, samples in zip(beats, headers) if samples and
                       sum(_same_header(candidate, h) for h in samples) / len(samples)
                       >= HEADER_SAMPLE_SHARE]
            if len(matched) > len(matching):
                matching = matched
        if len(matching) / len(beats) >= HEADER_BEAT_SHARE:
            warnings.append(f"persistent header: unchanged visible top content in "
                            f"{len(matching)}/{len(beats)} beats ({', '.join(matching)})")
    return dict(available=True, beats=result, warnings=warnings, header_beats=matching,
                excluded_bottom_share=EXCLUDE_BOTTOM, sample_size=[SAMPLE_WIDTH, SAMPLE_HEIGHT],
                sample_fps=SAMPLE_FPS, freeze_noise=FREEZE_NOISE)
