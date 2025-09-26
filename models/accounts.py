"""
Account database models.
"""
from sqlalchemy import Column, String, Boolean, Text, JSON, Numeric, ForeignKey, UniqueConstraint, Index, DateTime, Integer
from sqlalchemy.orm import relationship
from .base import Base


class Account(Base):
    """User account model"""
    
    # Basic fields
    user_id = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Security
    password_hash = Column(String(255))
    api_key_hash = Column(String(255), unique=True, index=True)
    
    # Settings
    settings = Column(JSON, default={})
    
    # Risk parameters
    max_position_size_usd = Column(Numeric(20, 8), default=100000)
    max_leverage = Column(Numeric(5, 2), default=10)
    
    # Relationships
    dex_accounts = relationship("DexAccount", back_populates="account", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="account", cascade="all, delete-orphan")
    positions = relationship("Position", back_populates="account", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_account_user_id', 'user_id'),
        Index('idx_account_email', 'email'),
    )


class DexAccount(Base):
    """DEX-specific account configuration"""
    
    # Foreign keys
    account_id = Column(Integer, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False)
    
    # DEX information
    dex_name = Column(String(50), nullable=False)  # hyperliquid, lighter, etc.
    account_name = Column(String(255), nullable=False)
    is_testnet = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Encrypted credentials
    encrypted_api_key = Column(Text)
    encrypted_api_secret = Column(Text)
    encrypted_private_key = Column(Text)  # For wallets
    
    # Additional configuration
    wallet_address = Column(String(255), index=True)
    vault_number = Column(Integer)  # For Extended
    config = Column(JSON, default={})  # DEX-specific config
    
    # Balances (cached)
    total_balance = Column(Numeric(20, 8), default=0)
    available_balance = Column(Numeric(20, 8), default=0)
    margin_balance = Column(Numeric(20, 8), default=0)
    unrealized_pnl = Column(Numeric(20, 8), default=0)
    
    # Rate limiting
    requests_per_minute = Column(Integer, default=60)
    last_request_time = Column(DateTime(timezone=True))
    request_count = Column(Integer, default=0)
    
    # Relationships
    account = relationship("Account", back_populates="dex_accounts")
    orders = relationship("Order", back_populates="dex_account", cascade="all, delete-orphan")
    positions = relationship("Position", back_populates="dex_account", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('account_id', 'dex_name', 'account_name', name='_dex_account_uc'),
        Index('idx_dex_account_dex_name', 'dex_name'),
        Index('idx_dex_account_wallet', 'wallet_address'),
    )


class ApiKey(Base):
    """API key management for external access"""
    
    # Foreign key
    account_id = Column(Integer, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False)
    
    # API key fields
    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Permissions
    permissions = Column(JSON, default={})
    can_trade = Column(Boolean, default=False)
    can_read = Column(Boolean, default=True)
    can_withdraw = Column(Boolean, default=False)
    
    # Rate limiting
    rate_limit_per_minute = Column(Integer, default=60)
    
    # Tracking
    last_used = Column(DateTime(timezone=True))
    usage_count = Column(Integer, default=0)
    
    # IP restrictions
    allowed_ips = Column(JSON, default=[])
    
    # Expiration
    expires_at = Column(DateTime(timezone=True))
    
    # Relationship
    account = relationship("Account")
    
    __table_args__ = (
        Index('idx_api_key_hash', 'key_hash'),
        Index('idx_api_key_account', 'account_id'),
    )