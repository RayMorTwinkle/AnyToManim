"""Video-only diagnostics, usable on external MP4s. No aggregate quality score.

All shares use video duration. These are screening proxies, not verdicts:
static diagrams can be useful, edge contact need not be clipping, scene scores
miss gradual builds, and OCR reports first *sampled* appearance (1s resolution).
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata

FREEZE_NOISE = 0.001
FREEZE_MIN_SECONDS = 2
SILENCE_NOISE_DB = -35
SILENCE_MIN_SECONDS = 1
BLACK_MIN_SECONDS = 0.1
BLACK_PIXEL_THRESHOLD = 0.10
BLACK_PICTURE_THRESHOLD = 0.999
METRICS_VERSION = 2
MOTION_FPS = 4
MOTION_WIDTH = 160
MOTION_HEIGHT = 90
MOTION_PIXEL_THRESHOLD = 12
MOTION_STILL_THRESHOLD = 0.0005
MOTION_EXCLUDE_BOTTOM = 0.15
SCENE_THRESHOLD = 0.01
EDGE_FPS = 2
EDGE_WIDTH = 320
EDGE_RING_SHARE = 0.02
EDGE_COLOR_DISTANCE = 35
EDGE_CONTENT_SHARE = 0.02
OCR_FPS = 1
OCR_WIDTH = 1280

# Heuristics for review, deliberately not a pass/fail quality scale.
FLAG_FREEZE_SHARE = 0.30
FLAG_SILENCE_SHARE = 0.20
FLAG_BLACK_SHARE = 0.10
FLAG_EDGE_SHARE = 0.10
FLAG_CHANGES_PER_MINUTE = 2
FLAG_STILL_SHARE = 0.70


@lru_cache(maxsize=None)
def _filters(binary: str) -> frozenset[str]:
    r = subprocess.run([binary, "-hide_banner", "-filters"],
                       capture_output=True, text=True, timeout=20)
    if r.returncode:
        raise RuntimeError(f"cannot inspect ffmpeg build: {binary}")
    return frozenset(m.group(1) for m in re.finditer(
        r"^\s*[TSC.]{3}\s+(\w+)\s", r.stdout, re.MULTILINE))


@lru_cache(maxsize=None)
def ffmpeg_binary(required: tuple[str, ...] = ()) -> str:
    """Prefer imageio's build, but verify filters on each candidate build."""
    candidates = []
    try:
        import imageio_ffmpeg
        candidates.append(imageio_ffmpeg.get_ffmpeg_exe())
    except (ImportError, RuntimeError, OSError):
        pass
    path = shutil.which("ffmpeg")
    if path and path not in candidates:
        candidates.append(path)
    failures = []
    for binary in candidates:
        try:
            missing = set(required) - _filters(binary)
            if not missing:
                return binary
            failures.append(f"{binary}: missing {', '.join(sorted(missing))}")
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            failures.append(str(exc))
    raise RuntimeError("no working ffmpeg build: " + "; ".join(failures))


def probe(video) -> dict:
    video = Path(video).resolve()
    if not video.is_file():
        raise ValueError(f"video does not exist: {video}")
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_streams",
                            "-show_format", "-of", "json", str(video)],
                           capture_output=True, text=True, timeout=30)
    except OSError as exc:
        raise RuntimeError("ffprobe is required to read video metadata") from exc
    try:
        data = json.loads(r.stdout)
        stream = next(s for s in data["streams"] if s["codec_type"] == "video"
                      and not s.get("disposition", {}).get("attached_pic"))
        duration = float(stream.get("duration") or data["format"]["duration"])
        num, den = stream.get("avg_frame_rate", "0/1").split("/")
        fps = float(num) / float(den) if float(den) else 0.0
        width, height = int(stream["width"]), int(stream["height"])
        if r.returncode or not math.isfinite(duration) or duration <= 0 or min(width, height) <= 0:
            raise ValueError("invalid video metadata")
    except (ValueError, KeyError, StopIteration, TypeError) as exc:
        raise ValueError(f"cannot read video (corrupt or no decodable video stream): {video}; "
                         f"{r.stderr.strip()[-500:]}") from exc
    # ffmpeg autorotates decoded frames, so report their display dimensions.
    for side in stream.get("side_data_list", []):
        if abs(float(side.get("rotation", 0))) % 180 == 90:
            width, height = height, width
            break
    return {"duration": duration, "width": width, "height": height, "fps": fps,
            "has_audio": any(s["codec_type"] == "audio" for s in data["streams"])}


