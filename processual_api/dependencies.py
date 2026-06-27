from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

from processual_kernel import CGTBridge, ProcessualMaestroKernel
from processual_kernel.security.keyring import KeyRing

from .auth.security import get_current_user

if sys.platform == "win32":
    import msvcrt

    def _lock_fd(fd: int):
        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)

    def _unlock_fd(fd: int):
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock_fd(fd: int):
        fcntl.flock(fd, fcntl.LOCK_EX)

    def _unlock_fd(fd: int):
        fcntl.flock(fd, fcntl.LOCK_UN)


@contextmanager
def file_lock(path: Path):
    """Cross-platform exclusive file lock via a sidecar .lock file."""
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    f = open(lock_path, "w")
    _lock_fd(f.fileno())
    try:
        yield
    finally:
        _unlock_fd(f.fileno())
        f.close()
        try:
            lock_path.unlink()
        except OSError:
            pass

_kernel: ProcessualMaestroKernel | None = None
_bridge: CGTBridge | None = None
_keyring: KeyRing | None = None


def get_kernel() -> ProcessualMaestroKernel:
    global _kernel
    if _kernel is None:
        _kernel = ProcessualMaestroKernel()
    return _kernel


def get_bridge() -> CGTBridge:
    global _bridge
    if _bridge is None:
        _bridge = CGTBridge()
    return _bridge


def get_keyring() -> KeyRing:
    global _keyring
    if _keyring is None:
        _keyring = KeyRing()
        try:
            _keyring.load_from_env()
        except ValueError:
            pass
    return _keyring


__all__ = ["get_kernel", "get_bridge", "get_keyring", "get_current_user", "file_lock"]
