"""Subtitle generation — per-language + bilingual .srt from beats.json.

Timing source priority:
  1. `<Scene>.audit.json` written by NarratedScene during render (exact beat
     start/end, by beat id)
  2. the .srt manim-voiceover writes during render — its cues are grouped into
     beats by matching their TEXT against each beat's narration
  3. cumulative `audio_seconds` + a fixed inter-beat gap (estimate; warns)

Long beat lines are split at sentence punctuation into several cues whose
times are proportional to their length.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

SRT_BLOCK = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})[^\n]*\n"
    r"(.*?)(?:\n\s*\n|\Z)", re.S)
_CJK = re.compile(r"[㐀-鿿]")
_BOOKMARK = re.compile(r"<bookmark[^>]*>")
MAX_CHARS = {"cjk": 22, "latin": 84}
DEFAULT_FONTSIZE = 14
# Explicit 16:9 ASS canvas: 14 units become 35px at 720p / 52.5px at 1080p.
BURN_RES_X, BURN_RES_Y = 512, 288
BURN_MARGIN = 24


def _wrap_width(text: str, fontsize: int = DEFAULT_FONTSIZE) -> list[str]:
    """Conservative em budget, including outline and font-metric headroom.

    libass also wraps at these margins. Pre-splitting handles unbroken strings;
    generation turns these lines into separate cues so bilingual stays two lines.
    """
    budget = (BURN_RES_X - 2 * BURN_MARGIN - 4) / (fontsize * 1.15)
    lines = []
    while text:
        width, cut = 0.0, 0
        for ch in text:
            units = (1.0 if unicodedata.east_asian_width(ch) in ("W", "F")
                     or ch.isupper() or ch in "mw@%" else 0.7)
            if width + units > budget and cut:
                break
            width += units
            cut += 1
        if cut < len(text):
            space = text.rfind(" ", 0, cut + 1)
            if space > 0:
                cut = space
        lines.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    return lines or [""]


def _ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", _BOOKMARK.sub("", text or ""))


def _parse_ref_srt(path: Path) -> list[tuple[float, float, str]]:
    cues = []
    for m in SRT_BLOCK.finditer(path.read_text()):
        h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, m.groups()[:8])
        cues.append((h1 * 3600 + m1 * 60 + s1 + ms1 / 1000,
                     h2 * 3600 + m2 * 60 + s2 + ms2 / 1000, m.group(9).strip()))
    return cues


def _from_audit(beats, audit: Path):
    data = json.loads(audit.read_text())
    by_id = {b["beat"]: (b["start"], b["start"] + b["audio_seconds"])
             for b in data["beats"]}
    if all(b["id"] in by_id for b in beats):
        return [by_id[b["id"]] for b in beats]
    return None


def _from_ref_srt(beats, ref_srt: Path):
    cues, i, out = _parse_ref_srt(ref_srt), 0, []
    for b in beats:
        need, acc, start = _norm(b["narration"]), "", None
        while i < len(cues) and len(acc) < len(need):
            if start is None:
                start = cues[i][0]
            acc += _norm(cues[i][2])
            end = cues[i][1]
            i += 1
        if start is None or acc != need:
            return None
        out.append((start, end))
    return out


def beat_timings(beats: list[dict], ref_srt: Path | None = None,
                 gap: float = 0.7, audit: Path | None = None
                 ) -> tuple[list[tuple[float, float]], str]:
    """((start, end) per beat, source name)."""
    if audit and audit.exists():
        t = _from_audit(beats, audit)
        if t:
            return t, "audit"
        print(f"warning: {audit.name} lacks some beat ids — trying other timing sources",
              file=sys.stderr)
    if ref_srt and ref_srt.exists():
        t = _from_ref_srt(beats, ref_srt)
        if t:
            return t, "ref-srt"
        print(f"warning: {ref_srt.name} cues do not match beats.json narration "
              "(was the scene rendered from this beats.json?) — falling back to "
              "ESTIMATED timing, subtitles may drift", file=sys.stderr)
    else:
        print("warning: no --audit/--ref-srt — subtitle timing is ESTIMATED from "
              "audio_seconds + gap and will drift", file=sys.stderr)
    out, t = [], 0.0
    for b in beats:
        dur = float(b.get("audio_seconds") or b.get("est_seconds") or 8)
        out.append((t, t + dur))
        t += dur + gap
    return out, "estimate"


def split_line(text: str) -> list[str]:
    """Split one beat's subtitle into cue-sized pieces at punctuation."""
    cjk = bool(_CJK.search(text))
    limit = MAX_CHARS["cjk" if cjk else "latin"]
    if len(text) <= limit:
        return _wrap_width(text)
    pat = r"[^。！？；，,.!?;]+[。！？；，,.!?;]*\s*" if cjk else r"[^.!?;,]+[.!?;,]*\s*"
    parts = [p.strip() for p in re.findall(pat, text)] or [text]
    chunks, cur = [], ""
    for p in parts:
        sep = "" if cjk or not cur else " "
        if cur and len(cur) + len(sep) + len(p) > limit:
            chunks.append(cur)
            cur, sep = "", ""
        while len(p) > limit:
            if cur:
                chunks.append(cur)
                cur, sep = "", ""
            cut = limit if cjk else p.rfind(" ", 0, limit + 1)
            if cut <= 0:
                cut = limit
            chunks.append(p[:cut])
            p = p[cut:].lstrip()
        cur += sep + p
    if cur:
        chunks.append(cur)
    return [line for chunk in chunks for line in _wrap_width(chunk)]


