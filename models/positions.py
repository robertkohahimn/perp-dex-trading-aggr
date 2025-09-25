"""
Position database models.
"""
from sqlalchemy import Column, String, Boolean, JSON, Numeric, ForeignKey, Enum, Index, DateTime, Text, Integer
from sqlalchemy.orm import relationship
from .base import Base
import enum


class PositionSide(enum.Enum):
    """Position side enum"""
    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"  # For net positions


class PositionStatus(enum.Enum):
    """Position status enum"""
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"
    LIQUIDATED = "LIQUIDATED"


class Position(Base):
    """Position model"""
    
    # Foreign keys
    account_id = Column(Integer, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False)
    dex_account_id = Column(Integer, ForeignKey('dex_accounts.id', ondelete='CASCADE'), nullable=False)
    
    # Position identifiers
    symbol = Column(String(50), nullable=False, index=True)
    side = Column(Enum(PositionSide), nullable=False)
    status = Column(Enum(PositionStatus), default=PositionStatus.OPEN, nullable=False, index=True)
    
    # Quantities
    quantity = Column(Numeric(20, 8), nullable=False)
    initial_quantity = Column(Numeric(20, 8), nullable=False)
    
    # Prices
    entry_price = Column(Numeric(20, 8), nullable=False)
    mark_price = Column(Numeric(20, 8))
    liquidation_price = Column(Numeric(20, 8))
    exit_price = Column(Numeric(20, 8))
    
    # P&L
    unrealized_pnl = Column(Numeric(20, 8), default=0)
    realized_pnl = Column(Numeric(20, 8), default=0)
    total_pnl = Column(Numeric(20, 8), default=0)
    pnl_percentage = Column(Numeric(10, 4))
    
    # Margin
    margin = Column(Numeric(20, 8), nullable=False)
    margin_ratio = Column(Numeric(10, 4))
    leverage = Column(Integer, default=1)
    is_isolated = Column(Boolean, default=False)
    
    # Fees
    total_fees = Column(Numeric(20, 8), default=0)
    funding_fees = Column(Numeric(20, 8), default=0)
    
    # Risk metrics
    max_drawdown = Column(Numeric(20, 8))
    max_profit = Column(Numeric(20, 8))
    
    # Timestamps
    opened_at = Column(DateTime(timezone=True), nullable=False)
    closed_at = Column(DateTime(timezone=True))
    last_updated = Column(DateTime(timezone=True))
    
    # Stop loss / Take profit
    stop_loss_price = Column(Numeric(20, 8))
    take_profit_price = Column(Numeric(20, 8))
    stop_loss_order_id = Column(String(255))
    take_profit_order_id = Column(String(255))
    
    # Metadata
    extra_data = Column(JSON, default={})
    notes = Column(Text)
    
    # Relationships
    account = relationship("Account", back_populates="positions")
    dex_account = relationship("DexAccount", back_populates="positions")
    trades = relationship("Trade", back_populates="position")
    
    __table_args__ = (
        Index('idx_position_account', 'account_id'),
        Index('idx_position_dex_account', 'dex_account_id'),
        Index('idx_position_symbol', 'symbol'),
        Index('idx_position_status', 'status'),
        Index('idx_position_opened_at', 'opened_at'),
        Index('idx_position_symbol_status', 'symbol', 'status'),
    )


class PositionHistory(Base):
    """Historical position data for analysis"""
    
    # Foreign keys
    position_id = Column(Integer, ForeignKey('positions.id', ondelete='CASCADE'), nullable=False)
    
    # Snapshot data
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    quantity = Column(Numeric(20, 8), nullable=False)
    mark_price = Column(Numeric(20, 8), nullable=False)
    unrealized_pnl = Column(Numeric(20, 8))
    margin_ratio = Column(Numeric(10, 4))
    
    # Market data at snapshot
    bid_price = Column(Numeric(20, 8))
    ask_price = Column(Numeric(20, 8))
    funding_rate = Column(Numeric(10, 6))
    
    # Metadata
    extra_data = Column(JSON, default={})
    
    # Relationship
    position = relationship("Position")
    
    __table_args__ = (
        Index('idx_position_history_position', 'position_id'),
        Index('idx_position_history_timestamp', 'timestamp'),
    )