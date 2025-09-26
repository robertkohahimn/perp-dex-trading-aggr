"""Extended DEX connector implementation using x10 SDK.

Extended is a derivatives DEX on Starknet. This implementation uses the official
x10-python-trading-starknet SDK.
"""

import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional
from datetime import datetime

from x10.perpetual.accounts import StarkPerpetualAccount
from x10.perpetual.configuration import TESTNET_CONFIG, MAINNET_CONFIG, EndpointConfig
from x10.perpetual.simple_client.simple_trading_client import BlockingTradingClient
from x10.perpetual.orders import OrderSide, OrderStatus
from x10.perpetual.trading_client.markets_information_module import MarketsInformationModule
from x10.perpetual.trading_client.order_management_module import OrderManagementModule
from x10.perpetual.trading_client.account_module import AccountModule

from connectors.base import BaseConnector, ConnectorConfig
from app.core.exceptions import (
    AuthenticationError,
    InsufficientBalanceError,
    InvalidOrderError,
    OrderNotFoundError,
    OrderExecutionError,
    RateLimitError,
    ConnectorError
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class ExtendedConnector(BaseConnector):
    """Connector for Extended DEX on Starknet using x10 SDK."""
    
    def __init__(self, config: ConnectorConfig):
        """Initialize Extended connector.
        
        Args:
            config: Connector configuration
        """
        super().__init__(config)
        self.name = "Extended"
        self.endpoint_config: Optional[EndpointConfig] = None
        self.account: Optional[StarkPerpetualAccount] = None
        self.client: Optional[BlockingTradingClient] = None
        self.markets_module: Optional[MarketsInformationModule] = None
        self.orders_module: Optional[OrderManagementModule] = None
        self.account_module: Optional[AccountModule] = None
        self._connected = False
        self._markets_cache: Dict[str, Any] = {}
        
    async def connect(self, **credentials) -> bool:
        """Connect to Extended DEX.
        
        Args:
            **credentials: Should include:
                - private_key: Starknet private key (hex)
                - public_key: Starknet public key (hex) 
                - vault: Vault ID (int or hex string)
                - api_key: X10 API key
        
        Returns:
            True if connection successful
        """
        try:
            # Get credentials
            private_key = credentials.get("private_key")
            public_key = credentials.get("public_key")
            vault = credentials.get("vault", credentials.get("account_address"))  # vault or account_address
            api_key = credentials.get("api_key")
            
            if not all([private_key, public_key, vault, api_key]):
                raise AuthenticationError("private_key, public_key, vault/account_address, and api_key are required")
            
            # Select endpoint config
            self.endpoint_config = TESTNET_CONFIG if self.config.testnet else MAINNET_CONFIG
            
            # Create account
            self.account = StarkPerpetualAccount(
                vault=vault,
                private_key=private_key,
                public_key=public_key,
                api_key=api_key
            )
            
            # Initialize modules
            self.markets_module = MarketsInformationModule(
                self.endpoint_config, 
                api_key=api_key
            )
            self.orders_module = OrderManagementModule(
                self.endpoint_config,
                api_key=api_key
            )
            self.account_module = AccountModule(
                self.endpoint_config,
                api_key=api_key,
                stark_account=self.account
            )
            
            # Create blocking client for simpler operations
            self.client = await BlockingTradingClient.create(
                self.endpoint_config,
                self.account
            )
            
            # Test connection by getting markets
            markets = await self.markets_module.get_all_markets()
            for market in markets:
                self._markets_cache[market.name] = market
            
            self._connected = True
            network = "testnet" if self.config.testnet else "mainnet"
            logger.info(f"Connected to Extended DEX ({network})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Extended: {e}")
            self._connected = False
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from Extended DEX."""
        try:
            # Clean up client
            if self.client:
                # BlockingTradingClient doesn't have explicit disconnect
                self.client = None
            
            self.account = None
            self.markets_module = None
            self.orders_module = None
            self.account_module = None
            self._connected = False
            logger.info("Disconnected from Extended DEX")
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting from Extended: {e}")
            return False
    
    async def authenticate(self, **credentials) -> bool:
        """Authenticate with Extended.
        
        Args:
            **credentials: Private key, public key, vault, and API key
            
        Returns:
            True if authenticated
        """
        return await self.connect(**credentials)
    
    async def place_order(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        order_type: str = "limit",
        price: Optional[Decimal] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Place an order.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTC-USD")
            side: Order side ('buy' or 'sell')
            size: Order size
            order_type: Order type ('limit' or 'market')
            price: Order price (required for limit orders)
            **kwargs: Additional order parameters
            
        Returns:
            Order details
        """
        if not self.client:
            raise ConnectorError("Not connected to Extended")
        
        try:
            # Get market
            market = self._get_market(symbol)
            if not market:
                raise InvalidOrderError(f"Market {symbol} not found")
            
            # Determine order side
            order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
            
            # Place order using blocking client
            if order_type.lower() == "market":
                result = await self.client.place_market_order(
                    market_name=market.name,
                    amount_of_synthetic=size,
                    side=order_side,
                    reduce_only=kwargs.get("reduce_only", False)
                )
            else:
                if not price:
                    raise InvalidOrderError("Price required for limit orders")
                    
                result = await self.client.place_order(
                    market_name=market.name,
                    amount_of_synthetic=size,
                    price=price,
                    side=order_side,
                    post_only=kwargs.get("post_only", False),
                    reduce_only=kwargs.get("reduce_only", False)
                )
            
            return {
                "id": result.order_id,
                "symbol": symbol,
                "side": side,
                "price": price or result.price,
                "size": size,
                "type": order_type,
                "status": "open",
                "created_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to place order on Extended: {e}")
            raise OrderExecutionError(f"Failed to place order: {e}")
    
    async def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        """Cancel an order.
        
        Args:
            order_id: Order ID to cancel
            symbol: Trading pair symbol
            
        Returns:
            True if order canceled successfully
        """
        if not self.client:
            raise ConnectorError("Not connected to Extended")
        
        try:
            await self.client.cancel_order(order_id)
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel order on Extended: {e}")
            return False
    
    async def get_order(self, order_id: str, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Get order details.
        
        Args:
            order_id: Order ID
            symbol: Trading pair symbol
            
        Returns:
            Order details
        """
        if not self.orders_module:
            raise ConnectorError("Not connected to Extended")
        
        try:
            # Get order from orders module
            orders = await self.orders_module.get_all_orders()
            
            for order in orders:
                if order.order_id == order_id:
                    return {
                        "id": order.order_id,
                        "symbol": self._get_symbol_from_market_name(order.market),
                        "side": "buy" if order.side == OrderSide.BUY else "sell",
                        "price": Decimal(str(order.price)),
                        "size": Decimal(str(order.quantity)),
                        "filled": Decimal(str(order.quantity_filled)),
                        "status": self._map_order_status(order.status),
                        "type": order.type.lower() if hasattr(order, 'type') else "limit",
                        "created_at": order.created_at if hasattr(order, 'created_at') else datetime.now().isoformat()
                    }
            
            raise OrderNotFoundError(f"Order {order_id} not found")
            
        except Exception as e:
            logger.error(f"Failed to get order from Extended: {e}")
            raise OrderNotFoundError(f"Order {order_id} not found")
    
    async def get_orders(
        self, 
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get orders.
        
        Args:
            symbol: Optional trading pair symbol to filter by
            status: Optional status filter
            limit: Maximum number of orders to return
            
        Returns:
            List of orders
        """
        if not self.orders_module:
            raise ConnectorError("Not connected to Extended")
        
        try:
            # Get all orders
            orders = await self.orders_module.get_all_orders()
            
            # Filter by symbol if provided
            if symbol:
                market = self._get_market(symbol)
                if market:
                    orders = [o for o in orders if o.market == market.name]
            
            # Filter by status if provided
            if status:
                target_status = self._map_status_to_sdk(status)
                orders = [o for o in orders if o.status == target_status]
            
            # Limit results
            orders = orders[:limit]
            
            return [
                {
                    "id": order.order_id,
                    "symbol": self._get_symbol_from_market_name(order.market),
                    "side": "buy" if order.side == OrderSide.BUY else "sell",
                    "price": Decimal(str(order.price)),
                    "size": Decimal(str(order.quantity)),
                    "filled": Decimal(str(order.quantity_filled)),
                    "status": self._map_order_status(order.status),
                    "type": order.type.lower() if hasattr(order, 'type') else "limit",
                    "created_at": order.created_at if hasattr(order, 'created_at') else datetime.now().isoformat()
                }
                for order in orders
            ]
            
        except Exception as e:
            logger.error(f"Failed to get orders from Extended: {e}")
            return []
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open orders.
        
        Args:
            symbol: Optional trading pair symbol to filter by
            
        Returns:
            List of open orders
        """
        if not self.orders_module:
            raise ConnectorError("Not connected to Extended")
        
        try:
            # Get open orders
            open_orders = await self.orders_module.get_open_orders()
            
            # Filter by symbol if provided
            if symbol:
                market = self._get_market(symbol)
                if market:
                    open_orders = [o for o in open_orders if o.market == market.name]
            
            return [
                {
                    "id": order.order_id,
                    "symbol": self._get_symbol_from_market_name(order.market),
                    "side": "buy" if order.side == OrderSide.BUY else "sell",
                    "price": Decimal(str(order.price)),
                    "size": Decimal(str(order.quantity)),
                    "filled": Decimal(str(order.quantity_filled)),
                    "status": "open",
                    "type": order.type.lower() if hasattr(order, 'type') else "limit",
                    "created_at": order.created_at if hasattr(order, 'created_at') else datetime.now().isoformat()
                }
                for order in open_orders
            ]
            
        except Exception as e:
            logger.error(f"Failed to get open orders from Extended: {e}")
            return []
    
    async def modify_order(
        self,
        order_id: str,
        symbol: Optional[str] = None,
        price: Optional[Decimal] = None,
        size: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """Modify an existing order.
        
        Note: x10 SDK doesn't support direct order modification,
        so we cancel and replace the order.
        
        Args:
            order_id: Order ID to modify
            symbol: Trading pair symbol
            price: New price (optional)
            size: New size (optional)
            
        Returns:
            Modified order details
        """
        if not self.client:
            raise ConnectorError("Not connected to Extended")
        
        try:
            # Get existing order
            order = await self.get_order(order_id)
            
            # Cancel existing order
            await self.cancel_order(order_id)
            
            # Place new order with modified parameters
            return await self.place_order(
                symbol=order["symbol"],
                side=order["side"],
                size=size or order["size"],
                order_type=order["type"],
                price=price or order["price"]
            )
            
        except Exception as e:
            logger.error(f"Failed to modify order on Extended: {e}")
            raise OrderExecutionError(f"Failed to modify order: {e}")
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get positions.
        
        Args:
            symbol: Optional trading pair symbol to filter by
            
        Returns:
            List of positions
        """
        if not self.account_module:
            raise ConnectorError("Not connected to Extended")
        
        try:
            # Get positions
            positions = await self.account_module.get_positions()
            
            # Filter by symbol if provided
            if symbol:
                market = self._get_market(symbol)
                if market:
                    positions = [p for p in positions if p.market == market.name]
            
            return [
                {
                    "symbol": self._get_symbol_from_market_name(pos.market),
                    "side": "long" if pos.side == "LONG" else "short",
                    "size": abs(Decimal(str(pos.size))),
                    "entry_price": Decimal(str(pos.avg_entry_price)),
                    "mark_price": Decimal(str(pos.mark_price)) if hasattr(pos, 'mark_price') else Decimal("0"),
                    "unrealized_pnl": Decimal(str(pos.unrealized_pnl)),
                    "realized_pnl": Decimal(str(pos.realized_pnl)) if hasattr(pos, 'realized_pnl') else Decimal("0"),
                    "margin": Decimal(str(pos.margin)) if hasattr(pos, 'margin') else Decimal("0")
                }
                for pos in positions
            ]
            
        except Exception as e:
            logger.error(f"Failed to get positions from Extended: {e}")
            return []
    
    async def close_position(
        self,
        symbol: str,
        size: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """Close a position.
        
        Args:
            symbol: Trading pair symbol
            size: Size to close (None for full position)
            
        Returns:
            Close order details
        """
        if not self.client:
            raise ConnectorError("Not connected to Extended")
        
        try:
            # Get current position
            positions = await self.get_positions(symbol)
            if not positions:
                raise InvalidOrderError(f"No position found for {symbol}")
            
            position = positions[0]
            close_size = size or position["size"]
            
            # Place opposite market order to close
            return await self.place_order(
                symbol=symbol,
                side="sell" if position["side"] == "long" else "buy",
                size=close_size,
                order_type="market",
                reduce_only=True
            )
            
        except Exception as e:
            logger.error(f"Failed to close position on Extended: {e}")
            raise OrderExecutionError(f"Failed to close position: {e}")
    
    async def get_balance(self, asset: str = "USDC") -> Dict[str, Any]:
        """Get account balance.
        
        Args:
            asset: Asset to get balance for
            
        Returns:
            Balance information
        """
        if not self.account_module:
            raise ConnectorError("Not connected to Extended")
        
        try:
            # Get account details
            account = await self.account_module.get_account()
            
            # Extract balance information
            total = Decimal(str(account.equity)) if hasattr(account, 'equity') else Decimal("0")
            available = Decimal(str(account.free_collateral)) if hasattr(account, 'free_collateral') else Decimal("0")
            
            return {
                "asset": asset,
                "total": total,
                "free": available,
                "locked": total - available
            }
            
        except Exception as e:
            logger.error(f"Failed to get balance from Extended: {e}")
            return {"asset": asset, "total": Decimal("0"), "free": Decimal("0"), "locked": Decimal("0")}
    
    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information.
        
        Returns:
            Account information
        """
        if not self.account_module:
            raise ConnectorError("Not connected to Extended")
        
        try:
            # Get account details
            account = await self.account_module.get_account()
            balance = await self.get_balance()
            positions = await self.get_positions()
            
            return {
                "account_id": str(self.account.vault) if self.account else "unknown",
                "balance": balance,
                "positions": positions,
                "margin_usage": Decimal(str(account.margin_usage)) if hasattr(account, 'margin_usage') else Decimal("0"),
                "available_margin": balance.get("free", Decimal("0")),
                "equity": Decimal(str(account.equity)) if hasattr(account, 'equity') else Decimal("0")
            }
            
        except Exception as e:
            logger.error(f"Failed to get account info from Extended: {e}")
            return {}
    
    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get market data.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Market data
        """
        if not self.markets_module:
            raise ConnectorError("Not connected to Extended")
        
        try:
            # Get market
            market = self._get_market(symbol)
            if not market:
                raise InvalidOrderError(f"Market {symbol} not found")
            
            # Get ticker data
            ticker = await self.markets_module.get_ticker(market.name)
            
            return {
                "symbol": symbol,
                "last_price": Decimal(str(ticker.last_price)),
                "bid": Decimal(str(ticker.best_bid)),
                "ask": Decimal(str(ticker.best_ask)),
                "volume_24h": Decimal(str(ticker.volume_24h)),
                "high_24h": Decimal(str(ticker.high_24h)) if hasattr(ticker, 'high_24h') else Decimal("0"),
                "low_24h": Decimal(str(ticker.low_24h)) if hasattr(ticker, 'low_24h') else Decimal("0"),
                "open_interest": Decimal(str(ticker.open_interest)) if hasattr(ticker, 'open_interest') else Decimal("0"),
                "funding_rate": Decimal(str(ticker.funding_rate)) if hasattr(ticker, 'funding_rate') else Decimal("0")
            }
            
        except Exception as e:
            logger.error(f"Failed to get market data from Extended: {e}")
            return {}
    
    async def get_order_book(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        """Get order book.
        
        Args:
            symbol: Trading pair symbol
            depth: Order book depth
            
        Returns:
            Order book data
        """
        if not self.markets_module:
            raise ConnectorError("Not connected to Extended")
        
        try:
            # Get market
            market = self._get_market(symbol)
            if not market:
                raise InvalidOrderError(f"Market {symbol} not found")
            
            # Get order book
            orderbook = await self.markets_module.get_orderbook(market.name)
            
            # Process bids and asks
            bids = []
            asks = []
            
            if hasattr(orderbook, 'bids'):
                for bid in orderbook.bids[:depth]:
                    bids.append([
                        Decimal(str(bid.price)),
                        Decimal(str(bid.quantity))
                    ])
            
            if hasattr(orderbook, 'asks'):
                for ask in orderbook.asks[:depth]:
                    asks.append([
                        Decimal(str(ask.price)),
                        Decimal(str(ask.quantity))
                    ])
            
            return {
                "symbol": symbol,
                "bids": bids,
                "asks": asks,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get order book from Extended: {e}")
            return {"symbol": symbol, "bids": [], "asks": [], "timestamp": datetime.now().isoformat()}
    
    async def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent trades.
        
        Args:
            symbol: Trading pair symbol
            limit: Maximum number of trades
            
        Returns:
            List of recent trades
        """
        if not self.markets_module:
            raise ConnectorError("Not connected to Extended")
        
        try:
            # Get market
            market = self._get_market(symbol)
            if not market:
                raise InvalidOrderError(f"Market {symbol} not found")
            
            # Get trades
            trades = await self.markets_module.get_recent_trades(market.name, limit)
            
            return [
                {
                    "id": trade.trade_id if hasattr(trade, 'trade_id') else str(i),
                    "price": Decimal(str(trade.price)),
                    "size": Decimal(str(trade.quantity)),
                    "side": trade.side.lower() if hasattr(trade, 'side') else "buy",
                    "timestamp": trade.timestamp if hasattr(trade, 'timestamp') else datetime.now().isoformat()
                }
                for i, trade in enumerate(trades[:limit])
            ]
            
        except Exception as e:
            logger.error(f"Failed to get recent trades from Extended: {e}")
            return []
    
    async def get_funding_rate(self, symbol: str) -> Dict[str, Any]:
        """Get funding rate.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Funding rate information
        """
        if not self.markets_module:
            raise ConnectorError("Not connected to Extended")
        
        try:
            # Get market
            market = self._get_market(symbol)
            if not market:
                raise InvalidOrderError(f"Market {symbol} not found")
            
            # Get funding info
            funding = await self.markets_module.get_funding_info(market.name)
            
            return {
                "symbol": symbol,
                "funding_rate": Decimal(str(funding.rate)) if hasattr(funding, 'rate') else Decimal("0"),
                "next_funding_time": funding.next_funding_time if hasattr(funding, 'next_funding_time') else datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get funding rate from Extended: {e}")
            return {"symbol": symbol, "funding_rate": Decimal("0")}
    
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for a symbol.
        
        Args:
            symbol: Trading pair symbol
            leverage: Leverage value
            
        Returns:
            True if successful
        """
        if not self.account_module:
            raise ConnectorError("Not connected to Extended")
        
        try:
            # Get market
            market = self._get_market(symbol)
            if not market:
                raise InvalidOrderError(f"Market {symbol} not found")
            
            # Set leverage
            await self.account_module.set_leverage(market.name, leverage)
            return True
            
        except Exception as e:
            logger.error(f"Failed to set leverage on Extended: {e}")
            return False
    
    async def subscribe_to_updates(self, symbols: List[str], callbacks: Dict) -> bool:
        """Subscribe to market updates (WebSocket).
        
        Args:
            symbols: List of symbols to subscribe to
            callbacks: Dict of callback functions
            
        Returns:
            True if subscription successful
        """
        # The x10 SDK has stream support through PerpetualStreamClient
        # This would be implemented using the stream_client module
        logger.warning("WebSocket subscriptions not yet fully implemented for Extended SDK")
        return False
    
    async def unsubscribe_from_updates(self, symbols: List[str]) -> bool:
        """Unsubscribe from market updates.
        
        Args:
            symbols: List of symbols to unsubscribe from
            
        Returns:
            True if unsubscription successful
        """
        logger.warning("WebSocket unsubscriptions not yet fully implemented for Extended SDK")
        return False
    
    def _get_market(self, symbol: str) -> Optional[Any]:
        """Get market object by symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTC-USD")
            
        Returns:
            Market object or None
        """
        # Try exact match first
        if symbol in self._markets_cache:
            return self._markets_cache[symbol]
        
        # Try with -PERP suffix
        market_name = f"{symbol}-PERP"
        if market_name in self._markets_cache:
            return self._markets_cache[market_name]
        
        # Try uppercase
        symbol_upper = symbol.upper()
        if symbol_upper in self._markets_cache:
            return self._markets_cache[symbol_upper]
        
        # Try uppercase with -PERP
        market_name_upper = f"{symbol_upper}-PERP"
        if market_name_upper in self._markets_cache:
            return self._markets_cache[market_name_upper]
        
        return None
    
    def _get_symbol_from_market_name(self, market_name: str) -> str:
        """Convert market name to symbol.
        
        Args:
            market_name: Extended market name
            
        Returns:
            Symbol
        """
        # Remove -PERP suffix if present
        if market_name.endswith("-PERP"):
            return market_name[:-5]
        return market_name
    
    def _map_order_status(self, status: OrderStatus) -> str:
        """Map SDK order status to standard status.
        
        Args:
            status: SDK OrderStatus
            
        Returns:
            Standard status string
        """
        status_map = {
            OrderStatus.PENDING: "pending",
            OrderStatus.OPEN: "open",
            OrderStatus.FILLED: "filled",
            OrderStatus.CANCELED: "canceled",
            OrderStatus.REJECTED: "rejected"
        }
        return status_map.get(status, "unknown")
    
    def _map_status_to_sdk(self, status: str) -> OrderStatus:
        """Map standard status to SDK OrderStatus.
        
        Args:
            status: Standard status string
            
        Returns:
            SDK OrderStatus
        """
        status_map = {
            "pending": OrderStatus.PENDING,
            "open": OrderStatus.OPEN,
            "filled": OrderStatus.FILLED,
            "canceled": OrderStatus.CANCELED,
            "cancelled": OrderStatus.CANCELED,
            "rejected": OrderStatus.REJECTED
        }
        return status_map.get(status.lower(), OrderStatus.OPEN)