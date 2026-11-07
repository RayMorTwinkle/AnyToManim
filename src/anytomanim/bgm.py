"""Mix a music bed under a narrated video with voice ducking."""
import subprocess
from pathlib import Path


def mix(video: Path, music: Path, out: Path,
        level_db: float = -12.0, duck: bool = True) -> Path:
    """ffmpeg-sidechain ducking: narration pushes the music down, the bed
    swells back in pauses. level_db = music gain AFTER ducking makeup."""
    gain = 10 ** (level_db / 20)
    if duck:
        fc = (
            "[0:a]asplit=2[voice][side];"
            f"[1:a]volume={gain}[bed];"
            "[bed][side]sidechaincompress=threshold=0.02:ratio=6:"
            "attack=15:release=400:makeup=1[ducked];"
            "[voice][ducked]amix=inputs=2:duration=first:normalize=0"
        )
    else:
        fc = f"[1:a]volume={gain}[bed];[0:a][bed]amix=inputs=2:duration=first"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(music),
         "-filter_complex", fc, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         str(out)], check=True)
    return out
