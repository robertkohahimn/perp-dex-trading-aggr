"""
Connector factory for creating DEX connector instances.
"""
from typing import Dict, Type, Optional, List
from enum import Enum
from .base import BaseConnector, ConnectorConfig, ConnectorException


class DEXProvider(Enum):
    """Supported DEX providers"""
    HYPERLIQUID = "hyperliquid"
    LIGHTER = "lighter"
    EXTENDED = "extended"
    EDGEX = "edgex"
    VEST = "vest"


class ConnectorFactory:
    """Factory for creating connector instances"""
    
    _connectors: Dict[str, Type[BaseConnector]] = {}
    
    @classmethod
    def register_connector(
        cls, 
        provider: DEXProvider, 
        connector_class: Type[BaseConnector]
    ) -> None:
        """
        Register a connector class for a provider
        
        Args:
            provider: DEX provider enum
            connector_class: Connector class to register
        """
        cls._connectors[provider.value] = connector_class
    
    @classmethod
    def create_connector(
        cls, 
        provider: str, 
        config: Optional[ConnectorConfig] = None,
        **kwargs
    ) -> BaseConnector:
        """
        Create a connector instance
        
        Args:
            provider: Provider name (string or DEXProvider enum)
            config: Optional connector configuration
            **kwargs: Additional configuration parameters
        
        Returns:
            Connector instance
        
        Raises:
            ConnectorException: If provider is not supported
        """
        # Convert to lowercase string if enum provided
        if isinstance(provider, DEXProvider):
            provider_key = provider.value
        else:
            provider_key = provider.lower()
        
        # Check if provider is registered
        if provider_key not in cls._connectors:
            # Try to auto-import the connector
            cls._auto_import_connector(provider_key)
        
        if provider_key not in cls._connectors:
            raise ConnectorException(
                f"Connector for provider '{provider}' not found. "
                f"Available providers: {list(cls._connectors.keys())}"
            )
        
        # Create config if not provided
        if config is None:
            config = ConnectorConfig(name=provider_key, **kwargs)
        
        # Create and return connector instance
        connector_class = cls._connectors[provider_key]
        return connector_class(config)
    
    @classmethod
    def _auto_import_connector(cls, provider: str) -> None:
        """
        Attempt to auto-import a connector module
        
        Args:
            provider: Provider name
        """
        try:
            # Try to import the connector module
            if provider == "hyperliquid":
                from .hyperliquid.connector import HyperliquidConnector
                cls.register_connector(DEXProvider.HYPERLIQUID, HyperliquidConnector)
            elif provider == "lighter":
                from .lighter.connector import LighterConnector
                cls.register_connector(DEXProvider.LIGHTER, LighterConnector)
            elif provider == "extended":
                from .extended.connector import ExtendedConnector
                cls.register_connector(DEXProvider.EXTENDED, ExtendedConnector)
            elif provider == "edgex":
                from .edgex.connector import EdgeXConnector
                cls.register_connector(DEXProvider.EDGEX, EdgeXConnector)
            elif provider == "vest":
                from .vest.connector import VestConnector
                cls.register_connector(DEXProvider.VEST, VestConnector)
            elif provider == "mock" or provider == "test":
                from .mock.connector import MockConnector
                cls._connectors[provider] = MockConnector
        except ImportError:
            # Connector not implemented yet - use mock as fallback
            try:
                from .mock.connector import MockConnector
                cls._connectors[provider] = MockConnector
            except ImportError:
                pass
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """
        Get list of available providers
        
        Returns:
            List of provider names
        """
        # Try to import all connectors
        for provider in DEXProvider:
            cls._auto_import_connector(provider.value)
        
        return list(cls._connectors.keys())
    
    @classmethod
    def is_provider_available(cls, provider: str) -> bool:
        """
        Check if a provider is available
        
        Args:
            provider: Provider name
        
        Returns:
            True if provider is available
        """
        if isinstance(provider, DEXProvider):
            provider = provider.value
        else:
            provider = provider.lower()
        
        # Try to import if not already registered
        if provider not in cls._connectors:
            cls._auto_import_connector(provider)
        
        return provider in cls._connectors


# Convenience function
def create_connector(
    provider: str,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    testnet: bool = False,
    **kwargs
) -> BaseConnector:
    """
    Convenience function to create a connector
    
    Args:
        provider: DEX provider name
        api_key: API key
        api_secret: API secret
        testnet: Use testnet if True
        **kwargs: Additional configuration
    
    Returns:
        Connector instance
    """
    config = ConnectorConfig(
        name=provider,
        api_key=api_key,
        api_secret=api_secret,
        testnet=testnet,
        metadata=kwargs
    )
    return ConnectorFactory.create_connector(provider, config)