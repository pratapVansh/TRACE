import asyncio
import json
import time
from collections import OrderedDict
from typing import Any, Optional

try:
    import redis.asyncio as redis
except ImportError:
    redis = None

from app.core.config import settings

class LocalLRUCache:
    def __init__(self, capacity: int = 10000):
        self.capacity = capacity
        self.cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self.lock = asyncio.Lock()
        self.hits = 0
        self.misses = 0

    async def get(self, key: str) -> Optional[Any]:
        async with self.lock:
            if key not in self.cache:
                self.misses += 1
                return None
            val, expiry = self.cache[key]
            if expiry < time.time():
                self.cache.pop(key)
                self.misses += 1
                return None
            self.cache.move_to_end(key)
            self.hits += 1
            return val

    async def set(self, key: str, value: Any, ttl: int = 3600):
        async with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = (value, time.time() + ttl)
            if len(self.cache) > self.capacity:
                # Remove oldest items (maybe expired ones first)
                now = time.time()
                expired = [k for k, v in self.cache.items() if v[1] < now]
                for k in expired:
                    self.cache.pop(k)
                while len(self.cache) > self.capacity:
                    self.cache.popitem(last=False)

    async def delete(self, key: str):
        async with self.lock:
            if key in self.cache:
                self.cache.pop(key)

    async def delete_pattern(self, pattern: str):
        import re
        regex = re.compile(pattern.replace("*", ".*"))
        async with self.lock:
            keys_to_delete = [k for k in self.cache.keys() if regex.match(k)]
            for k in keys_to_delete:
                self.cache.pop(k)


class CacheManager:
    """Manages Redis connection and caching operations."""
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._local_cache = LocalLRUCache(capacity=10000)
        
    async def connect(self):
        # We can simulate Redis connection if redis is not installed or settings.redis_url is missing
        if redis and getattr(settings, 'redis_url', None):
            self._redis = redis.from_url(settings.redis_url, decode_responses=True)
            try:
                await self._redis.ping()
            except Exception:
                self._redis = None
                
    async def get(self, key: str) -> Optional[Any]:
        from app.core.observability import metrics
        if self._redis:
            val = await self._redis.get(key)
            if val:
                metrics.increment("cache.hits")
                return json.loads(val)
            metrics.increment("cache.misses")
            return None
        else:
            val = await self._local_cache.get(key)
            if val is not None:
                metrics.increment("cache.hits")
            else:
                metrics.increment("cache.misses")
            return val
            
    async def set(self, key: str, value: Any, ttl: int = 3600):
        if self._redis:
            await self._redis.set(key, json.dumps(value), ex=ttl)
        else:
            await self._local_cache.set(key, value, ttl=ttl)

    async def delete(self, key: str):
        if self._redis:
            await self._redis.delete(key)
        else:
            await self._local_cache.delete(key)
            
    async def delete_pattern(self, pattern: str):
        if self._redis:
            keys = await self._redis.keys(pattern)
            if keys:
                await self._redis.delete(*keys)
        else:
            await self._local_cache.delete_pattern(pattern)

cache_manager = CacheManager()
