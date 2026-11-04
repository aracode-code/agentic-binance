"""Small thread-safe in-memory TTL cache for market data.

Keeps the watcher and the GUI from re-downloading the same candles on every
run. Uses monotonic time so wall-clock changes cannot resurrect entries.
"""
import threading
import time
from typing import Any, Callable

_store: dict[str, tuple[float, Any]] = {}
_lock = threading.Lock()


def get(key: str) -> Any:
    """Return a live entry, or None when missing/expired."""
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at <= time.monotonic():
            _store.pop(key, None)
            return None
        return value


def set(key: str, value: Any, ttl_seconds: float) -> None:
    with _lock:
        _store[key] = (time.monotonic() + ttl_seconds, value)


def get_or_fetch(key: str, ttl_seconds: float, fetch: Callable[[], Any]) -> Any:
    """Return the cached value or call `fetch` once and cache the result."""
    cached = get(key)
    if cached is not None:
        return cached
    value = fetch()
    set(key, value, ttl_seconds)
    return value


def clear() -> None:
    with _lock:
        _store.clear()
