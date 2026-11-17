"""Small shared helpers: a cross-platform file lock, JSON state, and the engine log."""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from .config import DATA


@contextmanager
def locked(path: str) -> Iterator[None]:
    """An exclusive lock on <path>.lock, so the engine and a command-line call never write a file at the same time."""
    lock_path = path + ".lock"
    os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)   # journal/ and data/ don't exist on a fresh clone
    f = open(lock_path, "a+")
    try:
        try:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX)
        except ImportError:                       # Windows
            import msvcrt
            f.seek(0)
            for _ in range(100):
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
        yield
    finally:
        f.close()


def replace(tmp: str, path: str) -> None:
    """os.replace that waits out a reader. On Windows, replacing a file fails while MT5 has it open (it reads
    notify.tsv every quarter second); the read takes milliseconds, so a short retry always gets through."""
    for attempt in range(40):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 39:
                raise
            time.sleep(0.05)


def load_json(path: str, default: Any) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path: str, value: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=1, default=str)
    replace(tmp, path)


def log(msg: str) -> None:
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, "engine.log")
    try:
        if os.path.getsize(path) > 2_000_000:
            os.replace(path, path + ".old")
    except OSError:
        pass
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")
