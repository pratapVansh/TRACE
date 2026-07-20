import time
import uuid
from collections import defaultdict

from fastapi import HTTPException, Request, status
from app.core.cache import cache_manager

class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    async def __call__(self, request: Request) -> None:
        key = f"rate_limit:{request.client.host}:{request.url.path}"
        now = time.time()
        redis = cache_manager._redis

        if redis:
            pipeline = redis.pipeline()
            pipeline.zremrangebyscore(key, 0, now - self._window_seconds)
            req_id = str(uuid.uuid4())
            pipeline.zadd(key, {req_id: now})
            pipeline.zcard(key)
            pipeline.expire(key, self._window_seconds)
            results = await pipeline.execute()
            
            count = results[2]
            if count > self._max_requests:
                oldest = await redis.zrange(key, 0, 0, withscores=True)
                retry_after = self._window_seconds
                if oldest:
                    retry_after = int(oldest[0][1] + self._window_seconds - now)
                
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                    headers={"Retry-After": str(max(1, retry_after))},
                )
        else:
            now_mono = time.monotonic()
            bucket = self._buckets[key]

            while bucket and bucket[0] < now_mono - self._window_seconds:
                bucket.pop(0)

            if len(bucket) >= self._max_requests:
                retry_after = int(bucket[0] + self._window_seconds - now_mono)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                    headers={"Retry-After": str(max(1, retry_after))},
                )

            bucket.append(now_mono)
