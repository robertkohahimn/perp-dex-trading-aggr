# Lighter DEX Connector

## Overview
The Lighter connector provides integration with the Lighter perpetual DEX on zkSync. It uses the official Lighter Python SDK for all operations.

## Installation

```bash
pip install git+https://github.com/elliottech/lighter-python.git
```

## Configuration

### Environment
- **Mainnet**: https://mainnet.zklighter.elliot.ai
- **Testnet**: https://testnet.zklighter.elliot.ai

### Authentication
Requires an Ethereum private key for authenticated operations:
```python
credentials = {'private_key': 'your_private_key_here'}
await connector.authenticate(credentials)
```

## Features

### Implemented
- ✅ Connection management
- ✅ Symbol to market ID mapping
- ✅ Market data retrieval
- ✅ Order book data
- ✅ Recent trades
- ✅ Authentication
- ✅ Account information
- ✅ Position management
- ✅ Order placement (limit, market, stop orders)
- ✅ Order cancellation
- ✅ Order modification
- ✅ Leverage adjustment

### Limitations
- Market data may have incomplete bid/ask information
- Funding rates not directly exposed by API
- WebSocket support requires additional implementation

## Usage Example

```python
from connectors.lighter import LighterConnector
from connectors.base import ConnectorConfig, OrderRequest, OrderSide, OrderType
from decimal import Decimal

# Initialize connector
config = ConnectorConfig(name="lighter", testnet=False)
connector = LighterConnector(config)

# Connect
await connector.connect()

# Get market data
market_data = await connector.get_market_data("ETH-PERP")
print(f"ETH Price: ${market_data.last_price}")

# Get order book
order_book = await connector.get_order_book("ETH-PERP", depth=10)
print(f"Best Bid: ${order_book.bids[0].price}")
print(f"Best Ask: ${order_book.asks[0].price}")

# Authenticate for trading
await connector.authenticate({'private_key': 'your_key'})

# Place order
order = OrderRequest(
    symbol="ETH-PERP",
    side=OrderSide.BUY,
    order_type=OrderType.LIMIT,
    quantity=Decimal("0.1"),
    price=Decimal("3000")
)
response = await connector.place_order(order)
print(f"Order placed: {response.order_id}")

# Disconnect
await connector.disconnect()
```

## Market Symbols

Lighter uses numeric market IDs internally. The connector automatically handles symbol mapping:
- ETH-PERP → Market ID 0
- BTC-PERP → Market ID 1
- Other symbols are dynamically mapped on connection

## Testing

Use the test script to verify functionality:
```bash
python test_lighter_connector.py
```

For authenticated testing:
```bash
export LIGHTER_PRIVATE_KEY='your_private_key'
python test_lighter_connector.py
```

## Implementation Notes

1. **Market ID Mapping**: The SDK uses numeric market IDs rather than string symbols. The connector builds a mapping on connection.

2. **Timestamp Handling**: Lighter returns timestamps in microseconds, which the connector converts to datetime objects.

3. **Order Types**: Supports limit, market, stop, and stop-limit orders through the SignerClient.

4. **Error Handling**: SDK-specific errors are caught and wrapped in ConnectorException for consistency.

## Dependencies
- lighter-sdk >= 0.1.4
- eth-account >= 0.13.4
- aiohttp >= 3.0.0
- websockets >= 12.0.0

## Status
✅ Production ready for basic trading operations
⚠️ WebSocket support needs additional implementation
⚠️ Some market data fields may be incomplete