def _run_ffmpeg(binary, args, duration):
    r = subprocess.run([binary, "-hide_banner", "-nostdin", *args],
                       capture_output=True, text=True,
                       timeout=max(60, duration * 4))
    if r.returncode:
        raise ValueError("cannot decode video: " + r.stderr.strip()[-1500:])
    return r.stderr


def _intervals(log: str, name: str, duration: float) -> list[tuple[float, float]]:
    """Pair starts/ends, including a freeze/silence still open at EOF."""
    intervals, start = [], None
    for kind, value in re.findall(rf"\b{name}_(start|end)\s*:\s*([\d.eE+-]+)", log):
        value = min(duration, max(0, float(value)))
        if kind == "start":
            if start is None:
                start = value
        elif start is not None:
            intervals.append((start, max(start, value)))
            start = None
    if start is not None:
        intervals.append((start, duration))
    return [(a, b) for a, b in intervals if b > a]


def _totals(intervals, duration):
    total = sum(b - a for a, b in intervals)
    return {"total_seconds": total, "share": min(1.0, total / duration)}


def _motion_samples(video, meta):
    """(time, changed-pixel share, mean absolute luma delta) per adjacent pair.

    Decode at 4 fps, 160x90; omit the bottom 15% before comparing. Keep only
    pair statistics in memory. The first sample has no predecessor.
    """
    import numpy as np

    binary = ffmpeg_binary(("fps", "scale", "format"))
    args = [binary, "-v", "error", "-nostdin", "-i", str(video), "-map", "0:v:0",
            "-vf", f"fps={MOTION_FPS}:start_time=0:round=up,"
            f"scale={MOTION_WIDTH}:{MOTION_HEIGHT},format=gray",
            "-an", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"]
    size = MOTION_WIDTH * MOTION_HEIGHT
    kept = MOTION_WIDTH * int(MOTION_HEIGHT * (1 - MOTION_EXCLUDE_BOTTOM))
    samples, previous, index = [], None, 0
    last = max(0, meta["duration"] - 1 / (meta["fps"] or 25))
    with tempfile.TemporaryFile() as err:
        with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=err) as proc:
            try:
                while True:
                    raw = proc.stdout.read(size)
                    if not raw:
                        break
                    if len(raw) != size:
                        raise ValueError("incomplete decoded motion frame")
                    frame = np.frombuffer(raw[:kept], dtype=np.uint8).astype(np.int16)
                    if previous is not None:
                        delta = np.abs(frame - previous)
                        samples.append((min(index / MOTION_FPS, last),
                                        float((delta > MOTION_PIXEL_THRESHOLD).mean()),
                                        float(delta.mean())))
                    previous = frame
                    index += 1
                proc.wait(timeout=30)
            except BaseException:
                proc.kill()
                proc.wait()
                raise
            if proc.returncode:
                err.seek(0)
                raise ValueError("cannot sample motion: " + err.read().decode(errors="replace")[-1000:])
    if not index:
        raise ValueError("video has no decodable motion frames")
    return samples


def _motion(video, meta):
    samples = _motion_samples(video, meta)
    return {"still_share": (sum(s[1] < MOTION_STILL_THRESHOLD for s in samples) / len(samples)
                            if samples else None),
            "mean_change": sum(s[1] for s in samples) / len(samples) if samples else None,
            "pair_count": len(samples), "sample_fps": MOTION_FPS,
            "sample_width": MOTION_WIDTH, "sample_height": MOTION_HEIGHT,
            "excluded_bottom_share": MOTION_EXCLUDE_BOTTOM,
            "pixel_threshold": MOTION_PIXEL_THRESHOLD, "still_threshold": MOTION_STILL_THRESHOLD,
            "mean_change_definition": "Mean share of retained pixels with absolute luma delta > 12."}


