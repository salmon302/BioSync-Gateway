# SPDX-License-Identifier: MIT
"""
Shared infrastructure for external API clients.
Implements SRS §3.10 - External Data Integration

Provides:
    - ExternalAPIError: raised when a live call fails and no cache is available
    - RateLimiter: async-safe token-interval rate limiter (SRS §4.3)
    - CachedClient: base class with on-disk caching + resilient HTTP GET
      (SRS FR-3.10.3 - local caching to reduce dependency on external services)

Design notes (P1-7 - Real external API calls):
    - There are NO mock-data fallbacks. Clients make real HTTPS calls.
    - On transient failure the client degrades to *stale* cache (if present) so
      the platform keeps functioning during upstream outages, matching the
      intent of FR-3.10.3. If nothing is cached, ExternalAPIError is raised.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Package version advertised to upstream services via User-Agent. NCBI in
# particular asks clients to identify themselves.
USER_AGENT = "BioSync-Gateway/1.0 (+https://github.com/biosync-gateway)"


def default_cache_root() -> str:
    """
    Resolve the base cache directory.

    Honours the BIOSYNC_CACHE_DIR environment variable so deployments (Docker,
    CI) can pin a writable location. Falls back to the OS temp dir which works
    on both Linux containers and Windows dev machines.
    """
    return os.getenv("BIOSYNC_CACHE_DIR") or os.path.join(
        tempfile.gettempdir(), "biosync_cache"
    )


class ExternalAPIError(RuntimeError):
    """Raised when an external API call fails and no cached data can serve it."""


class RateLimiter:
    """
    Async-safe rate limiter enforcing a minimum interval between calls.

    Unlike a decorator closure, this is a real object with an ``asyncio.Lock``
    so concurrent coroutines cannot bypass the limit. Shared per client so all
    requests from one client honour the same upstream quota.

    Args:
        calls_per_second: Maximum sustained call rate. ``<= 0`` disables limiting.
    """

    def __init__(self, calls_per_second: float):
        self._min_interval = 1.0 / calls_per_second if calls_per_second > 0 else 0.0
        self._last_call = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until it is safe to issue the next request."""
        if self._min_interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            wait = self._min_interval - (now - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()


class CachedClient:
    """
    Base class for external API clients with on-disk caching and resilient GET.

    Subclasses set BASE_URL / CACHE_TTL_HOURS and call ``_get_json``.
    """

    #: Default per-client rate. Overridden per upstream service.
    CALLS_PER_SECOND: float = 3.0
    #: Number of attempts for retryable failures (429 / 5xx / network).
    MAX_RETRIES: int = 3
    #: Base seconds for exponential backoff between retries.
    RETRY_BACKOFF: float = 0.5
    #: Per-request timeout in seconds.
    TIMEOUT: float = 30.0

    def __init__(
        self,
        cache_dir: str,
        calls_per_second: Optional[float] = None,
    ):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self._rate_limiter = RateLimiter(
            calls_per_second if calls_per_second is not None else self.CALLS_PER_SECOND
        )
        self._session = None

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------
    def _cache_path(self, key: str) -> str:
        """Cache file path for a key (sanitised to a safe filename)."""
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
        return os.path.join(self.cache_dir, f"{safe}.json")

    def _load_cache(self, key: str):
        """
        Load a cache entry.

        Returns:
            Tuple of (data, age_hours). Both are ``None`` when no entry exists.
        """
        path = self._cache_path(key)
        if not os.path.exists(path):
            return None, None
        try:
            age_hours = (time.time() - os.path.getmtime(path)) / 3600.0
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f), age_hours
        except (OSError, ValueError) as exc:
            logger.warning("Failed to read cache %s: %s", path, exc)
            return None, None

    def _write_cache(self, key: str, data: Any) -> None:
        """Persist a value to the cache atomically."""
        path = self._cache_path(key)
        tmp = f"{path}.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp, path)
        except OSError as exc:
            logger.warning("Failed to write cache %s: %s", path, exc)

    def _cached_or_fetch_sync_wrapper(self):  # pragma: no cover - placeholder
        raise NotImplementedError

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------
    async def _get_session(self):
        """Lazily create a shared httpx.AsyncClient."""
        if self._session is None:
            import httpx

            self._session = httpx.AsyncClient(
                timeout=self.TIMEOUT,
                limits=httpx.Limits(max_keepalive_connections=5),
                headers={"User-Agent": USER_AGENT},
            )
        return self._session

    async def aclose(self) -> None:
        """Close the underlying HTTP session."""
        if self._session is not None:
            await self._session.aclose()
            self._session = None

    async def _get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict]:
        """
        Perform a rate-limited GET with retry/backoff and return parsed JSON.

        Returns:
            Parsed JSON dict, or ``None`` if the resource does not exist (404).

        Raises:
            ExternalAPIError: on repeated transient failures or bad responses.
        """
        import httpx

        session = await self._get_session()
        request_headers = {"Accept": "application/json"}
        if headers:
            request_headers.update(headers)

        last_exc: Optional[Exception] = None
        for attempt in range(self.MAX_RETRIES):
            await self._rate_limiter.acquire()
            try:
                response = await session.get(
                    url, params=params, headers=request_headers
                )

                # 404 is a definitive "not found" - do not retry, do not fall back.
                if response.status_code == 404:
                    return None

                # Retry throttling and server errors with backoff.
                if response.status_code == 429 or response.status_code >= 500:
                    last_exc = ExternalAPIError(
                        f"{url} returned HTTP {response.status_code}"
                    )
                    await self._backoff(attempt, response)
                    continue

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as exc:
                # Non-retryable 4xx (other than 404/429 handled above).
                raise ExternalAPIError(
                    f"{url} failed: HTTP {exc.response.status_code}"
                ) from exc
            except (httpx.TransportError, httpx.HTTPError, ValueError) as exc:
                last_exc = exc
                await self._backoff(attempt)

        raise ExternalAPIError(
            f"{url} failed after {self.MAX_RETRIES} attempts"
        ) from last_exc

    async def _backoff(self, attempt: int, response=None) -> None:
        """Sleep using exponential backoff, honouring Retry-After when present."""
        delay = self.RETRY_BACKOFF * (2 ** attempt)
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    delay = max(delay, float(retry_after))
                except ValueError:
                    pass
        await asyncio.sleep(delay)

    # ------------------------------------------------------------------
    # Cache-aware fetch orchestration
    # ------------------------------------------------------------------
    async def _cached_fetch(self, cache_key: str, ttl_hours: float, fetch, *, empty=None):
        """
        Return fresh cache, else fetch live, else fall back to stale cache.

        Args:
            cache_key: Cache identifier.
            ttl_hours: Freshness window in hours.
            fetch: Zero-arg coroutine performing the live request; returns the
                   value to cache (or ``None`` for "not found").
            empty: Sentinel returned for a definitive not-found result.

        Raises:
            ExternalAPIError: when the live call fails and no cache exists.
        """
        cached, age_hours = self._load_cache(cache_key)
        if cached is not None and age_hours is not None and age_hours < ttl_hours:
            return cached

        try:
            result = await fetch()
        except ExternalAPIError:
            if cached is not None:
                logger.warning(
                    "External call failed for '%s'; serving stale cache "
                    "(age %.1fh)", cache_key, age_hours or 0.0,
                )
                return cached
            raise

        if result is None:
            return empty

        self._write_cache(cache_key, result)
        return result
