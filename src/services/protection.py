import asyncio
import time
from collections import defaultdict, deque

import httpx

from src.core.config import get_settings


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        settings = get_settings()
        now = time.monotonic()
        boundary = now - settings.submission_rate_window_seconds
        async with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < boundary:
                hits.popleft()
            if len(hits) >= settings.submission_rate_limit:
                return False
            hits.append(now)
            return True


rate_limiter = InMemoryRateLimiter()


async def verify_turnstile(token: str, remote_ip: str) -> bool:
    settings = get_settings()
    if not settings.turnstile_secret_key:
        return settings.app_env != "production"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={
                "secret": settings.turnstile_secret_key,
                "response": token,
                "remoteip": remote_ip,
            },
        )
    return bool(response.json().get("success"))
