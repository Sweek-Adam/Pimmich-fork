"""Verrou entre processus (interface et diaporama) sur un fichier : fcntl (Linux, Mac) ou msvcrt (Windows)."""
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
    import msvcrt


@contextmanager
def locked(path):
    path = Path(path)
    path.touch(exist_ok=True)
    with open(path, "r+") as handle:
        if fcntl:
            fcntl.flock(handle, fcntl.LOCK_EX)
        else:
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield handle
        finally:
            if fcntl:
                fcntl.flock(handle, fcntl.LOCK_UN)
            else:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
