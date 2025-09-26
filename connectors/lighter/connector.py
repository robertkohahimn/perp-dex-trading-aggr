"""
Lighter DEX connector implementation using the official Python SDK.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any, AsyncIterator
from datetime import datetime
from decimal import Decimal
from eth_account import Account as EthAccount

import lighter
from lighter import (
    ApiClient,
    Configuration,
    SignerClient,
    OrderApi,
    AccountApi,
    TransactionApi,
    InfoApi,
    WsClient,
)

from ..base import (
    BaseConnector,
    ConnectorConfig,
    OrderRequest,
    OrderResponse,
    Order,
    Position,
    AccountInfo,
    MarketData,
    OrderBook,
    OrderBookLevel,
    Trade,
    OrderSide,
    OrderType,
    OrderStatus,
    TimeInForce,
    PositionSide,
    AuthenticationException,
    OrderException,
    ConnectorException,
)

logger = logging.getLogger(__name__)


class LighterConnector(BaseConnector):
    """Lighter DEX connector implementation."""
    
    def __init__(self, config: Optional[ConnectorConfig] = None):
        """Initialize Lighter connector."""
        if config is None:
            config = ConnectorConfig(name="lighter")
        super().__init__(config)
        
        # API endpoints
        self.base_url = (
            "https://testnet.zklighter.elliot.ai" 
            if self.testnet 
            else "https://mainnet.zklighter.elliot.ai"
        )
        
        # SDK clients
        self.api_client: Optional[ApiClient] = None
        self.signer: Optional[SignerClient] = None
        self.order_api: Optional[OrderApi] = None
        self.account_api: Optional[AccountApi] = None
        self.tx_api: Optional[TransactionApi] = None
        self.info_api: Optional[InfoApi] = None
        self.ws_client: Optional[WsClient] = None
        
        # Authentication
        self.private_key: Optional[str] = None
        self.wallet: Optional[EthAccount] = None
        self.address: Optional[str] = None
        
        # Market mappings
        self.symbol_to_market_id: Dict[str, int] = {}
        self.market_id_to_symbol: Dict[int, str] = {}
        
        # Connection state
        self._connected = False
    
    async def connect(self) -> bool:
        """Establish connection to Lighter."""
        try:
            # Configure API client
            config = Configuration(host=self.base_url)
            self.api_client = ApiClient(configuration=config)
            
            # Initialize API modules
            self.order_api = OrderApi(self.api_client)
            self.account_api = AccountApi(self.api_client)
            self.tx_api = TransactionApi(self.api_client)
            self.info_api = InfoApi(self.api_client)
            
            # Build symbol mappings
            await self._build_symbol_mappings()
            
            self._connected = True
            logger.info(f"Connected to Lighter at {self.base_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Lighter: {e}")
            raise ConnectorException(f"Connection failed: {str(e)}")
    
    async def disconnect(self) -> None:
        """Close connection to Lighter."""
        try:
            if self.ws_client:
                await self.ws_client.close()
                self.ws_client = None
            
            if self.api_client:
                await self.api_client.close()
                self.api_client = None
            
            self.order_api = None
            self.account_api = None
            self.tx_api = None
            self.info_api = None
            self.signer = None
            
            self._connected = False
            logger.info("Disconnected from Lighter")
        except Exception as e:
            logger.error(f"Error disconnecting from Lighter: {e}")
    
    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authenticate with Lighter using private key.
        
        Args:
            credentials: Must contain 'private_key'
        """
        try:
            private_key = credentials.get('private_key')
            if not private_key:
                raise AuthenticationException("Private key required for authentication")
            
            # Store credentials
            self.private_key = private_key
            self.wallet = EthAccount.from_key(private_key)
            self.address = self.wallet.address
            
            # Initialize signer client
            # SignerClient requires URL and indices for API key and account
            self.signer = SignerClient(
                url=self.base_url,
                private_key=private_key,
                api_key_index=0,  # Default API key index
                account_index=0   # Default account index
            )
            
            # Verify authentication by getting account info
            account = await self.account_api.account(
                by="address",
                value=self.address.lower()
            )
            
            if account:
                self._authenticated = True
                logger.info(f"Authenticated with Lighter as {self.address}")
                return True
            else:
                # Account might not exist yet, but authentication is valid
                self._authenticated = True
                logger.info(f"Authenticated with Lighter (new account): {self.address}")
                return True
                
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise AuthenticationException(f"Failed to authenticate: {str(e)}")
    
    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """Place a new order on Lighter."""
        if not self._authenticated or not self.signer:
            raise AuthenticationException("Not authenticated")
        
        try:
            # Map order type
            if order.order_type == OrderType.MARKET:
                # Create market order
                tx = await self.signer.create_market_order(
                    ticker_id=self._format_symbol(order.symbol),
                    is_bid=(order.side == OrderSide.BUY),
                    size=float(order.quantity),
                    slippage_tolerance=0.02  # 2% slippage tolerance
                )
            elif order.order_type == OrderType.LIMIT:
                # Create limit order
                tx = await self.signer.create_order(
                    ticker_id=self._format_symbol(order.symbol),
                    is_bid=(order.side == OrderSide.BUY),
                    price=float(order.price),
                    size=float(order.quantity),
                    time_in_force=self._map_time_in_force(order.time_in_force),
                    post_only=order.post_only
                )
            elif order.order_type == OrderType.STOP:
                # Create stop order
                tx = await self.signer.create_sl_order(
                    ticker_id=self._format_symbol(order.symbol),
                    is_bid=(order.side == OrderSide.BUY),
                    trigger_price=float(order.stop_price),
                    size=float(order.quantity)
                )
            elif order.order_type == OrderType.STOP_LIMIT:
                # Create stop limit order
                tx = await self.signer.create_sl_limit_order(
                    ticker_id=self._format_symbol(order.symbol),
                    is_bid=(order.side == OrderSide.BUY),
                    trigger_price=float(order.stop_price),
                    limit_price=float(order.price),
                    size=float(order.quantity)
                )
            else:
                raise OrderException(f"Unsupported order type: {order.order_type}")
            
            # Send transaction
            result = await self.signer.send_tx(tx)
            
            # Parse response
            order_id = result.tx_hash if hasattr(result, 'tx_hash') else str(result)
            
            return OrderResponse(
                order_id=order_id,
                client_order_id=order.client_order_id,
                symbol=order.symbol,
                side=order.side,
                order_type=order.order_type,
                status=OrderStatus.NEW,
                price=order.price,
                quantity=order.quantity,
                filled_quantity=Decimal("0"),
                remaining_quantity=order.quantity,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            raise OrderException(f"Order placement failed: {str(e)}")
    
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel an order on Lighter."""
        if not self._authenticated or not self.signer:
            raise AuthenticationException("Not authenticated")
        
        try:
            # Create cancel order transaction
            tx = await self.signer.cancel_order(
                ticker_id=self._format_symbol(symbol),
                order_id=order_id
            )
            
            # Send transaction
            result = await self.signer.send_tx(tx)
            
            return result is not None
            
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            raise OrderException(f"Order cancellation failed: {str(e)}")
    
    async def modify_order(
        self, 
        symbol: str, 
        order_id: str, 
        modifications: Dict[str, Any]
    ) -> OrderResponse:
        """Modify an order on Lighter."""
        if not self._authenticated or not self.signer:
            raise AuthenticationException("Not authenticated")
        
        try:
            # Create modify order transaction
            tx = await self.signer.modify_order(
                ticker_id=self._format_symbol(symbol),
                order_id=order_id,
                new_price=float(modifications.get('price', 0)),
                new_size=float(modifications.get('quantity', 0))
            )
            
            # Send transaction
            result = await self.signer.send_tx(tx)
            
            # Return updated order info
            return OrderResponse(
                order_id=order_id,
                client_order_id=None,
                symbol=symbol,
                side=modifications.get('side', OrderSide.BUY),
                order_type=modifications.get('order_type', OrderType.LIMIT),
                status=OrderStatus.NEW,
                price=Decimal(str(modifications.get('price', 0))),
                quantity=Decimal(str(modifications.get('quantity', 0))),
                filled_quantity=Decimal("0"),
                remaining_quantity=Decimal(str(modifications.get('quantity', 0))),
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Failed to modify order: {e}")
            raise OrderException(f"Order modification failed: {str(e)}")
    
    async def get_order(self, symbol: str, order_id: str) -> Order:
        """Get specific order details."""
        # Get all orders and filter
        orders = await self.get_orders(symbol=symbol)
        for order in orders:
            if order.order_id == order_id:
                return order
        raise OrderException(f"Order {order_id} not found")
    
    async def get_orders(
        self, 
        symbol: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        limit: int = 100
    ) -> List[Order]:
        """Get orders from Lighter."""
        if not self._authenticated:
            raise AuthenticationException("Not authenticated")
        
        try:
            # Get active orders
            active_orders = await self.order_api.account_active_orders(
                account=self.address.lower(),
                limit=limit
            )
            
            orders = []
            if active_orders and hasattr(active_orders, 'orders'):
                for order_data in active_orders.orders:
                    # Filter by symbol if specified
                    if symbol and order_data.ticker_id != self._format_symbol(symbol):
                        continue
                    
                    order = Order(
                        order_id=order_data.id,
                        client_order_id=None,
                        symbol=self._parse_symbol(order_data.ticker_id),
                        side=OrderSide.BUY if order_data.is_bid else OrderSide.SELL,
                        order_type=self._parse_order_type(order_data),
                        status=OrderStatus.NEW,
                        price=Decimal(str(order_data.price)),
                        stop_price=None,
                        quantity=Decimal(str(order_data.size)),
                        filled_quantity=Decimal(str(order_data.filled_size or 0)),
                        remaining_quantity=Decimal(str(order_data.size - (order_data.filled_size or 0))),
                        time_in_force=TimeInForce.GTC,
                        created_at=datetime.fromtimestamp(order_data.created_at),
                        updated_at=datetime.fromtimestamp(order_data.updated_at or order_data.created_at)
                    )
                    
                    # Filter by status if specified
                    if status and order.status != status:
                        continue
                    
                    orders.append(order)
            
            return orders
            
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return []
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get all open orders."""
        return await self.get_orders(symbol=symbol, status=OrderStatus.NEW)
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """Get current positions."""
        if not self._authenticated:
            raise AuthenticationException("Not authenticated")
        
        try:
            # Get account info
            account = await self.account_api.account(
                by="address",
                value=self.address.lower()
            )
            
            positions = []
            if account and hasattr(account, 'positions'):
                for pos_data in account.positions:
                    # Filter by symbol if specified
                    if symbol and pos_data.ticker_id != self._format_symbol(symbol):
                        continue
                    
                    position = Position(
                        symbol=self._parse_symbol(pos_data.ticker_id),
                        side=PositionSide.LONG if pos_data.size > 0 else PositionSide.SHORT,
                        quantity=Decimal(str(abs(pos_data.size))),
                        entry_price=Decimal(str(pos_data.average_price)),
                        mark_price=Decimal(str(pos_data.mark_price or pos_data.average_price)),
                        liquidation_price=Decimal(str(pos_data.liquidation_price)) if hasattr(pos_data, 'liquidation_price') else None,
                        unrealized_pnl=Decimal(str(pos_data.unrealized_pnl or 0)),
                        realized_pnl=Decimal(str(pos_data.realized_pnl or 0)),
                        margin=Decimal(str(pos_data.margin or 0)),
                        margin_ratio=None,
                        leverage=pos_data.leverage if hasattr(pos_data, 'leverage') else None,
                        isolated=False,
                        timestamp=datetime.utcnow()
                    )
                    positions.append(position)
            
            return positions
            
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    async def close_position(
        self, 
        symbol: str, 
        quantity: Optional[Decimal] = None
    ) -> OrderResponse:
        """Close a position."""
        # Get current position
        positions = await self.get_positions(symbol=symbol)
        if not positions:
            raise OrderException(f"No position found for {symbol}")
        
        position = positions[0]
        close_qty = quantity if quantity else position.quantity
        
        # Place opposite order to close
        order = OrderRequest(
            symbol=symbol,
            side=OrderSide.SELL if position.side == PositionSide.LONG else OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=close_qty,
            reduce_only=True
        )
        
        return await self.place_order(order)
    
    async def get_account_info(self) -> AccountInfo:
        """Get account information."""
        if not self._authenticated:
            raise AuthenticationException("Not authenticated")
        
        try:
            # Get account data
            account = await self.account_api.account(
                by="address",
                value=self.address.lower()
            )
            
            if not account:
                # Return empty account info for new accounts
                return AccountInfo(
                    account_id=self.address,
                    total_balance=Decimal("0"),
                    available_balance=Decimal("0"),
                    margin_balance=Decimal("0"),
                    unrealized_pnl=Decimal("0"),
                    realized_pnl=Decimal("0"),
                    margin_ratio=None,
                    positions=[],
                    timestamp=datetime.utcnow()
                )
            
            # Get positions
            positions = await self.get_positions()
            
            return AccountInfo(
                account_id=account.id if hasattr(account, 'id') else self.address,
                total_balance=Decimal(str(account.total_balance or 0)),
                available_balance=Decimal(str(account.available_balance or 0)),
                margin_balance=Decimal(str(account.margin_balance or 0)),
                unrealized_pnl=Decimal(str(account.unrealized_pnl or 0)),
                realized_pnl=Decimal(str(account.realized_pnl or 0)),
                margin_ratio=Decimal(str(account.margin_ratio)) if hasattr(account, 'margin_ratio') else None,
                positions=positions,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            raise ConnectorException(f"Failed to get account info: {str(e)}")
    
    async def get_balance(self, asset: Optional[str] = None) -> Dict[str, Decimal]:
        """Get account balance."""
        account_info = await self.get_account_info()
        
        if asset:
            return {asset: account_info.available_balance}
        else:
            return {
                "USDC": account_info.available_balance,
                "total": account_info.total_balance,
                "available": account_info.available_balance,
                "margin": account_info.margin_balance
            }
    
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for a symbol."""
        if not self._authenticated or not self.signer:
            raise AuthenticationException("Not authenticated")
        
        try:
            # Create update leverage transaction
            tx = await self.signer.update_leverage(
                ticker_id=self._format_symbol(symbol),
                leverage=leverage
            )
            
            # Send transaction
            result = await self.signer.send_tx(tx)
            
            return result is not None
            
        except Exception as e:
            logger.error(f"Failed to set leverage: {e}")
            return False
    
    async def get_market_data(self, symbol: str) -> MarketData:
        """Get market data for a symbol."""
        try:
            # Get market ID
            market_id = self._get_market_id(symbol)
            
            # Get order book for market data
            book = await self.order_api.order_book_details(
                market_id=market_id
            )
            
            # Get recent trades for volume
            trades = await self.order_api.recent_trades(
                market_id=market_id,
                limit=100
            )
            
            # Calculate 24h volume from trades
            volume_24h = Decimal("0")
            if trades and hasattr(trades, 'trades'):
                for trade in trades.trades:
                    size = Decimal(str(trade.size)) if hasattr(trade, 'size') else Decimal("0")
                    price = Decimal(str(trade.price)) if hasattr(trade, 'price') else Decimal("0")
                    volume_24h += size * price
            
            # Get bid/ask from order book
            bid_price = None
            ask_price = None
            last_price = Decimal("0")
            
            if book:
                if hasattr(book, 'bids') and book.bids:
                    bid_price = Decimal(str(book.bids[0].price))
                    last_price = bid_price
                if hasattr(book, 'asks') and book.asks:
                    ask_price = Decimal(str(book.asks[0].price))
                    if not last_price:
                        last_price = ask_price
            
            return MarketData(
                symbol=symbol,
                last_price=last_price,
                bid_price=bid_price,
                ask_price=ask_price,
                volume_24h=volume_24h,
                high_24h=last_price,  # Not available in SDK
                low_24h=last_price,   # Not available in SDK
                open_24h=last_price,  # Not available in SDK
                funding_rate=None,
                next_funding_time=None,
                open_interest=None,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Failed to get market data: {e}")
            raise ConnectorException(f"Failed to get market data: {str(e)}")
    
    async def get_order_book(self, symbol: str, depth: int = 20) -> OrderBook:
        """Get order book for a symbol."""
        try:
            # Get market ID
            market_id = self._get_market_id(symbol)
            
            # Get order book details
            book = await self.order_api.order_book_details(
                market_id=market_id
            )
            
            bids = []
            asks = []
            
            if book:
                if hasattr(book, 'bids'):
                    for bid in book.bids[:depth]:
                        bids.append(OrderBookLevel(
                            price=Decimal(str(bid.price)),
                            quantity=Decimal(str(bid.size))
                        ))
                
                if hasattr(book, 'asks'):
                    for ask in book.asks[:depth]:
                        asks.append(OrderBookLevel(
                            price=Decimal(str(ask.price)),
                            quantity=Decimal(str(ask.size))
                        ))
            
            return OrderBook(
                symbol=symbol,
                bids=bids,
                asks=asks,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Failed to get order book: {e}")
            raise ConnectorException(f"Failed to get order book: {str(e)}")
    
    async def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Trade]:
        """Get recent trades for a symbol."""
        try:
            # Get market ID
            market_id = self._get_market_id(symbol)
            
            # Get recent trades
            trades_data = await self.order_api.recent_trades(
                market_id=market_id,
                limit=limit
            )
            
            trades = []
            if trades_data and hasattr(trades_data, 'trades'):
                for i, trade_data in enumerate(trades_data.trades):
                    # Generate a unique trade ID
                    trade_id = str(trade_data.id) if hasattr(trade_data, 'id') else f"trade_{market_id}_{i}"
                    
                    trade = Trade(
                        trade_id=trade_id,
                        order_id="",  # Not available
                        symbol=symbol,
                        side=OrderSide.BUY if hasattr(trade_data, 'is_bid') and trade_data.is_bid else OrderSide.SELL,
                        price=Decimal(str(trade_data.price)) if hasattr(trade_data, 'price') else Decimal("0"),
                        quantity=Decimal(str(trade_data.size)) if hasattr(trade_data, 'size') else Decimal("0"),
                        fee=Decimal("0"),  # Not available
                        fee_asset="USDC",
                        timestamp=self._parse_timestamp(trade_data.timestamp) if hasattr(trade_data, 'timestamp') else datetime.utcnow(),
                        is_maker=False  # Not available
                    )
                    trades.append(trade)
            
            return trades
            
        except Exception as e:
            logger.error(f"Failed to get recent trades: {e}")
            return []
    
    async def get_funding_rate(self, symbol: str) -> Dict[str, Any]:
        """Get funding rate for perpetual contracts."""
        # Lighter doesn't expose funding rate directly
        return {
            "symbol": symbol,
            "funding_rate": Decimal("0"),
            "next_funding_time": None,
            "timestamp": datetime.utcnow()
        }
    
    async def subscribe_to_updates(
        self, 
        channels: List[str],
        callback: Optional[Any] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """Subscribe to real-time updates via WebSocket."""
        try:
            # Initialize WebSocket client if needed
            if not self.ws_client:
                ws_url = self.base_url.replace('https', 'wss')
                self.ws_client = WsClient(url=ws_url)
                await self.ws_client.connect()
            
            # Subscribe to channels
            for channel in channels:
                await self.ws_client.subscribe(channel)
            
            # Yield updates
            async for message in self.ws_client.listen():
                if callback:
                    await callback(message)
                yield message
                
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            raise ConnectorException(f"WebSocket subscription failed: {str(e)}")
    
    async def unsubscribe_from_updates(self, channels: List[str]) -> bool:
        """Unsubscribe from WebSocket channels."""
        try:
            if self.ws_client:
                for channel in channels:
                    await self.ws_client.unsubscribe(channel)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to unsubscribe: {e}")
            return False
    
    # Utility methods
    
    def is_connected(self) -> bool:
        """Check if connector is connected."""
        return self._connected and self.api_client is not None
    
    # Helper methods
    
    async def _build_symbol_mappings(self):
        """Build symbol to market_id mappings."""
        try:
            books = await self.order_api.order_books()
            if books and hasattr(books, 'order_books'):
                for book in books.order_books:
                    if hasattr(book, 'symbol') and hasattr(book, 'market_id'):
                        symbol = book.symbol.upper()
                        market_id = book.market_id
                        
                        # Store mappings
                        self.symbol_to_market_id[symbol] = market_id
                        self.market_id_to_symbol[market_id] = symbol
                        
                        # Also store with -PERP suffix
                        symbol_perp = f"{symbol}-PERP"
                        self.symbol_to_market_id[symbol_perp] = market_id
                        
                logger.info(f"Loaded {len(self.symbol_to_market_id)} market symbols")
        except Exception as e:
            logger.warning(f"Failed to build symbol mappings: {e}")
            # Use fallback mappings for common symbols
            self.symbol_to_market_id = {
                "ETH": 0, "ETH-PERP": 0,
                "BTC": 1, "BTC-PERP": 1,
            }
            self.market_id_to_symbol = {0: "ETH", 1: "BTC"}
    
    def _format_symbol(self, symbol: str) -> str:
        """Format symbol for Lighter API."""
        # Remove common suffixes
        symbol = symbol.replace('-PERP', '').replace('-USD', '').replace('/USD', '')
        return symbol.upper()
    
    def _get_market_id(self, symbol: str) -> int:
        """Get market ID for a symbol."""
        formatted = self._format_symbol(symbol)
        
        # Check mappings
        if formatted in self.symbol_to_market_id:
            return self.symbol_to_market_id[formatted]
        if symbol.upper() in self.symbol_to_market_id:
            return self.symbol_to_market_id[symbol.upper()]
        
        # Try to parse as integer (if user passes market ID directly)
        try:
            return int(symbol)
        except ValueError:
            raise ConnectorException(f"Unknown symbol: {symbol}")
    
    def _parse_symbol(self, market_id: int) -> str:
        """Parse symbol from market ID."""
        if market_id in self.market_id_to_symbol:
            return f"{self.market_id_to_symbol[market_id]}-PERP"
        return f"MARKET{market_id}-PERP"
    
    def _map_time_in_force(self, tif: TimeInForce) -> int:
        """Map TimeInForce to Lighter format."""
        mapping = {
            TimeInForce.GTC: SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
            TimeInForce.IOC: SignerClient.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL,
            TimeInForce.POST_ONLY: SignerClient.ORDER_TIME_IN_FORCE_POST_ONLY,
        }
        return mapping.get(tif, SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME)
    
    def _parse_order_type(self, order_data) -> OrderType:
        """Parse order type from order data."""
        # Check if it's a stop order
        if hasattr(order_data, 'trigger_price') and order_data.trigger_price:
            if hasattr(order_data, 'limit_price') and order_data.limit_price:
                return OrderType.STOP_LIMIT
            return OrderType.STOP
        return OrderType.LIMIT
    
    def _parse_timestamp(self, timestamp) -> datetime:
        """Parse timestamp from various formats."""
        if isinstance(timestamp, datetime):
            return timestamp
        
        # Convert to float
        ts = float(timestamp)
        
        # Check if it's in milliseconds (>1e10) or microseconds (>1e12)
        if ts > 1e12:
            # Microseconds
            return datetime.fromtimestamp(ts / 1e6)
        elif ts > 1e10:
            # Milliseconds
            return datetime.fromtimestamp(ts / 1e3)
        else:
            # Seconds
            return datetime.fromtimestamp(ts)