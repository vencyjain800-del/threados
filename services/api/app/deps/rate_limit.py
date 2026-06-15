import structlog
from fastapi import HTTPException, Request, status

log = structlog.get_logger()

_RETRY_AFTER = "60"


class RateLimiter:
    """IP-based rate limiter backed by Redis.

    Fails open when Redis is unavailable so existing tests (which run without
    Redis) are not broken.  Production deployments always have Redis running.
    """

    def __init__(self, max_requests: int, window_seconds: int, key_prefix: str) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._prefix = key_prefix
        self._redis = None  # lazy-initialised on first call

    async def _get_redis(self):  # type: ignore[return]
        if self._redis is None:
            import redis.asyncio as aioredis  # noqa: PLC0415

            from app.config import settings  # noqa: PLC0415

            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    async def __call__(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"{self._prefix}:{client_ip}"
        try:
            r = await self._get_redis()
            count: int = await r.incr(key)
            if count == 1:
                await r.expire(key, self._window)
            if count > self._max:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "code": "rate_limit.too_many_requests",
                        "message": "Too many requests. Please try again later.",
                    },
                    headers={"Retry-After": _RETRY_AFTER},
                )
        except HTTPException:
            raise
        except Exception as exc:
            log.warning("rate_limit_redis_unavailable", error=str(exc), key_prefix=self._prefix)


signup_limiter = RateLimiter(max_requests=5, window_seconds=60, key_prefix="rl:signup")
login_limiter = RateLimiter(max_requests=10, window_seconds=60, key_prefix="rl:login")
