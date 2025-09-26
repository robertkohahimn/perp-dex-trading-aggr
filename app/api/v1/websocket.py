"""
WebSocket endpoints for real-time updates.
"""
from fastapi import WebSocket, WebSocketDisconnect, Depends, Query
from typing import Dict, Set, Optional
import json
import asyncio
import logging
from datetime import datetime

from app.core.auth import auth_service
from app.core.redis_client import redis_client
from services.market_data_service import MarketDataService
from services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.user_connections: Dict[int, Set[WebSocket]] = {}
        self.market_data_service = MarketDataService()
        self.notification_service = NotificationService()
    
    async def connect(self, websocket: WebSocket, client_id: str, user_id: Optional[int] = None):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        
        if client_id not in self.active_connections:
            self.active_connections[client_id] = set()
        self.active_connections[client_id].add(websocket)
        
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(websocket)
        
        logger.info(f"WebSocket connected: {client_id} (user: {user_id})")
    
    def disconnect(self, websocket: WebSocket, client_id: str, user_id: Optional[int] = None):
        """Remove a WebSocket connection."""
        if client_id in self.active_connections:
            self.active_connections[client_id].discard(websocket)
            if not self.active_connections[client_id]:
                del self.active_connections[client_id]
        
        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        logger.info(f"WebSocket disconnected: {client_id} (user: {user_id})")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific WebSocket."""
        await websocket.send_text(message)
    
    async def broadcast(self, message: str, client_id: str):
        """Broadcast a message to all connections for a client."""
        if client_id in self.active_connections:
            for connection in self.active_connections[client_id]:
                await connection.send_text(message)
    
    async def broadcast_to_user(self, message: str, user_id: int):
        """Broadcast a message to all connections for a user."""
        if user_id in self.user_connections:
            for connection in self.user_connections[user_id]:
                await connection.send_text(message)


# Global connection manager
manager = ConnectionManager()


async def get_current_user_from_token(token: str) -> Optional[int]:
    """Get user ID from WebSocket token."""
    try:
        payload = auth_service.verify_token(token)
        user_id = payload.get("sub")
        # In a real app, you'd fetch the user from DB
        # For now, return a mock user ID
        return 1 if user_id else None
    except Exception:
        return None


async def handle_market_data_subscription(
    websocket: WebSocket,
    symbols: list,
    dexes: list
):
    """Handle market data subscriptions."""
    async def send_update(data):
        await websocket.send_json({
            "type": "market_data",
            "data": data.to_dict() if hasattr(data, 'to_dict') else data
        })
    
    subscriptions = []
    for symbol in symbols:
        for dex in dexes:
            sub_id = await manager.market_data_service.subscribe_to_market_data(
                symbol=symbol,
                dex=dex,
                callback=send_update
            )
            subscriptions.append(sub_id)
    
    return subscriptions


async def handle_notifications(websocket: WebSocket, user_id: int):
    """Handle notification subscriptions."""
    queue = await manager.notification_service.subscribe_to_notifications(user_id)
    
    async def send_notifications():
        while True:
            try:
                notification = await queue.get()
                await websocket.send_json({
                    "type": "notification",
                    "data": notification.to_dict()
                })
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error sending notification: {e}")
    
    task = asyncio.create_task(send_notifications())
    return queue, task


# WebSocket endpoints

async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """Main WebSocket endpoint for real-time updates."""
    client_id = f"ws_{id(websocket)}"
    user_id = None
    subscriptions = []
    notification_queue = None
    notification_task = None
    
    # Authenticate if token provided
    if token:
        user_id = await get_current_user_from_token(token)
        if not user_id:
            await websocket.close(code=1008, reason="Invalid token")
            return
    
    await manager.connect(websocket, client_id, user_id)
    
    try:
        # Set up notification subscription if authenticated
        if user_id:
            notification_queue, notification_task = await handle_notifications(
                websocket, user_id
            )
        
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "data": {
                "client_id": client_id,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        
        # Handle incoming messages
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "ping":
                await websocket.send_json({"type": "pong"})
            
            elif message["type"] == "subscribe":
                # Subscribe to market data
                if "symbols" in message and "dexes" in message:
                    subs = await handle_market_data_subscription(
                        websocket,
                        message["symbols"],
                        message["dexes"]
                    )
                    subscriptions.extend(subs)
                    
                    await websocket.send_json({
                        "type": "subscribed",
                        "data": {
                            "symbols": message["symbols"],
                            "dexes": message["dexes"]
                        }
                    })
            
            elif message["type"] == "unsubscribe":
                # Unsubscribe from market data
                for sub_id in subscriptions:
                    await manager.market_data_service.unsubscribe(sub_id)
                subscriptions.clear()
                
                await websocket.send_json({
                    "type": "unsubscribed"
                })
            
            elif message["type"] == "order":
                # Handle order commands if authenticated
                if user_id:
                    # This would call the order service
                    await websocket.send_json({
                        "type": "order_response",
                        "data": {"status": "received"}
                    })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Authentication required"
                    })
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Clean up subscriptions
        for sub_id in subscriptions:
            await manager.market_data_service.unsubscribe(sub_id)
        
        # Clean up notification subscription
        if notification_task:
            notification_task.cancel()
        if notification_queue and user_id:
            await manager.notification_service.unsubscribe_from_notifications(
                user_id, notification_queue
            )
        
        manager.disconnect(websocket, client_id, user_id)


async def websocket_market_data(
    websocket: WebSocket,
    symbol: str,
    dex: str
):
    """WebSocket endpoint for specific market data stream."""
    client_id = f"market_{symbol}_{dex}_{id(websocket)}"
    
    await manager.connect(websocket, client_id)
    
    try:
        # Subscribe to market data
        async def send_update(data):
            await websocket.send_json({
                "symbol": symbol,
                "dex": dex,
                "data": data.to_dict() if hasattr(data, 'to_dict') else data,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        sub_id = await manager.market_data_service.subscribe_to_market_data(
            symbol=symbol,
            dex=dex,
            callback=send_update
        )
        
        # Keep connection alive
        while True:
            await asyncio.sleep(30)
            await websocket.send_json({"type": "heartbeat"})
            
    except WebSocketDisconnect:
        logger.info(f"Market data WebSocket disconnected: {client_id}")
    except Exception as e:
        logger.error(f"Market data WebSocket error: {e}")
    finally:
        await manager.market_data_service.unsubscribe(sub_id)
        manager.disconnect(websocket, client_id)


async def websocket_notifications(
    websocket: WebSocket,
    token: str
):
    """WebSocket endpoint for user notifications."""
    # Authenticate
    user_id = await get_current_user_from_token(token)
    if not user_id:
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    client_id = f"notifications_{user_id}_{id(websocket)}"
    await manager.connect(websocket, client_id, user_id)
    
    try:
        # Subscribe to notifications
        queue = await manager.notification_service.subscribe_to_notifications(user_id)
        
        # Send existing unread notifications
        unread = await manager.notification_service.get_notifications(
            user_id, unread_only=True
        )
        for notification in unread:
            await websocket.send_json(notification.to_dict())
        
        # Stream new notifications
        while True:
            notification = await queue.get()
            await websocket.send_json(notification.to_dict())
            
    except WebSocketDisconnect:
        logger.info(f"Notification WebSocket disconnected: {client_id}")
    except Exception as e:
        logger.error(f"Notification WebSocket error: {e}")
    finally:
        await manager.notification_service.unsubscribe_from_notifications(
            user_id, queue
        )
        manager.disconnect(websocket, client_id, user_id)