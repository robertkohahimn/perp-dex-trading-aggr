"""
Application configuration management using Pydantic Settings.
"""
from typing import List, Optional, Dict, Any
from pydantic import Field, SecretStr, validator
from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class AppSettings(BaseSettings):
    """Application settings"""
    app_name: str = Field(default="perp-dex-backend", description="Application name")
    app_env: str = Field(default="development", description="Environment: development, staging, production")
    debug: bool = Field(default=True, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # API Configuration
    api_version: str = Field(default="v1", description="API version")
    api_prefix: str = Field(default="/api", description="API prefix")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="Allowed CORS origins"
    )
    
    # Server Configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    workers: int = Field(default=4, description="Number of workers")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


class DatabaseSettings(BaseSettings):
    """Database settings"""
    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/perp_dex_db",
        description="Database connection URL"
    )
    database_pool_size: int = Field(default=20, description="Connection pool size")
    database_max_overflow: int = Field(default=40, description="Max overflow connections")
    database_pool_timeout: int = Field(default=30, description="Pool timeout in seconds")
    database_echo: bool = Field(default=False, description="Echo SQL statements")
    
    @validator("database_url")
    def validate_database_url(cls, v):
        """Ensure database URL uses async driver"""
        if "postgresql://" in v and "+asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


class RedisSettings(BaseSettings):
    """Redis settings"""
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis URL")
    redis_password: Optional[SecretStr] = Field(default=None, description="Redis password")
    redis_pool_size: int = Field(default=10, description="Connection pool size")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


class SecuritySettings(BaseSettings):
    """Security settings"""
    secret_key: SecretStr = Field(
        default="your-secret-key-change-this-in-production",
        description="Secret key for JWT"
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(default=30, description="Access token expiry")
    refresh_token_expire_days: int = Field(default=30, description="Refresh token expiry")
    api_key_header: str = Field(default="X-API-Key", description="API key header name")
    encryption_key: SecretStr = Field(
        default="your-32-byte-encryption-key-here",
        description="Key for encrypting sensitive data"
    )
    
    @validator("encryption_key")
    def validate_encryption_key(cls, v):
        """Ensure encryption key is 32 bytes"""
        if len(v.get_secret_value()) != 32:
            raise ValueError("Encryption key must be exactly 32 bytes long")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


class RateLimitSettings(BaseSettings):
    """Rate limiting settings"""
    rate_limit_requests_per_minute: int = Field(default=60, description="Requests per minute")
    rate_limit_burst: int = Field(default=100, description="Burst limit")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


class DEXSettings(BaseSettings):
    """DEX-specific settings"""
    # Hyperliquid
    hyperliquid_mainnet_url: str = Field(default="https://api.hyperliquid.xyz")
    hyperliquid_testnet_url: str = Field(default="https://api.hyperliquid-testnet.xyz")
    hyperliquid_use_testnet: bool = Field(default=True)
    
    # Lighter
    lighter_mainnet_url: str = Field(default="https://mainnet.zklighter.elliot.ai")
    lighter_use_testnet: bool = Field(default=False)
    
    # Extended
    extended_mainnet_url: str = Field(default="https://api.starknet.extended.exchange/")
    extended_testnet_url: str = Field(default="https://api.starknet.sepolia.extended.exchange/")
    extended_use_testnet: bool = Field(default=True)
    
    # EdgeX
    edgex_base_url: str = Field(default="https://pro.edgex.exchange")
    edgex_ws_url: str = Field(default="wss://quote.edgex.exchange")
    
    # Vest
    vest_production_url: str = Field(default="https://server-prod.hz.vestmarkets.com/v2")
    vest_development_url: str = Field(default="https://server-dev.hz.vestmarkets.com/v2")
    vest_ws_production_url: str = Field(default="wss://ws-prod.hz.vestmarkets.com/ws-api?version=1.0")
    vest_ws_development_url: str = Field(default="wss://ws-dev.hz.vestmarkets.com/ws-api?version=1.0")
    vest_use_testnet: bool = Field(default=True)
    
    def get_dex_config(self, dex_name: str) -> Dict[str, Any]:
        """Get configuration for a specific DEX"""
        configs = {
            "hyperliquid": {
                "url": self.hyperliquid_testnet_url if self.hyperliquid_use_testnet else self.hyperliquid_mainnet_url,
                "testnet": self.hyperliquid_use_testnet
            },
            "lighter": {
                "url": self.lighter_mainnet_url,
                "testnet": self.lighter_use_testnet
            },
            "extended": {
                "url": self.extended_testnet_url if self.extended_use_testnet else self.extended_mainnet_url,
                "testnet": self.extended_use_testnet
            },
            "edgex": {
                "url": self.edgex_base_url,
                "ws_url": self.edgex_ws_url,
                "testnet": False
            },
            "vest": {
                "url": self.vest_development_url if self.vest_use_testnet else self.vest_production_url,
                "ws_url": self.vest_ws_development_url if self.vest_use_testnet else self.vest_ws_production_url,
                "testnet": self.vest_use_testnet
            }
        }
        return configs.get(dex_name.lower(), {})
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


class WebSocketSettings(BaseSettings):
    """WebSocket settings"""
    ws_heartbeat_interval: int = Field(default=30, description="Heartbeat interval in seconds")
    ws_max_connections: int = Field(default=1000, description="Maximum connections")
    ws_message_queue_size: int = Field(default=100, description="Message queue size")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


class OrderManagementSettings(BaseSettings):
    """Order management settings"""
    max_orders_per_account: int = Field(default=100, description="Max orders per account")
    order_expiry_seconds: int = Field(default=86400, description="Order expiry in seconds")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


class RiskManagementSettings(BaseSettings):
    """Risk management settings"""
    max_position_size_usd: float = Field(default=100000, description="Max position size in USD")
    max_leverage: int = Field(default=20, description="Maximum leverage")
    margin_call_ratio: float = Field(default=0.8, description="Margin call ratio")
    liquidation_ratio: float = Field(default=0.95, description="Liquidation ratio")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


class NotificationSettings(BaseSettings):
    """Notification settings"""
    notification_webhook_url: Optional[str] = Field(default=None, description="Webhook URL")
    enable_email_notifications: bool = Field(default=False, description="Enable email notifications")
    smtp_host: Optional[str] = Field(default=None, description="SMTP host")
    smtp_port: int = Field(default=587, description="SMTP port")
    smtp_user: Optional[str] = Field(default=None, description="SMTP user")
    smtp_password: Optional[SecretStr] = Field(default=None, description="SMTP password")
    notification_from_email: Optional[str] = Field(default=None, description="From email")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


class Settings(BaseSettings):
    """Main settings class that combines all settings"""
    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    dex: DEXSettings = Field(default_factory=DEXSettings)
    websocket: WebSocketSettings = Field(default_factory=WebSocketSettings)
    order_mgmt: OrderManagementSettings = Field(default_factory=OrderManagementSettings)
    risk_mgmt: RiskManagementSettings = Field(default_factory=RiskManagementSettings)
    notification: NotificationSettings = Field(default_factory=NotificationSettings)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env
    
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.app.app_env == "production"
    
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.app.app_env == "development"
    
    def is_testing(self) -> bool:
        """Check if running in testing"""
        return self.app.app_env == "testing"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Use this function to get settings throughout the application.
    """
    return Settings()


# Create a global settings instance
settings = get_settings()