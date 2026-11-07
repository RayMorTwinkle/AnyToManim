"""Atomic file replacement with ordinary creation permissions."""
from contextlib import contextmanager
import os
from pathlib import Path
import stat
import uuid


@contextmanager
def atomic_output(path: Path, suffix: str = ".tmp"):
    """Stage beside path, preserve its mode, and replace only on success."""
    staged = path.with_name(f".{path.name}.{uuid.uuid4().hex}{suffix}")
    # Let the kernel apply umask, without changing process-wide state in workers.
    fd = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    default_mode = stat.S_IMODE(os.fstat(fd).st_mode)
    os.close(fd)
    try:
        yield staged
        try:
            mode = stat.S_IMODE(path.stat().st_mode)
        except FileNotFoundError:
            mode = default_mode
        staged.chmod(mode)
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)
