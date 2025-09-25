"""
Order database models.
"""
from sqlalchemy import Column, String, Boolean, JSON, Numeric, ForeignKey, Enum, Index, DateTime, Text, Integer
from sqlalchemy.orm import relationship
from .base import Base
import enum


class OrderSide(enum.Enum):
    """Order side enum"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(enum.Enum):
    """Order type enum"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"


class OrderStatus(enum.Enum):
    """Order status enum"""
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    PENDING = "PENDING"


class TimeInForce(enum.Enum):
    """Time in force enum"""
    GTC = "GTC"  # Good Till Cancel
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill
    GTT = "GTT"  # Good Till Time
    POST_ONLY = "POST_ONLY"


class Order(Base):
    """Order model"""
    
    # Foreign keys
    account_id = Column(Integer, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False)
    dex_account_id = Column(Integer, ForeignKey('dex_accounts.id', ondelete='CASCADE'), nullable=False)
    
    # Order identifiers
    exchange_order_id = Column(String(255), index=True)  # Exchange's order ID
    client_order_id = Column(String(255), unique=True, index=True)  # Our internal ID
    
    # Order details
    symbol = Column(String(50), nullable=False, index=True)
    side = Column(Enum(OrderSide), nullable=False)
    order_type = Column(Enum(OrderType), nullable=False)
    status = Column(Enum(OrderStatus), nullable=False, index=True)
    time_in_force = Column(Enum(TimeInForce), default=TimeInForce.GTC)
    
    # Quantities
    quantity = Column(Numeric(20, 8), nullable=False)
    filled_quantity = Column(Numeric(20, 8), default=0)
    remaining_quantity = Column(Numeric(20, 8))
    
    # Prices
    price = Column(Numeric(20, 8))  # Limit price
    stop_price = Column(Numeric(20, 8))  # Stop/trigger price
    average_fill_price = Column(Numeric(20, 8))
    
    # Flags
    reduce_only = Column(Boolean, default=False)
    post_only = Column(Boolean, default=False)
    is_isolated = Column(Boolean, default=False)
    
    # Fees
    fee = Column(Numeric(20, 8), default=0)
    fee_asset = Column(String(20))
    
    # Timestamps
    placed_at = Column(DateTime(timezone=True))
    filled_at = Column(DateTime(timezone=True))
    canceled_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    
    # Error tracking
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    
    # Metadata
    extra_data = Column(JSON, default={})
    
    # Relationships
    account = relationship("Account", back_populates="orders")
    dex_account = relationship("DexAccount", back_populates="orders")
    trades = relationship("Trade", back_populates="order", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_order_account', 'account_id'),
        Index('idx_order_dex_account', 'dex_account_id'),
        Index('idx_order_symbol', 'symbol'),
        Index('idx_order_status', 'status'),
        Index('idx_order_exchange_id', 'exchange_order_id'),
        Index('idx_order_client_id', 'client_order_id'),
        Index('idx_order_placed_at', 'placed_at'),
    )


class Trade(Base):
    """Trade/fill model"""
    
    # Foreign keys
    order_id = Column(Integer, ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    position_id = Column(Integer, ForeignKey('positions.id', ondelete='SET NULL'))
    
    # Trade identifiers
    exchange_trade_id = Column(String(255), unique=True, index=True)
    
    # Trade details
    symbol = Column(String(50), nullable=False, index=True)
    side = Column(Enum(OrderSide), nullable=False)
    
    # Quantities and prices
    quantity = Column(Numeric(20, 8), nullable=False)
    price = Column(Numeric(20, 8), nullable=False)
    value = Column(Numeric(20, 8))  # quantity * price
    
    # Fees
    fee = Column(Numeric(20, 8), default=0)
    fee_asset = Column(String(20))
    is_maker = Column(Boolean, default=False)
    
    # Realized P&L (if closing position)
    realized_pnl = Column(Numeric(20, 8))
    
    # Timestamp
    executed_at = Column(DateTime(timezone=True), nullable=False)
    
    # Metadata
    extra_data = Column(JSON, default={})
    
    # Relationships
    order = relationship("Order", back_populates="trades")
    position = relationship("Position", back_populates="trades")
    
    __table_args__ = (
        Index('idx_trade_order', 'order_id'),
        Index('idx_trade_position', 'position_id'),
        Index('idx_trade_symbol', 'symbol'),
        Index('idx_trade_executed_at', 'executed_at'),
        Index('idx_trade_exchange_id', 'exchange_trade_id'),
    )