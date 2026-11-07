"""manim-voiceover integration: MiMoService + NarratedScene.

MiMoService — a manim-voiceover SpeechService backed by MiMo-TTS that first
looks for PRE-RECORDED beat audio. Give it `beats_file=` and every
`self.voiceover(text=<a beat's narration>)` reuses that beat's `audio_file`
(written by `anytomanim tts --beats`) instead of synthesizing again. This is
what makes the measured `audio_seconds` in beats.json the exact audio that
ends up in the video (MiMo is not deterministic — a second synthesis of the
same text has a different length).

NarratedScene — VoiceoverScene plus:
  * `with self.voiceover(beat="b03") as tr:` pulls the narration from beats.json
  * a per-beat audit written next to the mp4 (`<Scene>.audit.json`): beat
    times, what is on screen when each beat ends (and since which beat),
    overlapping text, off-frame mobjects, too-small text, animation overrun
    past the narration, and static (frozen) time. `anytomanim preview` reads it.
  * CJK-aware subcaption chunking (manim-voiceover splits on spaces only, so a
    Chinese beat would become one giant caption).
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
from contextlib import contextmanager
from pathlib import Path

logging.getLogger("sox").setLevel(logging.ERROR)  # pysox nags about a missing binary we never use

from manim import (DEFAULT_WAIT_TIME, DecimalNumber, Integer, MathTex, MovingCameraScene,  # noqa: E402
                   SingleStringMathTex, Tex, Text, ValueTracker, config, logger)
from manim_voiceover import VoiceoverScene  # noqa: E402
from manim_voiceover.helper import remove_bookmarks  # noqa: E402
from manim_voiceover.services.base import SpeechService, initialize_speech_service  # noqa: E402

from .tts import synthesize, synthesis_inputs  # noqa: E402

_CJK = re.compile(r"[㐀-鿿　-〿＀-￯]")
_TEXT_TYPES = (Text, MathTex, SingleStringMathTex, Tex, DecimalNumber, Integer)


def _norm(text: str) -> str:
    """Whitespace-insensitive key for matching narration strings."""
    return re.sub(r"\s+", "", remove_bookmarks(text or ""))


class MiMoService(SpeechService):
    """MiMo-TTS as a manim-voiceover speech service.

    Args:
        mode: 'preset' | 'voicedesign' | 'voiceclone'
        voice: preset voice id (preset mode)
        clone_sample: reference audio path (voiceclone mode)
        design: voice-design description (voicedesign mode)
        style: default style directive; per-call `self.voiceover(style=...)`
               overrides for that beat.
        beats_file: beats.json whose `audio_file`s are reused verbatim when a
               voiceover's text matches a beat's narration.
    """

    def __init__(self, mode: str = "preset", voice: str = "mimo_default",
                 clone_sample: str | Path | None = None,
                 design: str | None = None, style: str = "",
                 beats_file: str | Path | None = None,
                 **kwargs: object) -> None:
        initialize_speech_service(self, kwargs)
        self.mode = mode
        self.voice = voice
        self.clone_sample = clone_sample
        self.design = design
        self.style = style
        self.beats: dict[str, dict] = {}        # id -> beat
        self._by_text: dict[str, list[str]] = {}  # normalized narration -> ids
        self._audio: dict[str, Path] = {}       # id -> absolute audio path
        if beats_file:
            self.load_beats(beats_file)

    # ---------------------------------------------------------- beats.json
    def load_beats(self, beats_file: str | Path) -> dict[str, dict]:
        path = Path(beats_file).resolve()
        doc = json.loads(path.read_text())
        from .beats import validate_ids
        validate_ids(doc["beats"])
        self.beats.clear()
        self._by_text.clear()
        self._audio.clear()
        for b in doc["beats"]:
            self.beats[b["id"]] = b
            self._by_text.setdefault(_norm(b["narration"]), []).append(b["id"])
            if b.get("audio_file"):
                p = Path(b["audio_file"])
                p = p if p.is_absolute() else path.parent / p
                if p.exists():
                    self._audio[b["id"]] = p
        return self.beats

    def beat_id_for(self, text: str) -> str | None:
        ids = self._by_text.get(_norm(text), [])
        if len(ids) > 1:
            raise ValueError(f"ambiguous narration matches {', '.join(ids)}; use beat= explicitly")
        return ids[0] if ids else None

    # ---------------------------------------------------------- synthesis
    def generate_from_text(self, text: str, cache_dir=None, path=None,
                           **kwargs: object):
        cache_dir = Path(cache_dir or self.cache_dir)
        input_text = remove_bookmarks(text)

        audio_file = kwargs.get("audio_file")
        bid = kwargs.get("beat_id")
        if bid is not None and bid not in self.beats:
            raise KeyError(f"beat {bid!r} not in beats_file")
        if audio_file is None:
            bid = bid or self.beat_id_for(text)
            audio_file = self._audio.get(bid)
        if audio_file is not None:
            return self._prerecorded(input_text, Path(audio_file), cache_dir)
        if self.beats:
            logger.warning(
                "voiceover text matches no beat with audio in beats_file — "
                "synthesizing live (its length will differ from beats.json): "
                f"{input_text[:40]!r}")

        style = kwargs.get("style", self.style)
        mode = "voicedesign" if self.design else self.mode
        if self.design:
            style = "\n".join(filter(None, [self.design, style]))
        input_data = synthesis_inputs(input_text, mode=mode, voice=self.voice,
                                      clone_sample=self.clone_sample, style=style)
        input_data["service"] = "mimo"
        cached = self.get_cached_result(input_data, cache_dir)
        if cached is not None:
            return cached
        audio_path = (str(path) if path is not None
                      else self.get_audio_basename(input_data) + ".wav")
        synthesize(input_text, cache_dir / audio_path, style=style, mode=mode,
                   voice=self.voice, clone_sample=self.clone_sample)
        return {"input_data": input_data, "original_audio": audio_path}

    def _prerecorded(self, input_text: str, src: Path, cache_dir: Path):
        if not src.exists():
            raise FileNotFoundError(f"voiceover audio_file not found: {src}")
        st = src.stat()
        digest = hashlib.sha256(
            f"{src.resolve()}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:10]
        name = f"pre-{src.stem}-{digest}{src.suffix}"
        dst = cache_dir / name
        if not dst.exists():
            cache_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        return {"input_data": {"input_text": input_text, "service": "prerecorded",
                               "audio_file": str(src.resolve())},
                "original_audio": name}


# ====================================================================== scene
class NarratedScene(VoiceoverScene, MovingCameraScene):
    """Moving camera + beat lookup + per-beat audit + CJK subcaptions.

    ``self.camera.frame`` is available by default. The older spelling still works:
        class MyScene(NarratedScene, MovingCameraScene): ...
    """

    small_font = 24          # effective font_size below this is flagged
    static_flag = 0.30       # frozen fraction of a beat above this is flagged

    def setup(self):
        super().setup()
        self._audit: list[dict] = []
        self._first_seen: dict[int, str] = {}
        self._cur_beat: str | None = None
        self._static = 0.0

    # ---------------------------------------------------------- voiceover
    @contextmanager
    def voiceover(self, text: str | None = None, ssml: str | None = None,
                  *, beat: str | None = None, **kwargs):
        svc = getattr(self, "speech_service", None)
        beats = getattr(svc, "beats", {}) or {}
        if text is None and ssml is None:
            if beat is None:
                raise ValueError("voiceover() needs text= or beat=")
            if beat not in beats:
                raise KeyError(f"beat {beat!r} not in beats_file "
                               f"(have: {', '.join(beats) or 'none — pass beats_file= to MiMoService'})")
            text = beats[beat]["narration"]
        bid = beat or (svc.beat_id_for(text) if hasattr(svc, "beat_id_for") and text else None) \
            or f"v{len(self._audit) + 1:02d}"

        if beat is not None:
            kwargs["beat_id"] = beat

        t0 = self.renderer.time
        self._cur_beat, self._static = bid, 0.0
        dur, error = None, None
        try:
            with super().voiceover(text=text, ssml=ssml, **kwargs) as tr:
                dur = tr.duration
                yield tr
        except BaseException as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self._cur_beat = None
            self._record(bid, t0, self.renderer.time, dur or 0.0)
            if error is not None:
                self._audit[-1].update(status="failed", error=error)
                self._flush_audit(partial=True, error=error)

    def wait(self, duration: float = DEFAULT_WAIT_TIME, stop_condition=None,
             frozen_frame: bool | None = None):
        if self._cur_beat and duration > 0:
            # same test manim uses to decide a Wait is a frozen frame
            alive = frozen_frame is False or (frozen_frame is None and bool(
                self.always_update_mobjects or self.updaters or stop_condition
                or any(m.has_time_based_updater()
                       for m in self.get_mobject_family_members())))
            if not alive:
                self._static += duration
        super().wait(duration, stop_condition=stop_condition,
                     frozen_frame=frozen_frame)

    # ---------------------------------------------------------- subcaptions
    def add_wrapped_subcaption(self, subcaption: str, duration: float,
                               subcaption_buff: float = 0.1,
                               max_subcaption_len: int = 70) -> None:
        if not _CJK.search(subcaption or ""):
            return super().add_wrapped_subcaption(
                subcaption, duration, subcaption_buff=subcaption_buff,
                max_subcaption_len=max_subcaption_len)
        chunks = split_cjk(subcaption, max_len=22)
        total = sum(len(c) for c in chunks) or 1
        offset = 0.0
        for c in chunks:
            d = duration * len(c) / total
            self.add_subcaption(c, duration=max(d - subcaption_buff, 0),
                                offset=offset)
            offset += d

    # ---------------------------------------------------------- audit
    def _frame_box(self):
        frame = getattr(self.camera, "frame", None)
        if frame is not None:
            c, w, h = frame.get_center(), frame.width, frame.height
        else:
            c, w, h = (0, 0, 0), config.frame_width, config.frame_height
        return (c[0] - w / 2, c[0] + w / 2, c[1] - h / 2, c[1] + h / 2), w

    def _record(self, bid: str, t0: float, t1: float, dur: float) -> None:
        (fx0, fx1, fy0, fy1), fw = self._frame_box()
        zoom = config.frame_width / fw
        items, texts, issues = [], [], []
        for m in self.mobjects:
            # Camera animations add the control frame to mobjects; it is not ink.
            if m is getattr(self.camera, "frame", None):
                continue
            if isinstance(m, ValueTracker) or not any(
                    s.has_points() for s in m.get_family()):
                continue
            first = self._first_seen.setdefault(id(m), bid)
            visible = _max_opacity(m) > 0.05
            box = _box(m)
            items.append({"label": _describe(m), "since": first,
                          "visible": visible,
                          "box": [round(v, 2) for v in box]})
            if not visible:
                continue
            if (box[0] < fx0 - 0.1 or box[1] > fx1 + 0.1
                    or box[2] < fy0 - 0.1 or box[3] > fy1 + 0.1):
                issues.append(f"off-frame: {_describe(m)}")
            for leaf in _text_leaves(m):
                if _max_opacity(leaf) < 0.3:
                    continue
                texts.append((id(m), leaf))
                fs = _font_size(leaf)
                if fs is not None and fs * zoom < self.small_font - 0.5:
                    issues.append(f"small text ({fs * zoom:.0f}): {_describe(leaf)}")
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                (pa, a), (pb, b) = texts[i], texts[j]
                if pa != pb and _overlap(_box(a), _box(b)) > 0.15:
                    issues.append(f"overlap: {_describe(a)} × {_describe(b)}")
        span = t1 - t0
        if dur and span > dur + 1.0 / config.frame_rate + 0.01:  # > one frame late
            issues.append(f"overrun: visuals run {span - dur:.2f}s past the narration")
        static_frac = self._static / span if span > 0 else 0.0
        if static_frac > self.static_flag:
            issues.append(f"static {static_frac:.0%} of the beat (nothing moves)")
        self._audit.append({
            "beat": bid, "start": round(t0, 3), "end": round(t1, 3),
            "audio_seconds": round(dur, 3), "static_fraction": round(static_frac, 2),
            "on_screen": items, "issues": sorted(set(issues), key=issues.index)})

    def render(self, *args, **kwargs):
        try:
            return super().render(*args, **kwargs)
        except BaseException as exc:
            self._flush_audit(partial=True, error=f"{type(exc).__name__}: {exc}")
            raise

    def tear_down(self):
        super().tear_down()
        self._flush_audit()

    def _flush_audit(self, partial: bool = False, error: str | None = None):
        try:
            out = Path(self.renderer.file_writer.movie_file_path)
        except AttributeError:
            return
        audit = getattr(self, "_audit", [])
        if (audit or partial) and not config.dry_run:
            from .beats import write_manifest
            out.parent.mkdir(parents=True, exist_ok=True)
            data = {"scene": type(self).__name__, "beats": audit}
            if partial:
                data.update(partial=True, error=error)
            suffix = ".partial.audit.json" if partial else ".audit.json"
            write_manifest(out.with_suffix(suffix), data)
            if not partial:
                out.with_suffix(".partial.audit.json").unlink(missing_ok=True)


# ====================================================================== helpers
def split_cjk(text: str, max_len: int = 22) -> list[str]:
    """Split CJK text into caption-sized chunks at punctuation."""
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.findall(r"[^。！？；，、,.!?;]+[。！？；，、,.!?;]*", text) or [text]
    chunks, cur = [], ""
    for p in parts:
        if cur and len(cur) + len(p) > max_len:
            chunks.append(cur)
            cur = ""
        while len(p) > max_len:
            chunks.append(p[:max_len])
            p = p[max_len:]
        cur += p
    if cur:
        chunks.append(cur)
    return chunks


def _box(m):
    return (m.get_left()[0], m.get_right()[0], m.get_bottom()[1], m.get_top()[1])


def _overlap(a, b) -> float:
    """Intersection area / smaller box area."""
    w = min(a[1], b[1]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[2], b[2])
    if w <= 0 or h <= 0:
        return 0.0
    small = min((a[1] - a[0]) * (a[3] - a[2]), (b[1] - b[0]) * (b[3] - b[2]))
    return w * h / small if small > 1e-6 else 0.0


def _max_opacity(m) -> float:
    best = 0.0
    for s in m.get_family():
        if not s.has_points():
            continue
        try:
            best = max(best, float(s.get_fill_opacity()), float(s.get_stroke_opacity()))
        except Exception:  # noqa: BLE001 — non-VMobject leaf (e.g. ImageMobject)
            best = max(best, 1.0)
    return best


def _text_leaves(m):
    """Outermost text-like mobjects inside m (a MathTex counts once)."""
    if isinstance(m, _TEXT_TYPES):
        return [m]
    out = []
    for s in m.submobjects:
        out.extend(_text_leaves(s))
    return out


def _font_size(m):
    try:
        return float(m.font_size)
    except Exception:  # noqa: BLE001
        return None


def _describe(m) -> str:
    if m.updaters:  # always_redraw & co: stored text is stale, value is live
        return f"{type(m).__name__}[live] @({m.get_x():.1f},{m.get_y():.1f})"
    for s in m.get_family():
        if isinstance(s, (Text,)) and getattr(s, "text", None):
            return f"{type(m).__name__}({s.text[:28]!r})"
        if isinstance(s, (MathTex, SingleStringMathTex, Tex)):
            tex = getattr(s, "tex_string", "") or ""
            return f"{type(m).__name__}(${tex[:28]}$)"
        if isinstance(s, (DecimalNumber, Integer)):
            return f"{type(m).__name__}({s.get_value():g})"
    w, h = m.width, m.height
    return f"{type(m).__name__}[{len(m.get_family())}] {w:.1f}×{h:.1f} @({m.get_x():.1f},{m.get_y():.1f})"
