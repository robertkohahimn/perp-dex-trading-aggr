# Extended DEX Connector Documentation

## Overview

The Extended connector provides integration with Extended, a derivatives DEX built on Starknet. This implementation uses the REST API directly since the Python SDK requires Python 3.10+ and our environment has Python 3.9.6.

## Features

- **REST API Implementation**: Direct API integration without SDK dependency
- **Starknet Integration**: Full support for Starknet-based operations
- **Comprehensive Trading**: Support for spot and perpetual futures
- **Account Management**: Multi-account support with sub-accounts
- **Advanced Orders**: Limit, market, stop-loss, and take-profit orders
- **Position Management**: Long/short positions with leverage
- **Real-time Data**: Market data, orderbook, and trade feeds
- **Safety Features**: Built-in rate limiting and error handling

## Architecture

### Components

1. **ExtendedConnector**: Main connector class implementing BaseConnector
2. **REST API Client**: Direct HTTP client with authentication
3. **Starknet Signer**: Integration with starknet-py for transaction signing
4. **Market Cache**: Local cache for market information and mappings

### Key Design Decisions

1. **REST API over SDK**: Due to Python version incompatibility (SDK requires 3.10+)
2. **Rate Limiting**: Built-in delays between requests to respect API limits
3. **Market ID Mapping**: Automatic mapping between symbols and internal IDs
4. **Error Recovery**: Comprehensive error handling with specific exceptions

## Installation

```bash
# Install required dependencies
pip install aiohttp
pip install starknet-py

# Extended SDK (requires Python 3.10+, not used in this implementation)
# pip install extended-sdk  # Not compatible with Python 3.9.6
```

## Configuration

### Environment Variables

```bash
# Starknet credentials
EXTENDED_PRIVATE_KEY=your_starknet_private_key
EXTENDED_ACCOUNT_ADDRESS=your_starknet_account_address

# API credentials (optional for authenticated endpoints)
EXTENDED_API_KEY=your_api_key
EXTENDED_API_SECRET=your_api_secret

# Network selection
EXTENDED_USE_TESTNET=true  # or false for mainnet
```

### Connector Configuration

```python
from connectors.base import ConnectorConfig
from connectors.extended.connector import ExtendedConnector

config = ConnectorConfig(
    name="extended",
    testnet=True,  # Use testnet for testing
    rate_limit=10  # requests per minute
)

connector = ExtendedConnector(config)
```

## Usage Examples

### Basic Connection

```python
import asyncio
from connectors.extended.connector import ExtendedConnector
from connectors.base import ConnectorConfig

async def connect_example():
    # Create connector
    config = ConnectorConfig(name="extended", testnet=True)
    connector = ExtendedConnector(config)
    
    # Connect with credentials
    connected = await connector.connect(
        private_key="your_private_key",
        account_address="your_account_address",
        api_key="your_api_key",  # Optional
        api_secret="your_api_secret"  # Optional
    )
    
    if connected:
        print("Connected to Extended!")
        
        # Get account balance
        balance = await connector.get_balance("USDC")
        print(f"Balance: ${balance['available']:,.2f}")
        
        # Disconnect
        await connector.disconnect()

asyncio.run(connect_example())
```

### Market Data

```python
async def market_data_example():
    connector = ExtendedConnector(config)
    await connector.connect(**credentials)
    
    # Get market data
    market = await connector.get_market_data("BTC-USD")
    print(f"BTC Price: ${market['last']:,.2f}")
    print(f"24h Volume: ${market['volume_24h']:,.0f}")
    print(f"Funding Rate: {market['funding_rate']:.4%}")
    
    # Get orderbook
    orderbook = await connector.get_orderbook("BTC-USD", depth=10)
    print(f"Best Bid: ${orderbook['bids'][0][0]:,.2f}")
    print(f"Best Ask: ${orderbook['asks'][0][0]:,.2f}")
    
    # Get recent trades
    trades = await connector.get_trades("BTC-USD", limit=50)
    for trade in trades[:5]:
        print(f"Trade: {trade['side']} {trade['quantity']} @ ${trade['price']:,.2f}")
```

### Order Management

```python
async def order_example():
    connector = ExtendedConnector(config)
    await connector.connect(**credentials)
    
    # Place limit order
    order = await connector.place_order(
        symbol="BTC-USD",
        side="buy",
        order_type="limit",
        quantity=0.001,
        price=30000,
        post_only=True  # Maker only
    )
    print(f"Order placed: {order['order_id']}")
    
    # Check order status
    order_details = await connector.get_order(order['order_id'])
    print(f"Status: {order_details['status']}")
    print(f"Filled: {order_details['filled']}/{order_details['quantity']}")
    
    # Cancel order
    cancelled = await connector.cancel_order(order['order_id'])
    print(f"Cancelled: {cancelled}")
    
    # Get all orders
    orders = await connector.get_orders(status="open")
    for o in orders:
        print(f"Order {o['order_id']}: {o['side']} {o['quantity']} @ {o['price']}")
```

### Position Management

```python
async def position_example():
    connector = ExtendedConnector(config)
    await connector.connect(**credentials)
    
    # Set leverage
    await connector.set_leverage("BTC-USD", 10)
    
    # Open position
    order = await connector.place_order(
        symbol="BTC-USD",
        side="buy",
        order_type="market",
        quantity=0.01
    )
    
    # Get positions
    positions = await connector.get_positions()
    for pos in positions:
        print(f"Position: {pos['symbol']}")
        print(f"  Side: {pos['side']}")
        print(f"  Size: {pos['size']}")
        print(f"  Entry: ${pos['entry_price']:,.2f}")
        print(f"  PnL: ${pos['pnl']:,.2f}")
        print(f"  Leverage: {pos['leverage']}x")
    
    # Close position
    close_order = await connector.close_position("BTC-USD")
    print(f"Position closed: {close_order['order_id']}")
```

