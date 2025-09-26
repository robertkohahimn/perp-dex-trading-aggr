"""
Trading schemas.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class OrderSide(str, Enum):
    """Order side enum."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type enum."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(str, Enum):
    """Order status enum."""
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class TimeInForce(str, Enum):
    """Time in force enum."""
    GTC = "GTC"  # Good Till Cancel
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill
    GTT = "GTT"  # Good Till Time


class PositionSide(str, Enum):
    """Position side enum."""
    LONG = "LONG"
    SHORT = "SHORT"


class PositionStatus(str, Enum):
    """Position status enum."""
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"
    LIQUIDATED = "LIQUIDATED"


class OrderRequest(BaseModel):
    """Order request schema."""
    dex: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float = Field(..., gt=0)
    price: Optional[float] = Field(None, gt=0)
    stop_price: Optional[float] = Field(None, gt=0)
    time_in_force: TimeInForce = TimeInForce.GTC
    reduce_only: bool = False
    post_only: bool = False
    client_order_id: Optional[str] = None


class OrderModifyRequest(BaseModel):
    """Order modification request schema."""
    quantity: Optional[float] = Field(None, gt=0)
    price: Optional[float] = Field(None, gt=0)
    stop_price: Optional[float] = Field(None, gt=0)


class OrderResponse(BaseModel):
    """Order response schema."""
    id: int
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float]
    status: OrderStatus
    executed_quantity: float
    executed_price: Optional[float]
    fee: float
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True


class PositionResponse(BaseModel):
    """Position response schema."""
    id: int
    symbol: str
    side: PositionSide
    size: float
    entry_price: float
    mark_price: float
    liquidation_price: Optional[float]
    unrealized_pnl: float
    realized_pnl: float
    margin: float
    leverage: int
    status: PositionStatus
    dex: str
    account_name: str
    
    class Config:
        orm_mode = True


class TradeResponse(BaseModel):
    """Trade response schema."""
    id: int
    order_id: int
    symbol: str
    side: OrderSide
    price: float
    quantity: float
    fee: float
    timestamp: datetime
    
    class Config:
        orm_mode = True


class AccountBalanceResponse(BaseModel):
    """Account balance response schema."""
    dex: str
    account_name: str
    total_balance: float
    available_balance: float
    margin_used: float
    unrealized_pnl: float
    realized_pnl: float
    
    class Config:
        orm_mode = True


class RiskMetricsResponse(BaseModel):
    """Risk metrics response schema."""
    account_id: int
    total_exposure: float
    margin_usage_pct: float
    leverage_ratio: float
    var_95: float
    max_drawdown: float
    sharpe_ratio: float
    risk_level: str
    alerts: List[str]
    timestamp: datetime
    
    class Config:
        orm_mode = True