from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path | str, data: bytes, mode: int | None = None) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    closed = False
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            closed = True

        if mode is not None:
            os.chmod(tmp_path, mode)

        os.replace(tmp_path, target)
    except BaseException:
        if not closed:
            os.close(fd)
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
