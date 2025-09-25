"""
Mock DEX connector for testing and development.
"""
from typing import Dict, List, Optional, AsyncIterator
from datetime import datetime
import asyncio
import random

from ..base import (
    BaseConnector, ConnectorConfig, ConnectorException,
    OrderRequest, OrderResponse, Order, Position, AccountInfo,
    MarketData, OrderBook, OrderSide, OrderType, OrderStatus,
    TimeInForce, PositionSide
)


class MockConnector(BaseConnector):
    """Mock connector for testing and development."""
    
    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.authenticated = False
        self.orders = []
        self.positions = []
        self.order_counter = 1
    
    async def connect(self) -> None:
        """Connect to the mock exchange."""
        await super().connect()
        self.authenticated = False
        self.logger.info("Connected to Mock DEX")
    
    async def disconnect(self) -> None:
        """Disconnect from the mock exchange."""
        await super().disconnect()
        self.authenticated = False
        self.logger.info("Disconnected from Mock DEX")
    
    async def authenticate(self, credentials: Optional[Dict] = None) -> bool:
        """Mock authentication."""
        creds = credentials or {
            "api_key": self.config.api_key,
            "api_secret": self.config.api_secret
        }
        
        # Simulate authentication delay
        await asyncio.sleep(0.1)
        
        # Always succeed for mock
        self.authenticated = True
        self.logger.info("Authenticated with Mock DEX")
        return True
    
    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """Place a mock order."""
        if not self.authenticated:
            raise ConnectorException("Not authenticated")
        
        # Generate order ID
        order_id = f"mock-order-{self.order_counter}"
        self.order_counter += 1
        
        # Create mock order
        mock_order = Order(
            order_id=order_id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            size=order.size,
            price=order.price or 50000.0,  # Default price for market orders
            status=OrderStatus.OPEN,
            filled_size=0.0,
            timestamp=datetime.now()
        )
        
        self.orders.append(mock_order)
        
        # Simulate partial fill for market orders
        if order.order_type == OrderType.MARKET:
            mock_order.filled_size = order.size * 0.5
            mock_order.status = OrderStatus.PARTIALLY_FILLED
        
        return OrderResponse(
            success=True,
            order_id=order_id,
            message="Mock order placed successfully",
            filled_size=mock_order.filled_size,
            average_price=mock_order.price
        )
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a mock order."""
        if not self.authenticated:
            raise ConnectorException("Not authenticated")
        
        for order in self.orders:
            if order.order_id == order_id:
                if order.status == OrderStatus.OPEN:
                    order.status = OrderStatus.CANCELLED
                    return True
        
        return False
    
    async def modify_order(
        self, 
        order_id: str, 
        modifications: Dict
    ) -> OrderResponse:
        """Modify a mock order."""
        if not self.authenticated:
            raise ConnectorException("Not authenticated")
        
        for order in self.orders:
            if order.order_id == order_id:
                # Apply modifications
                if "size" in modifications:
                    order.size = modifications["size"]
                if "price" in modifications:
                    order.price = modifications["price"]
                
                return OrderResponse(
                    success=True,
                    order_id=order_id,
                    message="Mock order modified successfully"
                )
        
        return OrderResponse(
            success=False,
            order_id=order_id,
            message="Order not found"
        )
    
    async def get_orders(
        self, 
        status: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Order]:
        """Get mock orders."""
        if not self.authenticated:
            raise ConnectorException("Not authenticated")
        
        orders = self.orders
        
        # Filter by status
        if status:
            if status == "open":
                orders = [o for o in orders if o.status in [OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]]
            elif status == "closed":
                orders = [o for o in orders if o.status in [OrderStatus.FILLED, OrderStatus.CANCELLED]]
        
        # Filter by symbol
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        
        return orders[:limit]
    
    async def get_positions(
        self,
        symbol: Optional[str] = None
    ) -> List[Position]:
        """Get mock positions."""
        if not self.authenticated:
            raise ConnectorException("Not authenticated")
        
        # Generate some mock positions if empty
        if not self.positions and not symbol:
            self.positions = [
                Position(
                    symbol="BTC-PERP",
                    side=PositionSide.LONG,
                    size=0.1,
                    entry_price=50000.0,
                    mark_price=50500.0,
                    unrealized_pnl=50.0,
                    realized_pnl=0.0,
                    margin_used=500.0
                ),
                Position(
                    symbol="ETH-PERP",
                    side=PositionSide.SHORT,
                    size=1.0,
                    entry_price=3000.0,
                    mark_price=2950.0,
                    unrealized_pnl=50.0,
                    realized_pnl=0.0,
                    margin_used=300.0
                )
            ]
        
        positions = self.positions
        
        # Filter by symbol
        if symbol:
            positions = [p for p in positions if p.symbol == symbol]
        
        return positions
    
    async def get_account_info(self) -> AccountInfo:
        """Get mock account information."""
        if not self.authenticated:
            raise ConnectorException("Not authenticated")
        
        # Calculate total margin used
        positions = await self.get_positions()
        total_margin_used = sum(p.margin_used for p in positions)
        total_unrealized_pnl = sum(p.unrealized_pnl for p in positions)
        
        balance = 10000.0 + total_unrealized_pnl
        
        return AccountInfo(
            balance=balance,
            currency="USDC",
            margin_used=total_margin_used,
            available_margin=balance - total_margin_used,
            unrealized_pnl=total_unrealized_pnl,
            realized_pnl=100.0,  # Mock realized PnL
            total_collateral=balance
        )
    
    async def get_market_data(self, symbol: str) -> MarketData:
        """Get mock market data."""
        # Generate random prices around a base price
        base_prices = {
            "BTC-PERP": 50000.0,
            "ETH-PERP": 3000.0,
            "SOL-PERP": 100.0,
        }
        
        base_price = base_prices.get(symbol, 100.0)
        spread = base_price * 0.0001  # 0.01% spread
        
        bid = base_price - spread
        ask = base_price + spread
        last = base_price + random.uniform(-spread * 2, spread * 2)
        
        return MarketData(
            symbol=symbol,
            bid=bid,
            ask=ask,
            last=last,
            volume=random.uniform(1000000, 10000000),
            open_interest=random.uniform(5000000, 50000000),
            funding_rate=random.uniform(-0.0001, 0.0001),
            mark_price=base_price
        )
    
    async def get_order_book(
        self, 
        symbol: str, 
        depth: int = 20
    ) -> OrderBook:
        """Get mock order book."""
        # Generate mock order book around current price
        market_data = await self.get_market_data(symbol)
        
        bids = []
        asks = []
        
        current_bid = market_data.bid
        current_ask = market_data.ask
        tick_size = current_bid * 0.00001  # 0.001% tick size
        
        for i in range(depth):
            # Bids (decreasing price)
            bid_price = current_bid - (i * tick_size)
            bid_size = random.uniform(0.1, 10.0)
            bids.append((bid_price, bid_size))
            
            # Asks (increasing price)
            ask_price = current_ask + (i * tick_size)
            ask_size = random.uniform(0.1, 10.0)
            asks.append((ask_price, ask_size))
        
        return OrderBook(
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=datetime.now()
        )
    
    async def subscribe_to_updates(
        self, 
        channels: List[str]
    ) -> AsyncIterator[Dict]:
        """Mock subscription to real-time updates."""
        if not self.authenticated:
            raise ConnectorException("Not authenticated")
        
        self.logger.info(f"Subscribed to channels: {channels}")
        
        # Generate mock updates
        while self.is_connected:
            await asyncio.sleep(1)  # Update every second
            
            for channel in channels:
                if channel == "orders":
                    # Mock order update
                    if self.orders:
                        order = random.choice(self.orders)
                        yield {
                            "channel": "orders",
                            "data": {
                                "order_id": order.order_id,
                                "status": order.status.value,
                                "filled_size": order.filled_size
                            }
                        }
                
                elif channel == "positions":
                    # Mock position update
                    if self.positions:
                        position = random.choice(self.positions)
                        position.mark_price += random.uniform(-10, 10)
                        position.unrealized_pnl = (
                            (position.mark_price - position.entry_price) * 
                            position.size * 
                            (1 if position.side == PositionSide.LONG else -1)
                        )
                        yield {
                            "channel": "positions",
                            "data": {
                                "symbol": position.symbol,
                                "mark_price": position.mark_price,
                                "unrealized_pnl": position.unrealized_pnl
                            }
                        }
                
                elif channel.startswith("market:"):
                    # Mock market data update
                    symbol = channel.split(":")[1]
                    market_data = await self.get_market_data(symbol)
                    yield {
                        "channel": channel,
                        "data": {
                            "symbol": symbol,
                            "bid": market_data.bid,
                            "ask": market_data.ask,
                            "last": market_data.last,
                            "volume": market_data.volume
                        }
                    }