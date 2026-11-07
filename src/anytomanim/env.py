"""Environment discovery shared by the CLI, pipeline and scenes.

No manim import here — the CLI's fast commands (tts/measure/subtitles) load
this without paying manim's ~3 s import (or its SoX warning on stdout).
"""
from __future__ import annotations

import glob
import os
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Where TeX distributions put latex/dvisvgm when they are not on PATH.
_TEX_CANDIDATES = [
    "/Library/TeX/texbin",                        # MacTeX / BasicTeX
    "~/Library/TinyTeX/bin/*",                    # TinyTeX (macOS)
    "~/.TinyTeX/bin/*",                           # TinyTeX (Linux)
    "/usr/local/texlive/*/bin/*",                 # TeX Live
    "/opt/homebrew/bin",
]


def tex_bin() -> str | None:
    """Directory holding dvisvgm (+ latex), or None."""
    found = shutil.which("dvisvgm")
    if found:
        return str(Path(found).parent)
    for pat in _TEX_CANDIDATES:
        for d in sorted(glob.glob(os.path.expanduser(pat)), reverse=True):
            if (Path(d) / "dvisvgm").exists():
                return d
    return None


def render_env() -> dict:
    """os.environ with the TeX bin dir prepended to PATH (if found)."""
    env = dict(os.environ)
    tb = tex_bin()
    if tb and tb not in env.get("PATH", "").split(os.pathsep):
        env["PATH"] = tb + os.pathsep + env.get("PATH", "")
    return env


def read_dotenv(key: str) -> str | None:
    """Value of `key` from the environment, else from the repo-root .env."""
    val = os.environ.get(key)
    if val:
        return val
    env = REPO / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.strip().startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None
