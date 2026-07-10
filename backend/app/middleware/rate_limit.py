import time
from collections import defaultdict

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    async def __call__(self, request: Request) -> None:
        key = f"{request.client.host}:{request.url.path}"
        now = time.monotonic()
        bucket = self._buckets[key]

        while bucket and bucket[0] < now - self._window_seconds:
            bucket.pop(0)

        if len(bucket) >= self._max_requests:
            retry_after = int(bucket[0] + self._window_seconds - now)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(max(1, retry_after))},
            )

        bucket.append(now)
