"""
CLI configuration management.
"""
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml
from pydantic import BaseModel, Field
from cryptography.fernet import Fernet
import keyring


class DisplayConfig(BaseModel):
    """Display configuration."""
    colors: bool = True
    table_style: str = "fancy"
    decimal_places: int = 4
    show_timestamps: bool = True


class MonitoringConfig(BaseModel):
    """Monitoring configuration."""
    refresh_interval: int = Field(default=1000, description="Refresh interval in milliseconds")
    max_rows: int = 100


class TradingConfig(BaseModel):
    """Trading configuration."""
    confirm_orders: bool = True
    default_leverage: int = 10
    max_position_size: float = Field(default=100000, description="Maximum position size in USD")


class WebSocketConfig(BaseModel):
    """WebSocket configuration."""
    reconnect_attempts: int = 5
    timeout: int = Field(default=30000, description="Timeout in milliseconds")


class AccountConfig(BaseModel):
    """Account configuration."""
    name: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    wallet: Optional[str] = None
    testnet: bool = False


class CLIConfig(BaseModel):
    """CLI configuration."""
    default_dex: Optional[str] = None
    default_account: Optional[str] = None
    accounts: Dict[str, List[AccountConfig]] = {}
    display: DisplayConfig = DisplayConfig()
    monitoring: MonitoringConfig = MonitoringConfig()
    trading: TradingConfig = TradingConfig()
    websocket: WebSocketConfig = WebSocketConfig()


def get_config_dir() -> Path:
    """Get the configuration directory."""
    config_dir = Path.home() / ".perp-dex"
    config_dir.mkdir(exist_ok=True)
    return config_dir


def get_config_file() -> Path:
    """Get the configuration file path."""
    return get_config_dir() / "config.yaml"


def load_config() -> CLIConfig:
    """Load configuration from file."""
    config_file = get_config_file()
    
    if config_file.exists():
        with open(config_file, "r") as f:
            data = yaml.safe_load(f) or {}
        
        # Process environment variables
        data = process_env_vars(data)
        
        return CLIConfig(**data)
    
    return CLIConfig()


def save_config(config: CLIConfig):
    """Save configuration to file."""
    config_file = get_config_file()
    
    with open(config_file, "w") as f:
        yaml.dump(config.model_dump(), f, default_flow_style=False)


def process_env_vars(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process environment variables in configuration."""
    import re
    
    def replace_env_vars(value):
        if isinstance(value, str):
            # Replace ${VAR_NAME} with environment variable
            pattern = r'\$\{([^}]+)\}'
            
            def replacer(match):
                env_var = match.group(1)
                return os.environ.get(env_var, match.group(0))
            
            return re.sub(pattern, replacer, value)
        elif isinstance(value, dict):
            return {k: replace_env_vars(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [replace_env_vars(item) for item in value]
        return value
    
    return replace_env_vars(data)


class CredentialManager:
    """Manage encrypted credentials."""
    
    SERVICE_NAME = "perp-dex-cli"
    
    @classmethod
    def get_or_create_key(cls) -> bytes:
        """Get or create encryption key."""
        key = keyring.get_password(cls.SERVICE_NAME, "encryption_key")
        
        if not key:
            # Generate new key
            key = Fernet.generate_key().decode()
            keyring.set_password(cls.SERVICE_NAME, "encryption_key", key)
        
        return key.encode()
    
    @classmethod
    def encrypt_credential(cls, credential: str) -> str:
        """Encrypt a credential."""
        key = cls.get_or_create_key()
        f = Fernet(key)
        return f.encrypt(credential.encode()).decode()
    
    @classmethod
    def decrypt_credential(cls, encrypted: str) -> str:
        """Decrypt a credential."""
        key = cls.get_or_create_key()
        f = Fernet(key)
        return f.decrypt(encrypted.encode()).decode()
    
    @classmethod
    def store_account_credential(cls, dex: str, account: str, key_type: str, value: str):
        """Store account credential securely."""
        keyring.set_password(
            cls.SERVICE_NAME,
            f"{dex}:{account}:{key_type}",
            value
        )
    
    @classmethod
    def get_account_credential(cls, dex: str, account: str, key_type: str) -> Optional[str]:
        """Get account credential."""
        return keyring.get_password(
            cls.SERVICE_NAME,
            f"{dex}:{account}:{key_type}"
        )
    
    @classmethod
    def delete_account_credential(cls, dex: str, account: str, key_type: str):
        """Delete account credential."""
        try:
            keyring.delete_password(
                cls.SERVICE_NAME,
                f"{dex}:{account}:{key_type}"
            )
        except keyring.errors.PasswordDeleteError:
            pass  # Already deleted


def get_account_credentials(dex: str, account_name: str) -> Dict[str, str]:
    """Get complete account credentials."""
    config = load_config()
    
    if dex not in config.accounts:
        raise ValueError(f"No accounts configured for {dex}")
    
    account = None
    for acc in config.accounts[dex]:
        if acc.name == account_name:
            account = acc
            break
    
    if not account:
        raise ValueError(f"Account {account_name} not found for {dex}")
    
    credentials = {}
    
    # Get API key
    if account.api_key:
        credentials["api_key"] = account.api_key
    else:
        api_key = CredentialManager.get_account_credential(dex, account_name, "api_key")
        if api_key:
            credentials["api_key"] = api_key
    
    # Get API secret
    if account.api_secret:
        credentials["api_secret"] = account.api_secret
    else:
        api_secret = CredentialManager.get_account_credential(dex, account_name, "api_secret")
        if api_secret:
            credentials["api_secret"] = api_secret
    
    # Get wallet address if applicable
    if account.wallet:
        credentials["wallet"] = account.wallet
    
    credentials["testnet"] = account.testnet
    
    return credentials