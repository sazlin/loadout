import os
import stat
from pathlib import Path

from loadout.io import atomic_write, sha256_bytes


def test_sha256_bytes_is_deterministic() -> None:
    data = b"hello, loadout"
    assert sha256_bytes(data) == sha256_bytes(data)
    assert sha256_bytes(data) == "56ec9b3d0b821f658d55b3e169d4509d9bb5b9ad2684474a541c0127fa3b92aa"


def test_atomic_write_creates_file_with_content(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "output.txt"
    atomic_write(target, b"synced content\n")

    assert target.read_bytes() == b"synced content\n"


def test_atomic_write_sets_mode_when_provided(tmp_path: Path) -> None:
    target = tmp_path / "scripts" / "run.sh"
    atomic_write(target, b"#!/bin/sh\n", mode=0o755)

    mode = stat.S_IMODE(os.stat(target).st_mode)
    assert mode == 0o755
