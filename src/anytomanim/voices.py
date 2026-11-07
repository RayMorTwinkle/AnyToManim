"""Voice preset registry — named, switchable narration voices.

A preset = {mode, voice, clone_sample, style, languages}. Users can add their own
entries using their own samples (clone your own voice by pointing clone_sample at a clean audio file, or
design one with mode='voicedesign' + style prompt). Resolved by CLI --voice or
beats.json 'voice' field.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO / "voices.json"

BUILTIN = {
    "baihua": {
        "mode": "preset",
        "voice": "白桦",
        "clone_sample": None,
        "style": "清晰沉稳的科普解说，语速适中，温和有好奇心",
        "languages": ["zh"],
        "note": "MiMo preset — clear steady zh science narration",
    },
    "moli": {
        "mode": "preset",
        "voice": "茉莉",
        "clone_sample": None,
        "style": "轻快的科普解说，亲切自然",
        "languages": ["zh"],
        "note": "MiMo preset — lighter zh voice",
    },
    "milo": {
        "mode": "preset",
        "voice": "Milo",
        "clone_sample": None,
        "style": "Warm, articulate explainer. Engaged but unhurried.",
        "languages": ["en"],
        "note": "MiMo preset — English male, non-clone fallback",
    },
}


def load_registry() -> dict:
    reg = dict(BUILTIN)
    if REGISTRY_PATH.exists():
        reg.update({k: v for k, v in json.loads(REGISTRY_PATH.read_text()).items()
                    if not k.startswith("_") and isinstance(v, dict)})
    return reg


def default_for(language: str = "en") -> str:
    """Use built-in, non-cloned narration by language."""
    return "baihua" if language == "zh" else "milo"


def missing_samples() -> list[str]:
    """Preset names whose voice-clone sample file does not exist."""
    return [n for n, p in load_registry().items()
            if not n.startswith("example") and p.get("mode") == "voiceclone" and p.get("clone_sample")
            and not (REPO / p["clone_sample"]).exists()]


def resolve(name_or_preset: str | dict) -> dict:
    """'baihua' | explicit dict -> full preset with absolute clone path."""
    if isinstance(name_or_preset, dict):
        preset = name_or_preset
    else:
        reg = load_registry()
        if name_or_preset not in reg:
            raise KeyError(
                f"unknown voice '{name_or_preset}'. Have: {sorted(reg)}. "
                f"Add entries to {REGISTRY_PATH}")
        preset = reg[name_or_preset]
    preset = dict(preset)
    if preset.get("clone_sample"):
        preset["clone_sample"] = str(REPO / preset["clone_sample"])
    return preset
