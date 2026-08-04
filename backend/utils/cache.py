"""In-process TTL cache for Google Sheets reads.

Apps Script round-trips take 2-30s and occasionally fail outright, so every page
load paying that cost is the main source of the app feeling slow. This caches
read results for a short TTL and — importantly — clears the relevant entries as
soon as a write succeeds, so a newly created event or visitor shows up
immediately instead of after the TTL expires.

Scope: a single process, in memory. That matches the deployment (one uvicorn
container), and means a container restart simply starts cold. It is not a
distributed cache and does not try to be.
"""

import asyncio
import time
from typing import Any, Callable, Awaitable, Optional

from backend.core.config import logger, CACHE_TTL_SECONDS


class TTLCache:
    def __init__(self, ttl_seconds: int):
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}
        # One lock per key, so a cache miss on 'events' doesn't block a
        # concurrent miss on a different key.
        self._locks: dict[str, asyncio.Lock] = {}

    @property
    def enabled(self) -> bool:
        return self.ttl > 0

    def _lock_for(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        if not self.enabled:
            return
        self._store[key] = (time.monotonic() + self.ttl, value)

    def invalidate(self, *keys: str) -> None:
        """Drop specific keys. Called after a successful write."""
        for key in keys:
            if self._store.pop(key, None) is not None:
                logger.info("Cache invalidated: %s", key)

    def invalidate_prefix(self, prefix: str) -> None:
        """Drop every key starting with `prefix` (e.g. all per-event entries)."""
        doomed = [k for k in self._store if k.startswith(prefix)]
        for key in doomed:
            self._store.pop(key, None)
        if doomed:
            logger.info("Cache invalidated %d key(s) under '%s'", len(doomed), prefix)

    def clear(self) -> None:
        self._store.clear()
        logger.info("Cache cleared")

    def stats(self) -> dict:
        now = time.monotonic()
        live = sum(1 for exp, _ in self._store.values() if exp > now)
        return {"enabled": self.enabled, "ttl_seconds": self.ttl, "live_entries": live}

    async def get_or_fetch(
        self,
        key: str,
        fetch: Callable[[], Awaitable[Any]],
        should_cache: Callable[[Any], bool] = lambda v: True,
    ) -> Any:
        """Return the cached value for `key`, else call `fetch` and cache it.

        `should_cache` guards against caching failures — an Apps Script error
        response is a valid Python object but must not be served for the next
        60 seconds, so only successful payloads are stored.
        """
        if not self.enabled:
            return await fetch()

        hit = self.get(key)
        if hit is not None:
            logger.info("Cache HIT: %s", key)
            return hit

        # Single-flight: if several requests miss the same key at once, only the
        # first calls Apps Script; the rest wait and reuse its result. Without
        # this, a page with 3 widgets triggers 3 identical 5s round-trips.
        async with self._lock_for(key):
            hit = self.get(key)
            if hit is not None:
                logger.info("Cache HIT (after wait): %s", key)
                return hit

            logger.info("Cache MISS: %s", key)
            value = await fetch()
            if should_cache(value):
                self.set(key, value)
            else:
                logger.info("Not caching unsuccessful result for: %s", key)
            return value


cache = TTLCache(CACHE_TTL_SECONDS)


# --- Key builders (kept here so writers and readers can't drift apart) ---

KEY_EVENTS = "events:list"
KEY_COMPANY_PROFILE = "company:profile"


def key_event(event_id: str) -> str:
    return f"event:{event_id}"


def key_event_data(event_id: str, event_name: str) -> str:
    return f"eventdata:{event_id or ''}|{event_name or ''}"


def is_successful(payload: Any) -> bool:
    """True only for an Apps Script response that actually succeeded."""
    return isinstance(payload, dict) and payload.get("success") is True