def _fit(pieces: list[str], count: int) -> list[str]:
    """Halve the longest piece until there are `count`, so paired languages line up."""
    pieces = list(pieces)
    while len(pieces) < count:
        i = max(range(len(pieces)), key=lambda k: len(pieces[k]))
        mid = len(pieces[i]) // 2
        cut = pieces[i].rfind(" ", 0, mid + 1)
        cut = cut if cut > 0 else mid
        pieces[i:i + 1] = [pieces[i][:cut].rstrip(), pieces[i][cut:].lstrip()]
    return pieces


def _spread(start: float, end: float, pieces: list[str]) -> list[tuple[float, float]]:
    total = sum(len(p) for p in pieces) or 1
    out, t = [], start
    for p in pieces:
        d = (end - start) * len(p) / total
        out.append((t, t + d))
        t += d
    return out


def _write_srt(cues: list[tuple[float, float, str]], out: Path) -> Path:
    body = [f"{i}\n{_ts(a)} --> {_ts(b)}\n{text}\n"
            for i, (a, b, text) in enumerate(cues, 1)]
    out.write_text("\n".join(body))
    return out


def generate(beats_file: Path, out_dir: Path, ref_srt: Path | None = None,
             gap: float = 0.7, audit: Path | None = None) -> list[Path]:
    """-> [beats.en.srt, beats.zh.srt, beats.bilingual.srt] (langs present only)."""
    doc = json.loads(Path(beats_file).read_text())
    beats = doc["beats"]
    times, source = beat_timings(beats, ref_srt, gap, audit)
    ordered = sorted(zip(times, beats), key=lambda item: item[0][0])
    times = [t for t, b in ordered]
    beats = [b for t, b in ordered]
    # frame quantization can make a beat's audio end a hair after the next
    # beat starts — never let cues overlap
    times = [(a, min(b, times[i + 1][0]) if i + 1 < len(times) else b)
             for i, (a, b) in enumerate(times)]
    print(f"subtitle timing: {source}", file=sys.stderr)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(beats_file).stem
    made: list[Path] = []

    langs = sorted({k for b in beats for k in (b.get("subtitle") or {})})
    if not langs:
        langs = [doc.get("language", "en")]
    text_of = {lang: [((b.get("subtitle") or {}).get(lang)
                      or (b["narration"] if lang == doc.get("language") else ""))
                     for b in beats] for lang in langs}

    for lang, lines in text_of.items():
        if not any(lines):
            continue
        cues = []
        for (a, b), line in zip(times, lines):
            pieces = split_line(line) if line else []
            cues += [(s, e, p) for (s, e), p in zip(_spread(a, b, pieces), pieces)]
        made.append(_write_srt(cues, out_dir / f"{stem}.{lang}.srt"))
    if len(langs) >= 2:
        cues = []
        for i, (a, b) in enumerate(times):
            per = [split_line(text_of[l][i]) for l in langs if text_of[l][i]]
            count = max(map(len, per), default=0)
            per = [_fit(p, count) for p in per]
            pieces = ["\n".join(group) for group in zip(*per)]
            spans = _spread(a, b, per[0] if per else [])
            cues += [(s, e, p) for (s, e), p in zip(spans, pieces)]
        made.append(_write_srt(cues, out_dir / f"{stem}.bilingual.srt"))
    return made