def _edge_contact(video, meta):
    import numpy as np

    width = min(EDGE_WIDTH, meta["width"])
    height = max(1, round(width * meta["height"] / meta["width"]))
    binary = ffmpeg_binary(("fps", "scale", "format"))
    args = [binary, "-v", "error", "-nostdin", "-i", str(video), "-map", "0:v:0",
            "-vf", f"fps={EDGE_FPS}:start_time=0:round=up,scale={width}:{height}",
            "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
    hits = Counter()
    count = 0
    with tempfile.TemporaryFile() as err:
        with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=err) as proc:
            try:
                size = width * height * 3
                while True:
                    raw = proc.stdout.read(size)
                    if not raw:
                        break
                    if len(raw) != size:
                        raise ValueError("incomplete decoded video frame")
                    frame = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 3)
                    ch, cw = max(1, height // 20), max(1, width // 20)
                    corners = np.concatenate([frame[:ch, :cw].reshape(-1, 3),
                                              frame[:ch, -cw:].reshape(-1, 3),
                                              frame[-ch:, :cw].reshape(-1, 3),
                                              frame[-ch:, -cw:].reshape(-1, 3)])
                    bg = np.median(corners, axis=0)
                    content = np.max(np.abs(frame.astype(float) - bg), axis=2) > EDGE_COLOR_DISTANCE
                    rh = max(1, round(height * EDGE_RING_SHARE))
                    rw = max(1, round(width * EDGE_RING_SHARE))
                    touching = {"left": content[:, :rw].mean() > EDGE_CONTENT_SHARE,
                                "right": content[:, -rw:].mean() > EDGE_CONTENT_SHARE,
                                "top": content[:rh].mean() > EDGE_CONTENT_SHARE,
                                "bottom": content[-rh:].mean() > EDGE_CONTENT_SHARE}
                    touching["left_or_right"] = touching["left"] or touching["right"]
                    hits.update(k for k, v in touching.items() if v)
                    count += 1
                proc.wait(timeout=30)
            except BaseException:
                proc.kill()
                proc.wait()
                raise
            if proc.returncode:
                err.seek(0)
                raise ValueError("cannot sample video: " + err.read().decode(errors="replace")[-1000:])
    if not count:
        raise ValueError("video has no decodable frames")
    return {"sample_count": count, "sample_fps": EDGE_FPS,
            "sample_width": width, "ring_share": EDGE_RING_SHARE,
            "color_distance": EDGE_COLOR_DISTANCE, "content_share_threshold": EDGE_CONTENT_SHARE,
            **{k + "_share": hits[k] / count
               for k in ("left", "right", "left_or_right", "top", "bottom")}}


def _vision_binary() -> Path:
    if sys.platform != "darwin" or not Path("/usr/bin/swift").exists():
        raise RuntimeError("macOS Vision and /usr/bin/swift are required")
    source = Path(__file__).with_name("vision_ocr.swift")
    fingerprint = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    cache = Path(os.environ.get("ANYTOMANIM_CACHE_DIR",
                                str(Path(tempfile.gettempdir()) / "anytomanim-cache")))
    cache.mkdir(parents=True, exist_ok=True)
    binary = cache / f"vision-ocr-{fingerprint}"
    import fcntl
    with binary.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if binary.is_file():
            return binary
        # Keep compiler caches here too; do not require a writable home directory.
        with tempfile.TemporaryDirectory(dir=cache) as tmp:
            built = Path(tmp) / "vision-ocr"
            r = subprocess.run(["/usr/bin/swiftc", str(source), "-o", str(built),
                                "-module-cache-path", str(cache / "modules")],
                               capture_output=True, text=True, timeout=120)
            if r.returncode:
                raise RuntimeError("Vision helper compilation failed: " + r.stderr[-1200:])
            built.replace(binary)
    return binary


def _ocr(video, meta):
    try:
        helper = _vision_binary()
        with tempfile.TemporaryDirectory(prefix="anytomanim-ocr-") as tmp:
            root = Path(tmp)
            binary = ffmpeg_binary(("fps", "scale"))
            _run_ffmpeg(binary, ["-v", "error", "-i", str(video), "-map", "0:v:0",
                                "-vf", f"fps={OCR_FPS}:start_time=0:round=up,"
                                f"scale='min({OCR_WIDTH},iw)':-2",
                                str(root / "frame-%06d.png")], meta["duration"])
            frames = sorted(root.glob("frame-*.png"))
            if not frames:
                raise RuntimeError("no OCR frames decoded")
            r = subprocess.run([str(helper)], input=json.dumps([str(p) for p in frames]),
                               capture_output=True, text=True,
                               timeout=max(60, meta["duration"] * 4))
            if r.returncode:
                raise RuntimeError("Vision recognition failed: " + r.stderr[-1200:])
            texts = json.loads(r.stdout)
            if len(texts) != len(frames):
                raise RuntimeError("Vision returned an incomplete sample list")
            samples = [{"timestamp": i / OCR_FPS, "text": "\n".join(lines)}
                       for i, lines in enumerate(texts)]
            seconds = sum(min(1 / OCR_FPS, max(0, meta["duration"] - s["timestamp"]))
                          for s in samples if s["text"].strip())
            return {"available": True, "sample_fps": OCR_FPS,
                    "languages": ["zh-Hant", "zh-Hans", "en-US"],
                    "samples": samples, "text_seconds_share": seconds / meta["duration"]}
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        return {"available": False, "reason": str(exc)}


def _normalise(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def _spoilers(specs, ocr):
    results = []
    for spec in specs or []:
        token, not_before = spec["token"], float(spec["not_before"])
        if not isinstance(token, str) or not _normalise(token) or not math.isfinite(not_before) or not_before < 0:
            raise ValueError("spoilers require a nonempty token and finite nonnegative not_before")
        first = next((s["timestamp"] for s in ocr.get("samples", [])
                      if _normalise(token) in _normalise(s["text"])), None)
        results.append({"token": token, "not_before": not_before,
                        "available": ocr["available"], "first_on_screen": first,
                        "too_early": first < not_before if first is not None else
                        (False if ocr["available"] else None)})
    return results


def _audit_counts(audit):
    if audit is None:
        return None
    data = audit if isinstance(audit, dict) else json.loads(Path(audit).read_text())
    counts = Counter()
    for beat in data.get("beats", []):
        for issue in beat.get("issues", []):
            if isinstance(issue, dict):
                kind = issue.get("type", "unknown")
            else:
                # NarratedScene currently stores human-readable issue strings.
                kind = next((k for k in ("off-frame", "small text", "overlap", "overrun", "static")
                             if issue.startswith(k)), issue.split(":", 1)[0])
            counts[kind] += 1
    return {"issue_counts": dict(counts), "total_issues": sum(counts.values()),
            "partial": bool(data.get("partial", False))}


def evaluate_cached(video) -> dict:
    """evaluate() once per file version; OCR makes repeat runs expensive."""
    video = Path(video).resolve()
    st = video.stat()
    key = hashlib.sha256(f"{METRICS_VERSION}|{video}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:24]
    cache = Path(os.environ.get("ANYTOMANIM_CACHE_DIR",
                                str(Path(tempfile.gettempdir()) / "anytomanim-cache"))) / "eval"
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{key}.json"
    if path.is_file():
        return json.loads(path.read_text())
    result = evaluate(video)
    path.write_text(json.dumps(result, ensure_ascii=False))
    return result


def evaluate(video, audit=None, spoilers=None) -> dict:
    """Measure a video without project metadata; raises ValueError for bad input."""
    video = Path(video).resolve()
    meta = probe(video)
    duration = meta["duration"]
    needed = ("freezedetect", "blackdetect", "select", "showinfo")
    if meta["has_audio"]:
        needed += ("silencedetect",)
    binary = ffmpeg_binary(needed)
    vf = (f"freezedetect=n={FREEZE_NOISE}:d={FREEZE_MIN_SECONDS},"
          f"blackdetect=d={BLACK_MIN_SECONDS}:pix_th={BLACK_PIXEL_THRESHOLD}:"
          f"pic_th={BLACK_PICTURE_THRESHOLD},select='gt(scene,{SCENE_THRESHOLD})',showinfo")
    args = ["-i", str(video), "-map", "0:v:0", "-vf", vf]
    if meta["has_audio"]:
        args += ["-map", "0:a:0", "-af",
                 f"silencedetect=noise={SILENCE_NOISE_DB}dB:d={SILENCE_MIN_SECONDS}"]
    args += ["-f", "null", "-"]
    log = _run_ffmpeg(binary, args, duration)
    frozen = _intervals(log, "freeze", duration)
    freeze = {**_totals(frozen, duration), "count": len(frozen),
              "longest_seconds": max((b - a for a, b in frozen), default=0),
              "noise": FREEZE_NOISE, "min_seconds": FREEZE_MIN_SECONDS}
    silence = ({"available": True, **_totals(_intervals(log, "silence", duration), duration),
                "noise_db": SILENCE_NOISE_DB, "min_seconds": SILENCE_MIN_SECONDS}
               if meta["has_audio"] else {"available": False, "reason": "no audio stream",
                                          "total_seconds": None, "share": None})
    black = {**_totals(_intervals(log, "black", duration), duration),
             "min_seconds": BLACK_MIN_SECONDS, "pixel_threshold": BLACK_PIXEL_THRESHOLD,
             "picture_threshold": BLACK_PICTURE_THRESHOLD}
    changes = len(re.findall(r"\[Parsed_showinfo[^\]]*\].*?\bn:\s*\d+.*?\bpts_time:", log))
    pacing = {"visual_changes": changes, "changes_per_minute": changes * 60 / duration,
              "scene_threshold": SCENE_THRESHOLD}
    edge = _edge_contact(video, meta)
    motion = _motion(video, meta)
    ocr = _ocr(video, meta)
    spoiler_results = _spoilers(spoilers, ocr)
    flags = []
    if motion["still_share"] is not None and motion["still_share"] >= FLAG_STILL_SHARE:
        flags.append(f"Still samples occupy {motion['still_share']:.1%} of adjacent motion pairs "
                     f"(review threshold {FLAG_STILL_SHARE:.0%}); review visual progression.")
    for name, metric, threshold in (("Frozen video", freeze, FLAG_FREEZE_SHARE),
                                     ("Silence", silence, FLAG_SILENCE_SHARE),
                                     ("Black frames", black, FLAG_BLACK_SHARE)):
        if metric["share"] is not None and metric["share"] > threshold:
            flags.append(f"{name} occupies {metric['share']:.1%} of the video (review threshold {threshold:.0%}).")
    if not meta["has_audio"]:
        flags.append("No audio stream; silence cannot be measured.")
    for ring in ("left_or_right", "top", "bottom"):
        if edge[ring + "_share"] > FLAG_EDGE_SHARE:
            flags.append(f"Content touches the {ring.replace('_', ' ')} edge ring in "
                         f"{edge[ring + '_share']:.1%} of samples (review threshold {FLAG_EDGE_SHARE:.0%}); "
                         "this may be intentional rather than clipping.")
    if pacing["changes_per_minute"] < FLAG_CHANGES_PER_MINUTE:
        flags.append(f"Fewer than {FLAG_CHANGES_PER_MINUTE} scene-score changes per minute; "
                     "gradual motion and useful static diagrams may not register.")
    if not ocr["available"]:
        flags.append("OCR unavailable; text coverage and spoiler checks are unverified.")
    for item in spoiler_results:
        if item["too_early"]:
            flags.append(f"Spoiler {item['token']!r} first sampled at {item['first_on_screen']:.1f}s, "
                         f"before {item['not_before']:.1f}s.")
    return {"metrics_version": METRICS_VERSION, "meta": meta, "freeze": freeze,
            "silence": silence, "black": black, "motion": motion,
            "edge_contact": edge, "pacing": pacing, "ocr": ocr,
            "spoilers": spoiler_results, "audit": _audit_counts(audit), "flags": flags,
            "tools": {"ffmpeg": binary, "edge_ffmpeg": ffmpeg_binary(("fps", "scale", "format"))}}
