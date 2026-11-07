"""Shared beat synthesis, resumable checkpoints and manifest writes."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
import fcntl
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

from . import tts
from .files import atomic_output


def validate_ids(beats: list[dict]) -> None:
    seen = set()
    for b in beats:
        bid = b.get("id")
        if not isinstance(bid, str) or not re.fullmatch(r"b[0-9]{2,}", bid):
            raise ValueError(f"invalid beat id {bid!r}: expected b[0-9]{{2,}}")
        if bid in seen:
            raise ValueError(f"duplicate beat id: {bid}")
        seen.add(bid)


@contextmanager
def manifest_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Lock a stable sibling: replacing the manifest changes its inode.
    with path.with_suffix(path.suffix + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def write_manifest(path: Path, doc: dict) -> None:
    """Atomic replacement; caller holds manifest_lock for read/modify/write."""
    with atomic_output(path) as staged:
        with staged.open("w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())


def synthesize_beats(doc: dict | None, manifest: Path, audio_dir: Path, *,
                     mode: str, voice: str, clone_sample: str | None, style: str,
                     force: bool = False, jobs: int = 4) -> tuple[dict, int]:
    """Resume by synthesis identity, checkpoint successes even on partial failure.

    doc=None edits the on-disk manifest; a supplied new script inherits only
    matching audio metadata from the previous script in this workdir.
    """
    manifest, audio_dir = Path(manifest).resolve(), Path(audio_dir).resolve()
    if jobs < 1:
        raise ValueError("jobs must be positive")
    with manifest_lock(manifest):
        previous = json.loads(manifest.read_text()) if manifest.exists() else {}
        if doc is None:
            doc = previous
        validate_ids(doc["beats"])
        old = {b["id"]: b for b in previous.get("beats", [])}
        tag = "draft" if tts.draft_mode() else f"{mode}:{voice}"
        todo, failures, made = [], {}, 0
        for b in doc["beats"]:
            wav = audio_dir / f"{b['id']}.wav"
            fingerprint = tts.synthesis_fingerprint(
                b["narration"], mode=mode, voice=voice,
                clone_sample=clone_sample, style=style)
            saved = old.get(b["id"], b)
            saved_path = Path(saved.get("audio_file") or "")
            if not saved_path.is_absolute():
                saved_path = manifest.parent / saved_path
            same = (not force and saved.get("audio_fingerprint") == fingerprint
                    and saved_path.resolve() == wav and wav.exists())
            if same:
                try:
                    dur = tts.audio_duration(wav)
                    same = math.isfinite(dur) and dur > 0 and abs(
                        dur - saved.get("audio_seconds", 0)) <= 0.002
                except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError):
                    same = False
            if same:
                b.update({k: v for k, v in saved.items() if k.startswith("audio_")})
            else:
                todo.append((b, wav, fingerprint))

        def work(b, wav):
            tts.synthesize(b["narration"], wav, mode=mode, voice=voice,
                           clone_sample=clone_sample, style=style)
            return round(tts.audio_duration(wav), 3)

        with ThreadPoolExecutor(max_workers=jobs) as ex:
            futures = {ex.submit(work, b, wav): (b, wav, fp) for b, wav, fp in todo}
            for future in as_completed(futures):
                b, wav, fp = futures[future]
                try:
                    dur = future.result()
                except (Exception, SystemExit) as exc:
                    failures[b["id"]] = str(exc)
                    continue
                b.update(audio_file=str(wav.relative_to(manifest.parent))
                         if wav.is_relative_to(manifest.parent) else str(wav),
                         audio_seconds=dur, audio_narration=b["narration"],
                         audio_voice=tag, audio_fingerprint=fp)
                made += 1
                write_manifest(manifest, doc)
                print(f"synthesized {b['id']}", file=sys.stderr, flush=True)
        write_manifest(manifest, doc)
        if failures:
            raise RuntimeError("TTS failed for " + "; ".join(
                f"{bid}: {error}" for bid, error in sorted(failures.items())))
        return doc, made