def _ffmpeg_with_libass() -> str:
    """An ffmpeg binary that has the `subtitles` filter (libass)."""
    import shutil
    import subprocess
    candidates = []
    try:
        import imageio_ffmpeg
        candidates.append(imageio_ffmpeg.get_ffmpeg_exe())
    except ImportError:
        pass
    if shutil.which("ffmpeg"):
        candidates.append(shutil.which("ffmpeg"))
    for ff in candidates:
        r = subprocess.run([ff, "-hide_banner", "-filters"], capture_output=True, text=True)
        if re.search(r"\ssubtitles\s", r.stdout):
            return ff
    sys.exit("no ffmpeg with libass (subtitles filter) found — "
             "`pip install imageio-ffmpeg` (bundled build has libass)")


def burn(video: Path, srt: Path, out: Path,
         fontsize: int = DEFAULT_FONTSIZE,
         fontname: str = "Hiragino Sans GB") -> Path:
    """Hard-burn an .srt into the video (bilingual srt = stacked lines).
    fontname must cover CJK for zh/bilingual srt (macOS default: Hiragino)."""
    import subprocess
    if fontsize <= 0:
        raise ValueError("fontsize must be positive")
    style = (f"FontName={fontname},FontSize={fontsize},PlayResX={BURN_RES_X},PlayResY={BURN_RES_Y},"
             f"MarginL={BURN_MARGIN},MarginR={BURN_MARGIN},MarginV=8,"
             "OutlineColour=&H80000000,BorderStyle=1,Outline=1,Shadow=0")
    import tempfile
    # A plain relative filter filename avoids both ffmpeg escaping layers,
    # even when the source path or the temporary directory has punctuation.
    video, srt, target = Path(video).resolve(), Path(srt).resolve(), Path(out).resolve()
    with tempfile.TemporaryDirectory() as d:
        cues = [(a, b, "\n".join(part for line in text.splitlines()
                                for part in _wrap_width(line, fontsize)))
                for a, b, text in _parse_ref_srt(srt)]
        _write_srt(cues, Path(d) / "captions.srt")
        vf = f"subtitles=captions.srt:force_style='{style}'"
        subprocess.run(
            [_ffmpeg_with_libass(), "-y", "-v", "error", "-i", str(video),
             "-vf", vf, "-c:a", "copy", str(target)], check=True, cwd=d)
    return out


def mux(video: Path, srts: list[Path], out: Path) -> Path:
    """Mux .srt files as selectable mov_text subtitle tracks into an mp4."""
    import subprocess
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(video)]
    for s in srts:
        cmd += ["-i", str(s)]
    cmd += ["-map", "0:v", "-map", "0:a"]
    for i, s in enumerate(srts):
        cmd += ["-map", str(i + 1)]
    cmd += ["-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text"]
    for i, s in enumerate(srts):
        lang = s.suffixes[-2][1:] if len(s.suffixes) >= 2 else "und"
        lang = {"bilingual": "zho+eng"}.get(lang, {"zh": "zho", "en": "eng"}.get(lang, lang))
        cmd += [f"-metadata:s:s:{i}", f"language={lang}",
                f"-metadata:s:s:{i}", f"title={s.stem.split('.')[-1]}"]
    cmd += [str(out)]
    subprocess.run(cmd, check=True)
    return out
