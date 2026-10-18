"""A minimal TTL cache for expensive endpoint computations (percentiles,
similarity, squad optimization) -- spec section 52. Keyed on function
name + arguments. Not a distributed cache (no Redis dependency for this
deliverable), but the interface (`cached`) is a drop-in decorator, so
swapping in Redis later doesn't change any call site.

Invalidated wholesale by `clear()`, which the ingest/reload endpoint
calls after a data refresh -- correctness (never serve stale results
after new data lands) matters more here than cache hit rate.
"""
from __future__ import annotations

import functools
import time
from typing import Any, Callable

_CACHE: dict[str, tuple[float, Any]] = {}
DEFAULT_TTL_SECONDS = 300


def cached(ttl: int = DEFAULT_TTL_SECONDS) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__module__}.{func.__qualname__}:{args}:{sorted(kwargs.items())}"
            now = time.time()
            if key in _CACHE:
                cached_at, value = _CACHE[key]
                if now - cached_at < ttl:
                    return value
            value = func(*args, **kwargs)
            _CACHE[key] = (now, value)
            return value
        return wrapper
    return decorator


def clear() -> None:
    _CACHE.clear()
