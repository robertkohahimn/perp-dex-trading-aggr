"""
Unit tests for notification service.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
import asyncio
import json

from services.notification_service import (
    NotificationService,
    Notification,
    NotificationType,
    NotificationPriority,
    NotificationPreferences
)


@pytest.mark.asyncio
@pytest.mark.unit
class TestNotificationService:
    """Test cases for NotificationService."""
    
    @pytest.fixture
    def notification_service(self):
        """Create notification service instance."""
        return NotificationService()
    
    @pytest.fixture
    def sample_notification(self):
        """Create sample notification."""
        return Notification(
            id="1:ORDER_FILLED:123456789",
            account_id=1,
            type=NotificationType.ORDER_FILLED,
            priority=NotificationPriority.MEDIUM,
            title="Order Filled",
            message="Your BUY order for BTC-PERP has been filled",
            data={"symbol": "BTC-PERP", "side": "BUY", "price": 50000},
            timestamp=datetime.utcnow(),
            read=False
        )
    
    @patch('services.notification_service.redis_client')
    async def test_send_notification(self, mock_redis, notification_service):
        """Test sending a notification."""
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.lpush = AsyncMock(return_value=1)
        mock_redis.ltrim = AsyncMock(return_value=True)
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.publish = AsyncMock(return_value=1)
        
        result = await notification_service.send_notification(
            account_id=1,
            type=NotificationType.ORDER_FILLED,
            title="Order Filled",
            message="Your order has been filled",
            data={"order_id": 123},
            priority=NotificationPriority.MEDIUM
        )
        
        assert result is not None
        assert "1:ORDER_FILLED:" in result
        
        # Verify Redis operations
        mock_redis.set.assert_called_once()
        mock_redis.lpush.assert_called_once()
        mock_redis.publish.assert_called_once()
        mock_redis.incr.assert_called_once()
    
    @patch('services.notification_service.redis_client')
    async def test_send_notification_with_subscribers(self, mock_redis, notification_service):
        """Test sending notification to WebSocket subscribers."""
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.lpush = AsyncMock(return_value=1)
        mock_redis.ltrim = AsyncMock(return_value=True)
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.publish = AsyncMock(return_value=1)
        
        # Add a subscriber
        queue = asyncio.Queue()
        notification_service.subscribers[1] = [queue]
        
        await notification_service.send_notification(
            account_id=1,
            type=NotificationType.ORDER_FILLED,
            title="Order Filled",
            message="Your order has been filled",
            data={"order_id": 123}
        )
        
        # Check queue received notification
        assert queue.qsize() == 1
        notification = await queue.get()
        assert isinstance(notification, Notification)
        assert notification.type == NotificationType.ORDER_FILLED
    
    @patch('services.notification_service.redis_client')
    async def test_send_notification_with_handler(self, mock_redis, notification_service):
        """Test sending notification with registered handler."""
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.lpush = AsyncMock(return_value=1)
        mock_redis.ltrim = AsyncMock(return_value=True)
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.publish = AsyncMock(return_value=1)
        
        # Register a handler
        handler_called = False
        async def test_handler(notification):
            nonlocal handler_called
            handler_called = True
        
        notification_service.register_handler(NotificationType.ORDER_FILLED, test_handler)
        
        await notification_service.send_notification(
            account_id=1,
            type=NotificationType.ORDER_FILLED,
            title="Order Filled",
            message="Your order has been filled",
            data={"order_id": 123}
        )
        
        assert handler_called is True
    
    @patch('services.notification_service.redis_client')
    async def test_get_notifications(self, mock_redis, notification_service, sample_notification):
        """Test getting notifications."""
        mock_redis.lrange = AsyncMock(return_value=[sample_notification.to_dict()])
        
        notifications = await notification_service.get_notifications(account_id=1, limit=50)
        
        assert len(notifications) == 1
        assert notifications[0].id == sample_notification.id
        assert notifications[0].type == NotificationType.ORDER_FILLED
        
        mock_redis.lrange.assert_called_once_with("notifications:list:1", 0, 49)
    
    @patch('services.notification_service.redis_client')
    async def test_get_notifications_unread_only(self, mock_redis, notification_service):
        """Test getting only unread notifications."""
        read_notification = {
            'id': '1:ORDER_FILLED:123',
            'account_id': 1,
            'type': 'ORDER_FILLED',
            'priority': 'MEDIUM',
            'title': 'Order Filled',
            'message': 'Filled',
            'data': {},
            'timestamp': datetime.utcnow().isoformat(),
            'read': True
        }
        unread_notification = {
            'id': '1:ORDER_FILLED:124',
            'account_id': 1,
            'type': 'ORDER_FILLED',
            'priority': 'MEDIUM',
            'title': 'Order Filled',
            'message': 'Filled',
            'data': {},
            'timestamp': datetime.utcnow().isoformat(),
            'read': False
        }
        
        mock_redis.lrange = AsyncMock(return_value=[read_notification, unread_notification])
        
        notifications = await notification_service.get_notifications(
            account_id=1,
            unread_only=True
        )
        
        assert len(notifications) == 1
        assert notifications[0].read is False
    
    @patch('services.notification_service.redis_client')
    async def test_mark_as_read(self, mock_redis, notification_service, sample_notification):
        """Test marking notification as read."""
        mock_redis.get = AsyncMock(return_value=sample_notification.to_dict())
        mock_redis.set = AsyncMock(return_value=True)
        
        result = await notification_service.mark_as_read(sample_notification.id)
        
        assert result is True
        
        # Verify Redis operations
        mock_redis.get.assert_called_once_with(f"notification:{sample_notification.id}")
        mock_redis.set.assert_called_once()
        
        # Check that read status was updated
        call_args = mock_redis.set.call_args[0]
        assert call_args[1]['read'] is True
    
    @patch('services.notification_service.redis_client')
    async def test_mark_all_as_read(self, mock_redis, notification_service):
        """Test marking all notifications as read."""
        notifications = [
            {'id': '1:ORDER_FILLED:123', 'read': False, 'account_id': 1, 
             'type': 'ORDER_FILLED', 'priority': 'MEDIUM', 'title': 'Test',
             'message': 'Test', 'data': {}, 'timestamp': datetime.utcnow().isoformat()},
            {'id': '1:ORDER_FILLED:124', 'read': False, 'account_id': 1,
             'type': 'ORDER_FILLED', 'priority': 'MEDIUM', 'title': 'Test',
             'message': 'Test', 'data': {}, 'timestamp': datetime.utcnow().isoformat()}
        ]
        
        mock_redis.lrange = AsyncMock(return_value=notifications)
        mock_redis.get = AsyncMock(side_effect=notifications)
        mock_redis.set = AsyncMock(return_value=True)
        
        count = await notification_service.mark_all_as_read(account_id=1)
        
        assert count == 2
        assert mock_redis.set.call_count == 2
    
    @patch('services.notification_service.redis_client')
    async def test_delete_notification(self, mock_redis, notification_service):
        """Test deleting a notification."""
        mock_redis.delete = AsyncMock(return_value=True)
        
        result = await notification_service.delete_notification("1:ORDER_FILLED:123")
        
        assert result is True
        mock_redis.delete.assert_called_once_with("notification:1:ORDER_FILLED:123")
    
    async def test_subscribe_to_notifications(self, notification_service):
        """Test subscribing to notifications."""
        queue = await notification_service.subscribe_to_notifications(account_id=1)
        
        assert isinstance(queue, asyncio.Queue)
        assert 1 in notification_service.subscribers
        assert queue in notification_service.subscribers[1]
    
    async def test_unsubscribe_from_notifications(self, notification_service):
        """Test unsubscribing from notifications."""
        queue = await notification_service.subscribe_to_notifications(account_id=1)
        
        await notification_service.unsubscribe_from_notifications(account_id=1, queue=queue)
        
        assert 1 not in notification_service.subscribers
    
    def test_register_handler(self, notification_service):
        """Test registering notification handler."""
        async def test_handler(notification):
            pass
        
        notification_service.register_handler(NotificationType.ORDER_FILLED, test_handler)
        
        assert NotificationType.ORDER_FILLED in notification_service.notification_handlers
        assert test_handler in notification_service.notification_handlers[NotificationType.ORDER_FILLED]
    
    @patch('services.notification_service.redis_client')
    async def test_notify_order_filled(self, mock_redis, notification_service):
        """Test order filled notification."""
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.lpush = AsyncMock(return_value=1)
        mock_redis.ltrim = AsyncMock(return_value=True)
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.publish = AsyncMock(return_value=1)
        
        order_data = {
            'symbol': 'BTC-PERP',
            'side': 'BUY',
            'price': 50000
        }
        
        await notification_service.notify_order_filled(account_id=1, order_data=order_data)
        
        # Verify notification was sent
        mock_redis.publish.assert_called_once()
        publish_args = mock_redis.publish.call_args[0]
        assert publish_args[0] == "notifications:1"
        
        notification_data = publish_args[1]
        assert notification_data['type'] == NotificationType.ORDER_FILLED.value
        assert "BTC-PERP" in notification_data['message']
    
    @patch('services.notification_service.redis_client')
    async def test_notify_position_liquidated(self, mock_redis, notification_service):
        """Test position liquidated notification."""
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.lpush = AsyncMock(return_value=1)
        mock_redis.ltrim = AsyncMock(return_value=True)
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.publish = AsyncMock(return_value=1)
        
        position_data = {'symbol': 'BTC-PERP'}
        
        await notification_service.notify_position_liquidated(
            account_id=1,
            position_data=position_data
        )
        
        # Verify critical priority
        publish_args = mock_redis.publish.call_args[0]
        notification_data = publish_args[1]
        assert notification_data['priority'] == NotificationPriority.CRITICAL.name
        assert "liquidated" in notification_data['message'].lower()
    
    @patch('services.notification_service.redis_client')
    async def test_notify_margin_call(self, mock_redis, notification_service):
        """Test margin call notification."""
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.lpush = AsyncMock(return_value=1)
        mock_redis.ltrim = AsyncMock(return_value=True)
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.publish = AsyncMock(return_value=1)
        
        margin_data = {'margin_level': 25.5}
        
        await notification_service.notify_margin_call(account_id=1, margin_data=margin_data)
        
        # Verify critical priority and message
        publish_args = mock_redis.publish.call_args[0]
        notification_data = publish_args[1]
        assert notification_data['priority'] == NotificationPriority.CRITICAL.name
        assert "25.5%" in notification_data['message']
        assert "Margin Call" in notification_data['title']


@pytest.mark.asyncio
@pytest.mark.unit
class TestNotificationPreferences:
    """Test cases for NotificationPreferences."""
    
    @pytest.fixture
    def preferences(self):
        """Create preferences instance."""
        return NotificationPreferences()
    
    @patch('services.notification_service.redis_client')
    async def test_get_preferences_default(self, mock_redis, preferences):
        """Test getting default preferences."""
        mock_redis.get = AsyncMock(return_value=None)
        
        prefs = await preferences.get_preferences(account_id=1)
        
        assert prefs['email_enabled'] is True
        assert prefs['push_enabled'] is True
        assert prefs['order_notifications'] is True
        assert prefs['risk_notifications'] is True
        assert prefs['price_alerts'] is False
        assert prefs['min_priority'] == NotificationPriority.LOW.name
    
    @patch('services.notification_service.redis_client')
    async def test_get_preferences_custom(self, mock_redis, preferences):
        """Test getting custom preferences."""
        custom_prefs = {
            'email_enabled': False,
            'push_enabled': True,
            'order_notifications': False,
            'min_priority': NotificationPriority.HIGH.name
        }
        mock_redis.get = AsyncMock(return_value=custom_prefs)
        
        prefs = await preferences.get_preferences(account_id=1)
        
        assert prefs['email_enabled'] is False
        assert prefs['order_notifications'] is False
        assert prefs['min_priority'] == NotificationPriority.HIGH.name
    
    @patch('services.notification_service.redis_client')
    async def test_update_preferences(self, mock_redis, preferences):
        """Test updating preferences."""
        mock_redis.set = AsyncMock(return_value=True)
        
        new_prefs = {
            'email_enabled': False,
            'price_alerts': True
        }
        
        result = await preferences.update_preferences(account_id=1, preferences=new_prefs)
        
        assert result is True
        mock_redis.set.assert_called_once_with("notification_prefs:1", new_prefs)
    
    @patch('services.notification_service.redis_client')
    async def test_should_send_notification_yes(self, mock_redis, preferences):
        """Test notification should be sent based on preferences."""
        prefs = {
            'order_notifications': True,
            'min_priority': NotificationPriority.LOW.name
        }
        mock_redis.get = AsyncMock(return_value=prefs)
        
        result = await preferences.should_send_notification(
            account_id=1,
            notification_type=NotificationType.ORDER_FILLED,
            priority=NotificationPriority.MEDIUM
        )
        
        assert result is True
    
    @patch('services.notification_service.redis_client')
    async def test_should_send_notification_priority_too_low(self, mock_redis, preferences):
        """Test notification blocked by priority threshold."""
        prefs = {
            'order_notifications': True,
            'min_priority': NotificationPriority.HIGH.name
        }
        mock_redis.get = AsyncMock(return_value=prefs)
        
        result = await preferences.should_send_notification(
            account_id=1,
            notification_type=NotificationType.ORDER_FILLED,
            priority=NotificationPriority.MEDIUM
        )
        
        assert result is False  # MEDIUM < HIGH, so should not send
    
    @patch('services.notification_service.redis_client')
    async def test_should_send_notification_type_disabled(self, mock_redis, preferences):
        """Test notification blocked by type preference."""
        prefs = {
            'order_notifications': False,
            'min_priority': NotificationPriority.LOW.name
        }
        mock_redis.get = AsyncMock(return_value=prefs)
        
        result = await preferences.should_send_notification(
            account_id=1,
            notification_type=NotificationType.ORDER_FILLED,
            priority=NotificationPriority.HIGH
        )
        
        assert result is False  # Order notifications disabled