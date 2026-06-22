"""Lightweight in-process rate limiting.

A fixed-window counter keyed by (scope, identity). This is intentionally simple
and dependency-free; it protects a single instance well. For multi-instance
deployments, swap ``_Backend`` for a shared store (e.g. Redis) — the limiter API
and the FastAPI dependencies below stay identical.
"""
from __future__ import annotations

import threading
import time

from fastapi import Depends, HTTPException, Request, status

from app.core.config import settings


class _Backend:
    def __init__(self) -> None:
        self._hits: dict[str, tuple[int, float]] = {}  # key -> (count, window_start)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window: int) -> int | None:
        """Register a hit. Returns retry-after seconds if over the limit, else None."""
        now = time.time()
        with self._lock:
            count, start = self._hits.get(key, (0, now))
            if now - start >= window:
                count, start = 0, now  # window elapsed; reset
            count += 1
            self._hits[key] = (count, start)
            # opportunistic prune so the map can't grow unbounded
            if len(self._hits) > 10_000:
                cutoff = now - window
                self._hits = {k: v for k, v in self._hits.items() if v[1] >= cutoff}
            if count > limit:
                return max(1, int(window - (now - start)))
            return None


_backend = _Backend()


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _enforce(key: str, limit: int, window: int) -> None:
    retry = _backend.hit(key, limit, window)
    if retry is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please slow down and try again shortly.",
            headers={"Retry-After": str(retry)},
        )


def limit_ip(scope: str, limit: int, window: int):
    """Dependency: rate-limit by client IP (for unauthenticated/public routes)."""
    def dep(request: Request) -> None:
        if not settings.rate_limit_enabled:
            return
        _enforce(f"{scope}:ip:{_client_ip(request)}", limit, window)
    return dep


def limit_user(scope: str, limit: int, window: int):
    """Dependency: rate-limit by authenticated user (for expensive AI routes)."""
    from app.core.dependencies import get_current_user

    def dep(request: Request, user=Depends(get_current_user)) -> None:
        if not settings.rate_limit_enabled:
            return
        _enforce(f"{scope}:user:{user.id}", limit, window)
    return dep
