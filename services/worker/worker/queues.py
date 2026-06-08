import os

from redis import Redis
from rq import Queue

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

_redis_conn: Redis | None = None


def get_redis() -> Redis:
    global _redis_conn
    if _redis_conn is None:
        _redis_conn = Redis.from_url(REDIS_URL)
    return _redis_conn


def get_default_queue() -> Queue:
    return Queue("default", connection=get_redis())


def get_high_queue() -> Queue:
    return Queue("high", connection=get_redis())
