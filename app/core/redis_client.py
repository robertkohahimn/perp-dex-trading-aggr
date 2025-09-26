"""
Redis client for caching and pub/sub.
"""
import json
import pickle
from typing import Optional, Any, Dict, List
import redis.asyncio as redis
from datetime import timedelta
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Async Redis client for caching and message queuing."""
    
    def __init__(self):
        self.redis_url = settings.database.redis_url
        self.pool = None
        self.client = None
    
    async def connect(self):
        """Initialize Redis connection pool."""
        try:
            self.pool = redis.ConnectionPool.from_url(
                self.redis_url,
                decode_responses=False,
                max_connections=50
            )
            self.client = redis.Redis(connection_pool=self.pool)
            await self.client.ping()
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self):
        """Close Redis connections."""
        if self.client:
            await self.client.close()
        if self.pool:
            await self.pool.disconnect()
    
    # Cache operations
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            value = await self.client.get(key)
            if value:
                # Try to deserialize as JSON first
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    # Fall back to pickle
                    return pickle.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error getting key {key}: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None,
        expire_timedelta: Optional[timedelta] = None
    ) -> bool:
        """Set value in cache with optional expiration."""
        try:
            # Try JSON serialization first
            try:
                serialized = json.dumps(value)
            except (TypeError, ValueError):
                # Fall back to pickle for complex objects
                serialized = pickle.dumps(value)
            
            if expire_timedelta:
                expire = int(expire_timedelta.total_seconds())
            
            if expire:
                await self.client.setex(key, expire, serialized)
            else:
                await self.client.set(key, serialized)
            return True
        except Exception as e:
            logger.error(f"Error setting key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            result = await self.client.delete(key)
            return bool(result)
        except Exception as e:
            logger.error(f"Error deleting key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        try:
            return bool(await self.client.exists(key))
        except Exception as e:
            logger.error(f"Error checking key {key}: {e}")
            return False
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on key."""
        try:
            return bool(await self.client.expire(key, seconds))
        except Exception as e:
            logger.error(f"Error setting expiration for key {key}: {e}")
            return False
    
    # List operations
    async def lpush(self, key: str, value: Any) -> int:
        """Push value to left of list."""
        try:
            serialized = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
            return await self.client.lpush(key, serialized)
        except Exception as e:
            logger.error(f"Error lpush to {key}: {e}")
            return 0
    
    async def rpush(self, key: str, value: Any) -> int:
        """Push value to right of list."""
        try:
            serialized = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
            return await self.client.rpush(key, serialized)
        except Exception as e:
            logger.error(f"Error rpush to {key}: {e}")
            return 0
    
    async def lpop(self, key: str) -> Optional[Any]:
        """Pop value from left of list."""
        try:
            value = await self.client.lpop(key)
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value.decode() if isinstance(value, bytes) else value
            return None
        except Exception as e:
            logger.error(f"Error lpop from {key}: {e}")
            return None
    
    async def lrange(self, key: str, start: int = 0, end: int = -1) -> List[Any]:
        """Get range of values from list."""
        try:
            values = await self.client.lrange(key, start, end)
            result = []
            for value in values:
                try:
                    result.append(json.loads(value))
                except json.JSONDecodeError:
                    result.append(value.decode() if isinstance(value, bytes) else value)
            return result
        except Exception as e:
            logger.error(f"Error lrange from {key}: {e}")
            return []
    
    # Hash operations
    async def hset(self, name: str, key: str, value: Any) -> int:
        """Set hash field."""
        try:
            serialized = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
            return await self.client.hset(name, key, serialized)
        except Exception as e:
            logger.error(f"Error hset {name}:{key}: {e}")
            return 0
    
    async def hget(self, name: str, key: str) -> Optional[Any]:
        """Get hash field."""
        try:
            value = await self.client.hget(name, key)
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value.decode() if isinstance(value, bytes) else value
            return None
        except Exception as e:
            logger.error(f"Error hget {name}:{key}: {e}")
            return None
    
    async def hgetall(self, name: str) -> Dict[str, Any]:
        """Get all hash fields."""
        try:
            data = await self.client.hgetall(name)
            result = {}
            for key, value in data.items():
                key_str = key.decode() if isinstance(key, bytes) else key
                try:
                    result[key_str] = json.loads(value)
                except json.JSONDecodeError:
                    result[key_str] = value.decode() if isinstance(value, bytes) else value
            return result
        except Exception as e:
            logger.error(f"Error hgetall {name}: {e}")
            return {}
    
    # Pub/Sub operations
    async def publish(self, channel: str, message: Any) -> int:
        """Publish message to channel."""
        try:
            serialized = json.dumps(message) if isinstance(message, (dict, list)) else str(message)
            return await self.client.publish(channel, serialized)
        except Exception as e:
            logger.error(f"Error publishing to {channel}: {e}")
            return 0
    
    async def subscribe(self, *channels: str):
        """Subscribe to channels."""
        try:
            pubsub = self.client.pubsub()
            await pubsub.subscribe(*channels)
            return pubsub
        except Exception as e:
            logger.error(f"Error subscribing to channels: {e}")
            raise
    
    # Atomic operations
    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment counter."""
        try:
            return await self.client.incr(key, amount)
        except Exception as e:
            logger.error(f"Error incrementing {key}: {e}")
            return 0
    
    async def decr(self, key: str, amount: int = 1) -> int:
        """Decrement counter."""
        try:
            return await self.client.decr(key, amount)
        except Exception as e:
            logger.error(f"Error decrementing {key}: {e}")
            return 0
    
    # Lock operations for distributed locking
    async def acquire_lock(self, key: str, timeout: int = 10) -> bool:
        """Acquire distributed lock."""
        try:
            return await self.client.set(f"lock:{key}", "1", nx=True, ex=timeout)
        except Exception as e:
            logger.error(f"Error acquiring lock {key}: {e}")
            return False
    
    async def release_lock(self, key: str) -> bool:
        """Release distributed lock."""
        try:
            return await self.delete(f"lock:{key}")
        except Exception as e:
            logger.error(f"Error releasing lock {key}: {e}")
            return False


# Singleton instance
redis_client = RedisClient()


# Cache decorator
def cache_result(expire_seconds: int = 300, key_prefix: str = ""):
    """Decorator to cache function results."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}"
            if args:
                cache_key += f":{':'.join(str(a) for a in args)}"
            if kwargs:
                cache_key += f":{':'.join(f'{k}={v}' for k, v in sorted(kwargs.items()))}"
            
            # Try to get from cache
            cached = await redis_client.get(cache_key)
            if cached is not None:
                return cached
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            await redis_client.set(cache_key, result, expire=expire_seconds)
            
            return result
        return wrapper
    return decorator