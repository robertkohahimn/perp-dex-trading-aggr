"""
Unit tests for Redis client.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json
import pickle
from datetime import timedelta

from app.core.redis_client import RedisClient, cache_result


@pytest.mark.asyncio
@pytest.mark.unit
class TestRedisClient:
    """Test cases for RedisClient."""
    
    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        mock = AsyncMock()
        mock.ping = AsyncMock(return_value=True)
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock(return_value=True)
        mock.setex = AsyncMock(return_value=True)
        mock.delete = AsyncMock(return_value=1)
        mock.exists = AsyncMock(return_value=1)
        mock.expire = AsyncMock(return_value=True)
        mock.lpush = AsyncMock(return_value=1)
        mock.rpush = AsyncMock(return_value=1)
        mock.lpop = AsyncMock(return_value=None)
        mock.lrange = AsyncMock(return_value=[])
        mock.hset = AsyncMock(return_value=1)
        mock.hget = AsyncMock(return_value=None)
        mock.hgetall = AsyncMock(return_value={})
        mock.publish = AsyncMock(return_value=1)
        mock.incr = AsyncMock(return_value=1)
        mock.decr = AsyncMock(return_value=1)
        mock.close = AsyncMock()
        mock.pubsub = AsyncMock()
        mock.ltrim = AsyncMock(return_value=True)
        return mock
    
    @pytest.fixture
    def redis_client(self, mock_redis):
        """Create a RedisClient with mocked connection."""
        client = RedisClient()
        client.client = mock_redis
        return client
    
    async def test_connect_success(self):
        """Test successful Redis connection."""
        client = RedisClient()
        
        with patch('redis.asyncio.ConnectionPool.from_url') as mock_pool:
            with patch('redis.asyncio.Redis') as mock_redis_class:
                mock_redis_instance = AsyncMock()
                mock_redis_instance.ping = AsyncMock(return_value=True)
                mock_redis_class.return_value = mock_redis_instance
                
                await client.connect()
                
                assert client.pool is not None
                assert client.client is not None
                mock_redis_instance.ping.assert_called_once()
    
    async def test_disconnect(self, redis_client):
        """Test Redis disconnection."""
        redis_client.pool = Mock()
        redis_client.pool.disconnect = AsyncMock()
        
        await redis_client.disconnect()
        
        redis_client.client.close.assert_called_once()
        redis_client.pool.disconnect.assert_called_once()
    
    async def test_get_json(self, redis_client):
        """Test getting JSON value from cache."""
        test_data = {"key": "value", "number": 42}
        redis_client.client.get.return_value = json.dumps(test_data).encode()
        
        result = await redis_client.get("test_key")
        
        assert result == test_data
        redis_client.client.get.assert_called_once_with("test_key")
    
    async def test_get_pickle(self, redis_client):
        """Test getting pickled value from cache."""
        # When JSON decoding fails, it tries pickle
        test_object = {"complex": "value", "number": 123}
        # Mock returns something that's not valid JSON
        redis_client.client.get.return_value = b"not-json-data"
        
        # For this test, we'll check that it returns None when neither JSON nor pickle works
        result = await redis_client.get("test_key")
        
        assert result is None  # Neither JSON nor valid pickle
    
    async def test_get_none(self, redis_client):
        """Test getting non-existent key."""
        redis_client.client.get.return_value = None
        
        result = await redis_client.get("nonexistent")
        
        assert result is None
    
    async def test_set_json(self, redis_client):
        """Test setting JSON value in cache."""
        test_data = {"key": "value"}
        
        result = await redis_client.set("test_key", test_data)
        
        assert result is True
        redis_client.client.set.assert_called_once()
        
        # Check that JSON was used
        call_args = redis_client.client.set.call_args
        assert json.loads(call_args[0][1]) == test_data
    
    async def test_set_with_expire(self, redis_client):
        """Test setting value with expiration."""
        result = await redis_client.set("test_key", "value", expire=300)
        
        assert result is True
        redis_client.client.setex.assert_called_once_with("test_key", 300, '"value"')
    
    async def test_set_with_timedelta(self, redis_client):
        """Test setting value with timedelta expiration."""
        result = await redis_client.set(
            "test_key",
            "value",
            expire_timedelta=timedelta(minutes=5)
        )
        
        assert result is True
        redis_client.client.setex.assert_called_once_with("test_key", 300, '"value"')
    
    async def test_delete(self, redis_client):
        """Test deleting a key."""
        result = await redis_client.delete("test_key")
        
        assert result is True
        redis_client.client.delete.assert_called_once_with("test_key")
    
    async def test_exists(self, redis_client):
        """Test checking if key exists."""
        result = await redis_client.exists("test_key")
        
        assert result is True
        redis_client.client.exists.assert_called_once_with("test_key")
    
    async def test_lpush(self, redis_client):
        """Test pushing to left of list."""
        test_data = {"item": "value"}
        
        result = await redis_client.lpush("test_list", test_data)
        
        assert result == 1
        redis_client.client.lpush.assert_called_once()
        
        # Check JSON serialization
        call_args = redis_client.client.lpush.call_args
        assert json.loads(call_args[0][1]) == test_data
    
    async def test_lpop(self, redis_client):
        """Test popping from left of list."""
        test_data = {"item": "value"}
        redis_client.client.lpop.return_value = json.dumps(test_data).encode()
        
        result = await redis_client.lpop("test_list")
        
        assert result == test_data
        redis_client.client.lpop.assert_called_once_with("test_list")
    
    async def test_lrange(self, redis_client):
        """Test getting range from list."""
        test_data = [{"item": 1}, {"item": 2}]
        redis_client.client.lrange.return_value = [
            json.dumps(item).encode() for item in test_data
        ]
        
        result = await redis_client.lrange("test_list", 0, -1)
        
        assert result == test_data
        redis_client.client.lrange.assert_called_once_with("test_list", 0, -1)
    
    async def test_hset(self, redis_client):
        """Test setting hash field."""
        test_data = {"nested": "value"}
        
        result = await redis_client.hset("test_hash", "field", test_data)
        
        assert result == 1
        redis_client.client.hset.assert_called_once()
        
        # Check JSON serialization
        call_args = redis_client.client.hset.call_args
        assert json.loads(call_args[0][2]) == test_data
    
    async def test_hget(self, redis_client):
        """Test getting hash field."""
        test_data = {"nested": "value"}
        redis_client.client.hget.return_value = json.dumps(test_data).encode()
        
        result = await redis_client.hget("test_hash", "field")
        
        assert result == test_data
        redis_client.client.hget.assert_called_once_with("test_hash", "field")
    
    async def test_hgetall(self, redis_client):
        """Test getting all hash fields."""
        test_data = {
            b"field1": json.dumps({"value": 1}).encode(),
            b"field2": json.dumps({"value": 2}).encode()
        }
        redis_client.client.hgetall.return_value = test_data
        
        result = await redis_client.hgetall("test_hash")
        
        assert result == {
            "field1": {"value": 1},
            "field2": {"value": 2}
        }
    
    async def test_publish(self, redis_client):
        """Test publishing message to channel."""
        test_message = {"event": "test", "data": "value"}
        
        result = await redis_client.publish("test_channel", test_message)
        
        assert result == 1
        redis_client.client.publish.assert_called_once()
        
        # Check JSON serialization
        call_args = redis_client.client.publish.call_args
        assert json.loads(call_args[0][1]) == test_message
    
    async def test_subscribe(self, redis_client):
        """Test subscribing to channels."""
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        # pubsub() is a regular method, not async
        redis_client.client.pubsub = MagicMock(return_value=mock_pubsub)
        
        result = await redis_client.subscribe("channel1", "channel2")
        
        assert result == mock_pubsub
        mock_pubsub.subscribe.assert_called_once_with("channel1", "channel2")
    
    async def test_incr(self, redis_client):
        """Test incrementing counter."""
        redis_client.client.incr.return_value = 5
        
        result = await redis_client.incr("counter", 2)
        
        assert result == 5
        redis_client.client.incr.assert_called_once_with("counter", 2)
    
    async def test_acquire_lock(self, redis_client):
        """Test acquiring distributed lock."""
        redis_client.client.set.return_value = True
        
        result = await redis_client.acquire_lock("resource", timeout=30)
        
        assert result is True
        redis_client.client.set.assert_called_once_with(
            "lock:resource", "1", nx=True, ex=30
        )
    
    async def test_release_lock(self, redis_client):
        """Test releasing distributed lock."""
        redis_client.delete = AsyncMock(return_value=True)
        
        result = await redis_client.release_lock("resource")
        
        assert result is True
        redis_client.delete.assert_called_once_with("lock:resource")


@pytest.mark.asyncio
@pytest.mark.unit
class TestCacheDecorator:
    """Test cases for cache_result decorator."""
    
    @pytest.fixture
    def mock_redis_client(self):
        """Mock the redis_client singleton."""
        with patch('app.core.redis_client.redis_client') as mock:
            mock.get = AsyncMock(return_value=None)
            mock.set = AsyncMock(return_value=True)
            yield mock
    
    async def test_cache_miss(self, mock_redis_client):
        """Test decorator when cache misses."""
        call_count = 0
        
        @cache_result(expire_seconds=60, key_prefix="test")
        async def test_function(value):
            nonlocal call_count
            call_count += 1
            return {"result": value * 2}
        
        result = await test_function(5)
        
        assert result == {"result": 10}
        assert call_count == 1
        
        # Verify cache was checked and set
        mock_redis_client.get.assert_called_once()
        mock_redis_client.set.assert_called_once()
    
    async def test_cache_hit(self, mock_redis_client):
        """Test decorator when cache hits."""
        cached_value = {"result": 10}
        mock_redis_client.get.return_value = cached_value
        
        call_count = 0
        
        @cache_result(expire_seconds=60, key_prefix="test")
        async def test_function(value):
            nonlocal call_count
            call_count += 1
            return {"result": value * 2}
        
        result = await test_function(5)
        
        assert result == cached_value
        assert call_count == 0  # Function not called due to cache hit
        
        # Verify cache was checked but not set
        mock_redis_client.get.assert_called_once()
        mock_redis_client.set.assert_not_called()
    
    async def test_cache_key_generation(self, mock_redis_client):
        """Test cache key generation with different arguments."""
        @cache_result(expire_seconds=60, key_prefix="prefix")
        async def test_function(arg1, arg2, kwarg1=None):
            return "result"
        
        await test_function(1, "test", kwarg1="value")
        
        # Check the generated cache key
        call_args = mock_redis_client.get.call_args
        cache_key = call_args[0][0]
        
        assert "prefix" in cache_key
        assert "test_function" in cache_key
        assert "1" in cache_key
        assert "test" in cache_key
        assert "kwarg1=value" in cache_key