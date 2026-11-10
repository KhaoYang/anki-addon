from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from typing import TypeVar

T = TypeVar("T")


def process_batch(items: Iterable[T], create: Callable[[T], object], cancel: threading.Event,
                  progress: Callable[[int, int], None], delay: float = 0) -> tuple[int, int]:
    done = failures = 0
    for item in items:
        if cancel.is_set():
            break
        try:
            create(item)
        except Exception:
            failures += 1
        done += 1
        progress(done, failures)
        if delay > 0 and cancel.wait(delay):
            break
    return done, failures
