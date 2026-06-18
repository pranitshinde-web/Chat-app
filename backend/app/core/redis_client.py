import json
from typing import Optional, Any, Set
from redis.asyncio import Redis, ConnectionPool
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class RedisClient:
    pool: Optional[ConnectionPool] = None
    client: Optional[Redis] = None


redis_state = RedisClient()


async def connect_to_redis() -> None:
    """
    Creates a Redis connection pool and verifies connectivity.
    Called once on application startup.
    """
    logger.info("Connecting to Redis...")
    try:
        redis_state.pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=settings.REDIS_SOCKET_TIMEOUT,
            decode_responses=True,
        )
        redis_state.client = Redis(connection_pool=redis_state.pool)

        # Verify connection
        await redis_state.client.ping()
        logger.info("Connected to Redis")

    except RedisConnectionError as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise


async def disconnect_from_redis() -> None:
    """
    Closes the Redis connection pool cleanly.
    Called once on application shutdown.
    """
    if redis_state.client:
        await redis_state.client.aclose()
        logger.info("Disconnected from Redis")


def get_redis() -> Redis:
    """
    Returns the active Redis client instance.
    Use this as a FastAPI dependency in routers.
    """
    if redis_state.client is None:
        raise RuntimeError(
            "Redis not initialized. "
            "Ensure connect_to_redis() was called on startup."
        )
    return redis_state.client


# ── Utility Functions ──────────────────────────────────────────────────────────

async def set_value(key: str, value: Any) -> bool:
    """
    Store a plain string value with no expiry.
    """
    try:
        client = get_redis()
        serialized = json.dumps(value) if not isinstance(value, str) else value
        await client.set(key, serialized)
        return True
    except RedisError as e:
        logger.error(f"Redis set_value error | key={key} | {e}")
        return False


async def set_with_expiry(key: str, value: Any, ttl_seconds: int) -> bool:
    """
    Store a value that auto-deletes after ttl_seconds.
    Used for presence tracking, typing indicators, session tokens.
    """
    try:
        client = get_redis()
        serialized = json.dumps(value) if not isinstance(value, str) else value
        await client.setex(key, ttl_seconds, serialized)
        return True
    except RedisError as e:
        logger.error(f"Redis set_with_expiry error | key={key} | {e}")
        return False


async def get_value(key: str) -> Optional[str]:
    """
    Retrieve a value by key. Returns None if key does not exist.
    """
    try:
        client = get_redis()
        value = await client.get(key)
        return value
    except RedisError as e:
        logger.error(f"Redis get_value error | key={key} | {e}")
        return None


async def delete_key(key: str) -> bool:
    """
    Delete a key. Returns True if key existed and was deleted.
    """
    try:
        client = get_redis()
        result = await client.delete(key)
        return result > 0
    except RedisError as e:
        logger.error(f"Redis delete_key error | key={key} | {e}")
        return False


async def key_exists(key: str) -> bool:
    """
    Check if a key exists in Redis without fetching its value.
    """
    try:
        client = get_redis()
        result = await client.exists(key)
        return result > 0
    except RedisError as e:
        logger.error(f"Redis key_exists error | key={key} | {e}")
        return False


async def refresh_expiry(key: str, ttl_seconds: int) -> bool:
    """
    Reset the TTL on an existing key without changing its value.
    Used for keepalive on presence keys.
    """
    try:
        client = get_redis()
        result = await client.expire(key, ttl_seconds)
        return result
    except RedisError as e:
        logger.error(f"Redis refresh_expiry error | key={key} | {e}")
        return False


async def add_to_set(key: str, *values: str) -> bool:
    """
    Add one or more members to a Redis set.
    Used for tracking which users are in a room.
    """
    try:
        client = get_redis()
        await client.sadd(key, *values)
        return True
    except RedisError as e:
        logger.error(f"Redis add_to_set error | key={key} | {e}")
        return False


async def remove_from_set(key: str, *values: str) -> bool:
    """
    Remove one or more members from a Redis set.
    """
    try:
        client = get_redis()
        await client.srem(key, *values)
        return True
    except RedisError as e:
        logger.error(f"Redis remove_from_set error | key={key} | {e}")
        return False


async def get_set_members(key: str) -> Set[str]:
    """
    Return all members of a Redis set.
    Returns empty set if key does not exist.
    """
    try:
        client = get_redis()
        members = await client.smembers(key)
        return members or set()
    except RedisError as e:
        logger.error(f"Redis get_set_members error | key={key} | {e}")
        return set()


async def increment(key: str, amount: int = 1) -> Optional[int]:
    """
    Atomically increment a counter.
    Used for unread message counts.
    """
    try:
        client = get_redis()
        return await client.incrby(key, amount)
    except RedisError as e:
        logger.error(f"Redis increment error | key={key} | {e}")
        return None


async def get_all_keys_by_pattern(pattern: str) -> list:
    """
    Scan for all keys matching a pattern.
    Uses SCAN instead of KEYS to avoid blocking Redis in production.
    """
    try:
        client = get_redis()
        keys = []
        async for key in client.scan_iter(match=pattern):
            keys.append(key)
        return keys
    except RedisError as e:
        logger.error(f"Redis scan error | pattern={pattern} | {e}")
        return []