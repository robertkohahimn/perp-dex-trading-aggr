"""
Base connector abstract class for all DEX integrations.
Defines the standard interface that all connectors must implement.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, AsyncIterator
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from decimal import Decimal


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"


class OrderStatus(Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class TimeInForce(Enum):
    GTC = "GTC"  # Good Till Cancel
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill
    GTT = "GTT"  # Good Till Time
    POST_ONLY = "POST_ONLY"


class PositionSide(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"  # For net positions


@dataclass
class OrderRequest:
    """Standard order request structure"""
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    reduce_only: bool = False
    post_only: bool = False
    client_order_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class OrderResponse:
    """Standard order response structure"""
    order_id: str
    client_order_id: Optional[str]
    symbol: str
    side: OrderSide
    order_type: OrderType
    status: OrderStatus
    price: Optional[Decimal]
    quantity: Decimal
    filled_quantity: Decimal
    remaining_quantity: Decimal
    timestamp: datetime
    fee: Optional[Decimal] = None
    fee_asset: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Order:
    """Order information structure"""
    order_id: str
    client_order_id: Optional[str]
    symbol: str
    side: OrderSide
    order_type: OrderType
    status: OrderStatus
    price: Optional[Decimal]
    stop_price: Optional[Decimal]
    quantity: Decimal
    filled_quantity: Decimal
    remaining_quantity: Decimal
    time_in_force: TimeInForce
    created_at: datetime
    updated_at: datetime
    fee: Optional[Decimal] = None
    fee_asset: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Position:
    """Position information structure"""
    symbol: str
    side: PositionSide
    quantity: Decimal
    entry_price: Decimal
    mark_price: Decimal
    liquidation_price: Optional[Decimal]
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    margin: Decimal
    margin_ratio: Optional[Decimal]
    leverage: Optional[int]
    isolated: bool = False
    timestamp: datetime = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class AccountInfo:
    """Account information structure"""
    account_id: str
    total_balance: Decimal
    available_balance: Decimal
    margin_balance: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    margin_ratio: Optional[Decimal]
    positions: List[Position]
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class MarketData:
    """Market data structure"""
    symbol: str
    last_price: Decimal
    bid_price: Optional[Decimal]
    ask_price: Optional[Decimal]
    volume_24h: Decimal
    high_24h: Decimal
    low_24h: Decimal
    open_24h: Decimal
    funding_rate: Optional[Decimal]
    next_funding_time: Optional[datetime]
    open_interest: Optional[Decimal]
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class OrderBookLevel:
    """Single order book level"""
    price: Decimal
    quantity: Decimal
    order_count: Optional[int] = None


@dataclass
class OrderBook:
    """Order book structure"""
    symbol: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Trade:
    """Trade/fill information"""
    trade_id: str
    order_id: str
    symbol: str
    side: OrderSide
    price: Decimal
    quantity: Decimal
    fee: Decimal
    fee_asset: str
    timestamp: datetime
    is_maker: bool
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ConnectorConfig:
    """Base configuration for connectors"""
    name: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    testnet: bool = False
    rate_limit: Optional[int] = None  # requests per minute
    metadata: Optional[Dict[str, Any]] = None


class ConnectorException(Exception):
    """Base exception for connector errors"""
    pass


class AuthenticationException(ConnectorException):
    """Authentication related errors"""
    pass


class OrderException(ConnectorException):
    """Order related errors"""
    pass


class RateLimitException(ConnectorException):
    """Rate limit errors"""
    pass


class BaseConnector(ABC):
    """Abstract base class for all DEX connectors"""
    
    def __init__(self, config: ConnectorConfig):
        """Initialize connector with configuration"""
        self.config = config
        self.name = config.name
        self.testnet = config.testnet
        self._authenticated = False
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the DEX"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the DEX"""
        pass
    
    @abstractmethod
    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authenticate with the DEX
        
        Args:
            credentials: Authentication credentials (API keys, etc.)
        
        Returns:
            Success status
        """
        pass
    
    # Order Management
    
    @abstractmethod
    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """
        Place a new order
        
        Args:
            order: Order request details
        
        Returns:
            Order response with order ID and status
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """
        Cancel an existing order
        
        Args:
            symbol: Trading symbol
            order_id: Order ID to cancel
        
        Returns:
            Success status
        """
        pass
    
    @abstractmethod
    async def modify_order(
        self, 
        symbol: str, 
        order_id: str, 
        modifications: Dict[str, Any]
    ) -> OrderResponse:
        """
        Modify an existing order
        
        Args:
            symbol: Trading symbol
            order_id: Order ID to modify
            modifications: Dictionary of fields to modify
        
        Returns:
            Modified order response
        """
        pass
    
    @abstractmethod
    async def get_order(self, symbol: str, order_id: str) -> Order:
        """
        Get specific order details
        
        Args:
            symbol: Trading symbol
            order_id: Order ID
        
        Returns:
            Order details
        """
        pass
    
    @abstractmethod
    async def get_orders(
        self, 
        symbol: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        limit: int = 100
    ) -> List[Order]:
        """
        Get orders with optional filters
        
        Args:
            symbol: Optional symbol filter
            status: Optional status filter
            limit: Maximum number of orders to return
        
        Returns:
            List of orders
        """
        pass
    
    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """
        Get all open orders
        
        Args:
            symbol: Optional symbol filter
        
        Returns:
            List of open orders
        """
        pass
    
    # Position Management
    
    @abstractmethod
    async def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """
        Get current positions
        
        Args:
            symbol: Optional symbol filter
        
        Returns:
            List of positions
        """
        pass
    
    @abstractmethod
    async def close_position(
        self, 
        symbol: str, 
        quantity: Optional[Decimal] = None
    ) -> OrderResponse:
        """
        Close a position
        
        Args:
            symbol: Trading symbol
            quantity: Optional quantity to close (None = close all)
        
        Returns:
            Order response for the closing order
        """
        pass
    
    # Account Management
    
    @abstractmethod
    async def get_account_info(self) -> AccountInfo:
        """
        Get account information including balances
        
        Returns:
            Account information
        """
        pass
    
    @abstractmethod
    async def get_balance(self, asset: Optional[str] = None) -> Dict[str, Decimal]:
        """
        Get account balance
        
        Args:
            asset: Optional specific asset to query
        
        Returns:
            Balance dictionary
        """
        pass
    
    @abstractmethod
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """
        Set leverage for a symbol
        
        Args:
            symbol: Trading symbol
            leverage: Leverage value
        
        Returns:
            Success status
        """
        pass
    
    # Market Data
    
    @abstractmethod
    async def get_market_data(self, symbol: str) -> MarketData:
        """
        Get market data for a symbol
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Market data
        """
        pass
    
    @abstractmethod
    async def get_order_book(
        self, 
        symbol: str, 
        depth: int = 20
    ) -> OrderBook:
        """
        Get order book for a symbol
        
        Args:
            symbol: Trading symbol
            depth: Number of levels to fetch
        
        Returns:
            Order book
        """
        pass
    
    @abstractmethod
    async def get_recent_trades(
        self, 
        symbol: str, 
        limit: int = 100
    ) -> List[Trade]:
        """
        Get recent trades for a symbol
        
        Args:
            symbol: Trading symbol
            limit: Maximum number of trades
        
        Returns:
            List of recent trades
        """
        pass
    
    @abstractmethod
    async def get_funding_rate(self, symbol: str) -> Dict[str, Any]:
        """
        Get funding rate for perpetual contracts
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Funding rate information
        """
        pass
    
    # WebSocket Support
    
    @abstractmethod
    async def subscribe_to_updates(
        self, 
        channels: List[str],
        callback: Optional[Any] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Subscribe to real-time updates via WebSocket
        
        Args:
            channels: List of channels to subscribe to
            callback: Optional callback function for updates
        
        Yields:
            Update messages
        """
        pass
    
    @abstractmethod
    async def unsubscribe_from_updates(self, channels: List[str]) -> bool:
        """
        Unsubscribe from WebSocket channels
        
        Args:
            channels: List of channels to unsubscribe from
        
        Returns:
            Success status
        """
        pass
    
    # Utility Methods
    
    async def get_server_time(self) -> datetime:
        """Get server time (optional implementation)"""
        return datetime.utcnow()
    
    async def get_exchange_info(self) -> Dict[str, Any]:
        """Get exchange configuration (optional implementation)"""
        return {}
    
    async def get_trading_fees(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Get trading fee structure (optional implementation)"""
        return {}
    
    def is_connected(self) -> bool:
        """Check if connector is connected"""
        return self._authenticated
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, testnet={self.testnet})"