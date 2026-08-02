"""滑动窗口限流：Redis Sorted Set + pipeline 原子化。"""

import time
import uuid
from functools import lru_cache

from app.core.config import settings
from app.core.exceptions import RateLimitedError
from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger(__name__)

WINDOW_SECONDS = 60


class RateLimiter:
    def __init__(self) -> None:
        self._redis = get_redis()

    async def check(self, identity: str) -> None:
        now = time.time()
        key = f"rate-limit:{identity}"
        async with self._redis.pipeline(transaction=True) as pipe:
            await pipe.zremrangebyscore(key, 0, now - WINDOW_SECONDS)
            await pipe.zcard(key)
            await pipe.zadd(key, {str(uuid.uuid4()): now})
            await pipe.expire(key, WINDOW_SECONDS)
            results = await pipe.execute()
            count = results[1]
            limit = settings.rate_limit_per_minute

            if int(count) >= limit:
                logger.warning(
                    "rate limit exceeded: identity=%s count=%s limit=%s",
                    identity, count, limit,
                )
                raise RateLimitedError(
                    f"请求过于频繁，每分钟最多 {limit} 次，请稍后再试"
                )


@lru_cache(maxsize=1)
def get_rate_limiter() -> RateLimiter:
    return RateLimiter()
