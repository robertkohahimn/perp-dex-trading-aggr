"""
Notification service for alerts and updates.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum, IntEnum
import asyncio
import logging
from dataclasses import dataclass, asdict
import json

from app.core.redis_client import redis_client
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.accounts import Account

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """Notification types."""
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_PARTIALLY_FILLED = "ORDER_PARTIALLY_FILLED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_REJECTED = "ORDER_REJECTED"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_CLOSED = "POSITION_CLOSED"
    POSITION_LIQUIDATED = "POSITION_LIQUIDATED"
    RISK_ALERT = "RISK_ALERT"
    MARGIN_CALL = "MARGIN_CALL"
    SYSTEM_ALERT = "SYSTEM_ALERT"
    PRICE_ALERT = "PRICE_ALERT"
    TRADE_EXECUTED = "TRADE_EXECUTED"


class NotificationPriority(IntEnum):
    """Notification priority levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Notification:
    """Notification data structure."""
    id: str
    account_id: int
    type: NotificationType
    priority: NotificationPriority
    title: str
    message: str
    data: Dict[str, Any]
    timestamp: datetime
    read: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['type'] = self.type.value
        data['priority'] = self.priority.name  # Use name for string representation
        data['timestamp'] = self.timestamp.isoformat()
        return data


class NotificationService:
    """Service for managing notifications."""
    
    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session
        self.subscribers: Dict[int, List[asyncio.Queue]] = {}
        self.notification_handlers: Dict[NotificationType, List[callable]] = {}
    
    async def send_notification(
        self,
        account_id: int,
        type: NotificationType,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        priority: NotificationPriority = NotificationPriority.MEDIUM
    ) -> str:
        """Send a notification to an account."""
        notification_id = f"{account_id}:{type.value}:{datetime.utcnow().timestamp()}"
        
        notification = Notification(
            id=notification_id,
            account_id=account_id,
            type=type,
            priority=priority,
            title=title,
            message=message,
            data=data or {},
            timestamp=datetime.utcnow()
        )
        
        # Store in Redis
        await self._store_notification(notification)
        
        # Publish to Redis pub/sub for real-time delivery
        await redis_client.publish(
            f"notifications:{account_id}",
            notification.to_dict()
        )
        
        # Add to in-memory queues for WebSocket subscribers
        if account_id in self.subscribers:
            for queue in self.subscribers[account_id]:
                await queue.put(notification)
        
        # Execute registered handlers
        await self._execute_handlers(notification)
        
        # Log critical notifications
        if priority == NotificationPriority.CRITICAL:
            logger.warning(f"Critical notification for account {account_id}: {title} - {message}")
        
        return notification_id
    
    async def get_notifications(
        self,
        account_id: int,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Notification]:
        """Get notifications for an account."""
        # Get from Redis list
        key = f"notifications:list:{account_id}"
        notifications_data = await redis_client.lrange(key, 0, limit - 1)
        
        notifications = []
        for data in notifications_data:
            notification = self._parse_notification(data)
            if not unread_only or not notification.read:
                notifications.append(notification)
        
        return notifications
    
    async def mark_as_read(self, notification_id: str) -> bool:
        """Mark a notification as read."""
        # Get notification
        account_id = notification_id.split(":")[0]
        key = f"notification:{notification_id}"
        
        data = await redis_client.get(key)
        if not data:
            return False
        
        # Update read status
        data['read'] = True
        await redis_client.set(key, data)
        
        return True
    
    async def mark_all_as_read(self, account_id: int) -> int:
        """Mark all notifications as read for an account."""
        notifications = await self.get_notifications(account_id, unread_only=True)
        
        count = 0
        for notification in notifications:
            if await self.mark_as_read(notification.id):
                count += 1
        
        return count
    
    async def delete_notification(self, notification_id: str) -> bool:
        """Delete a notification."""
        key = f"notification:{notification_id}"
        return await redis_client.delete(key)
    
    async def subscribe_to_notifications(self, account_id: int) -> asyncio.Queue:
        """Subscribe to real-time notifications for an account."""
        queue = asyncio.Queue()
        
        if account_id not in self.subscribers:
            self.subscribers[account_id] = []
        
        self.subscribers[account_id].append(queue)
        
        return queue
    
    async def unsubscribe_from_notifications(self, account_id: int, queue: asyncio.Queue):
        """Unsubscribe from notifications."""
        if account_id in self.subscribers:
            if queue in self.subscribers[account_id]:
                self.subscribers[account_id].remove(queue)
            
            if not self.subscribers[account_id]:
                del self.subscribers[account_id]
    
    def register_handler(self, notification_type: NotificationType, handler: callable):
        """Register a handler for a notification type."""
        if notification_type not in self.notification_handlers:
            self.notification_handlers[notification_type] = []
        
        self.notification_handlers[notification_type].append(handler)
    
    # Specific notification methods
    
    async def notify_order_filled(
        self,
        account_id: int,
        order_data: Dict[str, Any]
    ):
        """Send order filled notification."""
        await self.send_notification(
            account_id=account_id,
            type=NotificationType.ORDER_FILLED,
            title="Order Filled",
            message=f"Your {order_data['side']} order for {order_data['symbol']} has been filled at {order_data['price']}",
            data=order_data,
            priority=NotificationPriority.MEDIUM
        )
    
    async def notify_order_cancelled(
        self,
        account_id: int,
        order_data: Dict[str, Any]
    ):
        """Send order cancelled notification."""
        await self.send_notification(
            account_id=account_id,
            type=NotificationType.ORDER_CANCELLED,
            title="Order Cancelled",
            message=f"Your order for {order_data['symbol']} has been cancelled",
            data=order_data,
            priority=NotificationPriority.LOW
        )
    
    async def notify_position_opened(
        self,
        account_id: int,
        position_data: Dict[str, Any]
    ):
        """Send position opened notification."""
        await self.send_notification(
            account_id=account_id,
            type=NotificationType.POSITION_OPENED,
            title="Position Opened",
            message=f"Opened {position_data['side']} position for {position_data['symbol']} at {position_data['entry_price']}",
            data=position_data,
            priority=NotificationPriority.MEDIUM
        )
    
    async def notify_position_closed(
        self,
        account_id: int,
        position_data: Dict[str, Any]
    ):
        """Send position closed notification."""
        pnl = position_data.get('realized_pnl', 0)
        pnl_text = f"Profit: ${pnl:.2f}" if pnl > 0 else f"Loss: ${abs(pnl):.2f}"
        
        await self.send_notification(
            account_id=account_id,
            type=NotificationType.POSITION_CLOSED,
            title="Position Closed",
            message=f"Closed {position_data['symbol']} position. {pnl_text}",
            data=position_data,
            priority=NotificationPriority.MEDIUM
        )
    
    async def notify_position_liquidated(
        self,
        account_id: int,
        position_data: Dict[str, Any]
    ):
        """Send position liquidated notification."""
        await self.send_notification(
            account_id=account_id,
            type=NotificationType.POSITION_LIQUIDATED,
            title="⚠️ Position Liquidated",
            message=f"Your {position_data['symbol']} position has been liquidated",
            data=position_data,
            priority=NotificationPriority.CRITICAL
        )
    
    async def notify_risk_alert(
        self,
        account_id: int,
        alert_data: Dict[str, Any]
    ):
        """Send risk alert notification."""
        await self.send_notification(
            account_id=account_id,
            type=NotificationType.RISK_ALERT,
            title="Risk Alert",
            message=alert_data.get('message', 'Risk threshold exceeded'),
            data=alert_data,
            priority=NotificationPriority.HIGH
        )
    
    async def notify_margin_call(
        self,
        account_id: int,
        margin_data: Dict[str, Any]
    ):
        """Send margin call notification."""
        await self.send_notification(
            account_id=account_id,
            type=NotificationType.MARGIN_CALL,
            title="⚠️ Margin Call",
            message=f"Your margin level is at {margin_data['margin_level']:.1f}%. Please add funds or reduce positions.",
            data=margin_data,
            priority=NotificationPriority.CRITICAL
        )
    
    async def notify_price_alert(
        self,
        account_id: int,
        alert_data: Dict[str, Any]
    ):
        """Send price alert notification."""
        symbol = alert_data['symbol']
        price = alert_data['price']
        condition = alert_data.get('condition', 'reached')
        
        await self.send_notification(
            account_id=account_id,
            type=NotificationType.PRICE_ALERT,
            title="Price Alert",
            message=f"{symbol} has {condition} ${price:.2f}",
            data=alert_data,
            priority=NotificationPriority.LOW
        )
    
    async def notify_system_alert(
        self,
        account_id: int,
        alert_data: Dict[str, Any]
    ):
        """Send system alert notification."""
        await self.send_notification(
            account_id=account_id,
            type=NotificationType.SYSTEM_ALERT,
            title="System Alert",
            message=alert_data.get('message', 'System maintenance or update'),
            data=alert_data,
            priority=NotificationPriority.MEDIUM
        )
    
    # Private helper methods
    
    async def _store_notification(self, notification: Notification):
        """Store notification in Redis."""
        # Store individual notification
        key = f"notification:{notification.id}"
        await redis_client.set(key, notification.to_dict(), expire=86400 * 7)  # Keep for 7 days
        
        # Add to account's notification list
        list_key = f"notifications:list:{notification.account_id}"
        await redis_client.lpush(list_key, notification.to_dict())
        
        # Trim list to keep only recent notifications
        await redis_client.ltrim(list_key, 0, 999)  # Keep last 1000
        
        # Update unread count
        if not notification.read:
            await redis_client.incr(f"notifications:unread:{notification.account_id}")
    
    def _parse_notification(self, data: Dict[str, Any]) -> Notification:
        """Parse notification from stored data."""
        # Handle priority as either string name or int value
        priority = data['priority']
        if isinstance(priority, str):
            priority = NotificationPriority[priority]
        else:
            priority = NotificationPriority(priority)
            
        return Notification(
            id=data['id'],
            account_id=data['account_id'],
            type=NotificationType(data['type']),
            priority=priority,
            title=data['title'],
            message=data['message'],
            data=data.get('data', {}),
            timestamp=datetime.fromisoformat(data['timestamp']),
            read=data.get('read', False)
        )
    
    async def _execute_handlers(self, notification: Notification):
        """Execute registered handlers for a notification."""
        if notification.type in self.notification_handlers:
            for handler in self.notification_handlers[notification.type]:
                try:
                    await handler(notification)
                except Exception as e:
                    logger.error(f"Error executing notification handler: {e}")


