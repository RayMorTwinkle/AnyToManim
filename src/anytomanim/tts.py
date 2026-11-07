"""MiMo-TTS client (api.xiaomimimo.com/v1, OpenAI-compatible).

Three modes:
  - preset      : model mimo-v2.5-tts,             voice=<preset id>
  - voicedesign : model mimo-v2.5-tts-voicedesign, user msg = voice-design description
  - voiceclone  : model mimo-v2.5-tts-voiceclone,  voice=data:<mime>;base64,<sample>

Style directives go in the `user` message; narration text in the `assistant` message.
Non-streaming WAV output (~24 kHz). Key: MIMO_API_KEY env or repo-root .env.

Draft mode (no key, no cost): `ANYTOMANIM_TTS=draft` makes every synthesize()
call use the local macOS `say` voice (or silence of estimated length when `say`
is unavailable) — for iterating on layout/pacing before paying for real voice.

The manim-voiceover adapter `MiMoService` lives in `anytomanim.voiceover`;
`from anytomanim.tts import MiMoService` still works (lazy import), so this
module stays manim-free and fast for the CLI.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

from .env import REPO, read_dotenv
from .files import atomic_output

BASE_URL = "https://api.xiaomimimo.com/v1"

MODELS = {
    "preset": "mimo-v2.5-tts",
    "voicedesign": "mimo-v2.5-tts-voicedesign",
    "voiceclone": "mimo-v2.5-tts-voiceclone",
}

_CJK = re.compile(r"[㐀-鿿]")


def load_key() -> str:
    key = read_dotenv("MIMO_API_KEY")
    if key:
        return key
    sys.exit("MIMO_API_KEY not found in env or .env "
             "(or set ANYTOMANIM_TTS=draft to iterate without a key)")


def draft_mode() -> bool:
    return os.environ.get("ANYTOMANIM_TTS", "").lower() == "draft"


def synthesis_inputs(text: str, *, mode: str, voice: str,
                     clone_sample=None, style: str = "") -> dict:
    """All inputs affecting synthesis; shared by beat and live caches."""
    sample = Path(clone_sample) if clone_sample else None
    clone_hash = None
    if sample is not None:
        if sample.exists():
            clone_hash = hashlib.sha256(sample.read_bytes()).hexdigest()
        elif not draft_mode():
            raise FileNotFoundError(f"voice-clone sample missing: {sample}")
    return {"input_text": text, "mode": "voiceclone" if sample else mode,
            "voice": voice, "style": style,
            "backend": "draft" if draft_mode() else "mimo",
            "model": MODELS["voiceclone" if sample else mode],
            "clone_sample": str(sample.resolve()) if sample else None,
            "clone_sha256": clone_hash}


def synthesis_fingerprint(text: str, **kwargs) -> str:
    return hashlib.sha256(json.dumps(synthesis_inputs(text, **kwargs),
                                     sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def synthesize(text: str, out_path: str | Path, *, style: str = "",
               mode: str = "preset", voice: str = "mimo_default",
               clone_sample: str | Path | None = None, timeout: int = 300) -> Path:
    """Validate a complete temporary WAV before replacing any existing audio."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with atomic_output(out, suffix=".wav") as staged:
        _synthesize(text, staged, style=style, mode=mode, voice=voice,
                    clone_sample=clone_sample, timeout=timeout)
        with wave.open(str(staged), "rb") as w:
            frames = w.getnframes()
            expected = frames * w.getnchannels() * w.getsampwidth()
            if not frames or len(w.readframes(frames)) != expected:
                raise ValueError("synthesis produced an empty or truncated WAV")
        duration = audio_duration(staged)
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("synthesis produced an invalid WAV duration")
    return out


def _synthesize(
    text: str,
    out_path: str | Path,
    *,
    style: str = "",
    mode: str = "preset",
    voice: str = "mimo_default",
    clone_sample: str | Path | None = None,
    timeout: int = 300,
) -> Path:
    """Synthesize `text` to a WAV file. Returns out_path."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if draft_mode():
        return _synthesize_draft(text, out)

    from openai import OpenAI

    if mode == "voiceclone" or clone_sample:
        model = MODELS["voiceclone"]
        sample = Path(clone_sample) if clone_sample else None
        if sample is None:
            raise ValueError("voiceclone mode requires clone_sample")
        if not sample.exists():
            sys.exit(f"voice-clone sample missing: {sample}\n"
                     "  drop a clean <=10MB clip there, or pick a preset voice "
                     "(--voice milo / baihua / moli)")
        mime = "audio/wav" if sample.suffix == ".wav" else "audio/mpeg"
        b64 = base64.b64encode(sample.read_bytes()).decode()
        audio = {"format": "wav", "voice": f"data:{mime};base64,{b64}"}
    elif mode == "voicedesign":
        model = MODELS["voicedesign"]
        audio = {"format": "wav"}
    else:
        model = MODELS["preset"]
        audio = {"format": "wav", "voice": voice}

    client = OpenAI(api_key=load_key(), base_url=BASE_URL)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": style or ""},
            {"role": "assistant", "content": text},
        ],
        audio=audio,
        timeout=timeout,
    )
    out.write_bytes(base64.b64decode(resp.choices[0].message.audio.data))
    return out


def _synthesize_draft(text: str, out: Path) -> Path:
    zh = bool(_CJK.search(text))
    if shutil.which("say"):
        voice = "Tingting" if zh else "Samantha"
        with tempfile.TemporaryDirectory() as d:
            aiff = Path(d) / "a.aiff"
            r = subprocess.run(["say", "-v", voice, "-o", str(aiff), text],
                               capture_output=True)
            if r.returncode != 0:  # voice not installed -> system default
                subprocess.run(["say", "-o", str(aiff), text], check=True)
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(aiff),
                            "-ar", "24000", "-ac", "1", str(out)], check=True)
        return out
    # no local voice: silence of plausible length (zh ~4.5 chars/s, en ~2.6 words/s)
    secs = (len(_CJK.findall(text)) / 4.5 if zh
            else len(text.split()) / 2.6) + 0.4
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\0\0" * int(secs * 24000))
    return out


def audio_duration(path: str | Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def __getattr__(name):  # lazy: keep manim out of the CLI's fast path
    if name == "MiMoService":
        from .voiceover import MiMoService
        return MiMoService
    raise AttributeError(name)