## API Methods

### Connection Methods

- `connect(**credentials)`: Connect to Extended with credentials
- `disconnect()`: Close connection and clean up resources
- `is_connected()`: Check if connector is connected

### Trading Methods

- `place_order(symbol, side, order_type, quantity, price=None, **kwargs)`: Place an order
- `cancel_order(order_id, symbol=None)`: Cancel an order
- `get_order(order_id, symbol=None)`: Get order details
- `get_orders(symbol=None, status=None, limit=100)`: Get multiple orders

### Position Methods

- `get_positions(symbol=None)`: Get open positions
- `close_position(symbol, quantity=None)`: Close a position
- `get_leverage(symbol)`: Get current leverage
- `set_leverage(symbol, leverage)`: Set leverage for a symbol

### Account Methods

- `get_balance(asset="USDC")`: Get account balance
- `get_funding_rate(symbol)`: Get funding rate information

### Market Data Methods

- `get_market_data(symbol)`: Get market ticker data
- `get_orderbook(symbol, depth=20)`: Get order book
- `get_trades(symbol, limit=100)`: Get recent trades

## Error Handling

The connector uses specific exceptions for different error scenarios:

```python
from app.core.exceptions import (
    APIError,
    AuthenticationError,
    InsufficientBalanceError,
    InvalidOrderError,
    OrderNotFoundError,
    RateLimitError
)

try:
    order = await connector.place_order(...)
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
except InvalidOrderError as e:
    print(f"Invalid order: {e}")
except RateLimitError as e:
    print(f"Rate limited: {e}")
    await asyncio.sleep(60)  # Wait before retry
except APIError as e:
    print(f"API error: {e}")
```

## Safety Features

### Rate Limiting

The connector implements automatic rate limiting:

```python
# Built-in delay between requests
connector.rate_limit_delay = 0.1  # 100ms between requests
```

### Market ID Mapping

Automatic handling of symbol variations:

```python
# Supports various symbol formats
"BTC-USD"    -> "BTC-USD-PERP"
"ETH-USD"    -> "ETH-USD-PERP"
"BTC-USDT"   -> "BTC-USDT-PERP"
```

### Connection State Management

```python
# Always check connection before operations
if connector.is_connected():
    # Perform operations
    pass
else:
    # Reconnect
    await connector.connect(**credentials)
```

## Testing

### Unit Tests

Run the comprehensive test suite:

```bash
# Run all Extended tests
pytest tests/test_extended_connector.py -v

# Run specific test
pytest tests/test_extended_connector.py::TestExtendedConnector::test_place_order -v

# Run with coverage
pytest tests/test_extended_connector.py --cov=connectors.extended
```

### Integration Tests

Test with real credentials (testnet recommended):

```bash
# Set credentials
export EXTENDED_PRIVATE_KEY=your_private_key
export EXTENDED_ACCOUNT_ADDRESS=your_account_address
export EXTENDED_API_KEY=your_api_key  # Optional
export EXTENDED_API_SECRET=your_api_secret  # Optional

# Run integration tests (testnet)
python test_extended_real.py

# Run on mainnet (use with caution!)
python test_extended_real.py --mainnet
```

## Troubleshooting

### Common Issues

1. **Connection Failed**
   - Verify credentials are correct
   - Check network connectivity
   - Ensure using correct network (testnet/mainnet)

2. **Authentication Errors**
   - Verify API key and secret
   - Check signature generation
   - Ensure timestamp is synchronized

3. **Order Placement Failed**
   - Check account balance
   - Verify market exists
   - Ensure order parameters are valid
   - Check minimum order size requirements

4. **Rate Limiting**
   - Connector has built-in rate limiting
   - Increase delay if still hitting limits
   - Consider using WebSocket for real-time data

5. **Market Not Found**
   - Symbol format may vary
   - Check available markets with get_market_data
   - Use market ID directly if known

### Debug Logging

Enable detailed logging:

```python
import logging

# Set log level
logging.basicConfig(level=logging.DEBUG)

# Or configure specific logger
logger = logging.getLogger('connectors.extended')
logger.setLevel(logging.DEBUG)
```

## Performance Considerations

1. **Connection Pooling**: Reuse connections when possible
2. **Caching**: Market information is cached locally
3. **Batch Operations**: Group multiple operations when possible
4. **Rate Limiting**: Built-in delays prevent API throttling

## Security Notes

1. **Private Keys**: Never commit private keys to version control
2. **API Credentials**: Store securely, use environment variables
3. **Starknet Security**: Understand Starknet's security model
4. **Test First**: Always test on testnet before mainnet
5. **Monitor Positions**: Set up alerts for position monitoring

## Limitations

1. **Python Version**: SDK requires Python 3.10+, using REST API instead
2. **Starknet Dependencies**: Requires starknet-py for signing
3. **API Rate Limits**: Subject to Extended's rate limiting
4. **Market Coverage**: Limited to Extended's supported markets

## Support Resources

- **Extended API Documentation**: https://api.docs.extended.exchange/
- **Extended Support**: Check Extended's official channels
- **Starknet Documentation**: https://docs.starknet.io/
- **GitHub Issues**: Report connector-specific issues

## Future Enhancements

1. **WebSocket Support**: Real-time data feeds
2. **SDK Integration**: When Python 3.10+ is available
3. **Advanced Orders**: OCO, trailing stop support
4. **Portfolio Analytics**: Built-in PnL tracking
5. **Multi-Account**: Enhanced sub-account management