# Notification preferences management
class NotificationPreferences:
    """Manage user notification preferences."""
    
    def __init__(self):
        pass
    
    async def get_preferences(self, account_id: int) -> Dict[str, Any]:
        """Get notification preferences for an account."""
        key = f"notification_prefs:{account_id}"
        prefs = await redis_client.get(key)
        
        if not prefs:
            # Return default preferences
            return {
                'email_enabled': True,
                'push_enabled': True,
                'order_notifications': True,
                'position_notifications': True,
                'risk_notifications': True,
                'price_alerts': False,
                'system_notifications': True,
                'min_priority': NotificationPriority.LOW.name
            }
        
        return prefs
    
    async def update_preferences(
        self,
        account_id: int,
        preferences: Dict[str, Any]
    ) -> bool:
        """Update notification preferences."""
        key = f"notification_prefs:{account_id}"
        return await redis_client.set(key, preferences)
    
    async def should_send_notification(
        self,
        account_id: int,
        notification_type: NotificationType,
        priority: NotificationPriority
    ) -> bool:
        """Check if notification should be sent based on preferences."""
        prefs = await self.get_preferences(account_id)
        
        # Check minimum priority
        min_priority_str = prefs.get('min_priority', 'LOW')
        min_priority = NotificationPriority[min_priority_str] if isinstance(min_priority_str, str) else NotificationPriority(min_priority_str)
        if priority < min_priority:
            return False
        
        # Check type-specific preferences
        type_map = {
            NotificationType.ORDER_FILLED: 'order_notifications',
            NotificationType.ORDER_CANCELLED: 'order_notifications',
            NotificationType.POSITION_OPENED: 'position_notifications',
            NotificationType.POSITION_CLOSED: 'position_notifications',
            NotificationType.RISK_ALERT: 'risk_notifications',
            NotificationType.MARGIN_CALL: 'risk_notifications',
            NotificationType.PRICE_ALERT: 'price_alerts',
            NotificationType.SYSTEM_ALERT: 'system_notifications'
        }
        
        pref_key = type_map.get(notification_type, 'system_notifications')
        return prefs.get(pref_key, True)