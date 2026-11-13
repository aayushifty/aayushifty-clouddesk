"""
Tiny thread-safe TTL cache for expensive scans.

The dashboard polls every few seconds; walking D:\\CloudDesk or the streamed
Google Drive that often keeps the disk, network and DriveFS busy on an 8 GB machine.
Wrap such functions with @ttl_cache(seconds) and pass refresh=True to force a rescan.
"""
from __future__ import annotations

import functools
import threading
import time
from typing import Any, Callable, Dict, Tuple


def ttl_cache(seconds: float) -> Callable:
    def decorator(fn: Callable) -> Callable:
        lock = threading.Lock()
        store: Dict[Tuple, Tuple[float, Any]] = {}

        @functools.wraps(fn)
        def wrapper(*args, refresh: bool = False, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.monotonic()
            with lock:
                hit = store.get(key)
                if hit and not refresh and now - hit[0] < seconds:
                    return hit[1]
            value = fn(*args, **kwargs)  # computed outside the lock: never blocks readers of other keys
            with lock:
                store[key] = (time.monotonic(), value)
            return value

        def cache_clear() -> None:
            with lock:
                store.clear()

        wrapper.cache_clear = cache_clear  # type: ignore[attr-defined]
        return wrapper

    return decorator
