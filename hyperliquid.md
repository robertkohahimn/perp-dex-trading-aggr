# Hyperliquid API/SDK Documentation

## Overview
Hyperliquid is a performant perpetual DEX with comprehensive API support and official SDKs.

## API Endpoints
- **Mainnet**: https://api.hyperliquid.xyz
- **Testnet**: https://api.hyperliquid-testnet.xyz

## Official SDKs
- **Python SDK**: https://github.com/hyperliquid-dex/hyperliquid-python-sdk
- **Rust SDK**: https://github.com/hyperliquid-dex/hyperliquid-rust-sdk
- **Community TypeScript SDKs**: Available from community developers

## Python SDK Installation
```bash
pip install hyperliquid-python-sdk
```

Requirements:
- Python 3.10+
- Poetry for dependency management (if building from source)

## Authentication

### Setup Process
1. Create configuration file with wallet credentials:
```json
{
  "account_address": "0x...", // Your public key
  "secret_key": "0x..."       // Your private key
}
```

2. Optional: Generate API key at https://app.hyperliquid.xyz/API for enhanced rate limits

### Authentication Method
- Uses wallet-based signing with nonces
- Each request requires signature verification
- Private key used for signing transactions

## Core SDK Classes

### Info Class
Retrieves market and account information:
```python
from hyperliquid.info import Info
from hyperliquid.utils import constants

# Initialize Info client
info = Info(constants.MAINNET_API_URL, skip_ws=False)

# Get user state
user_state = info.user_state("0xaddress")

# Get market data
market_data = info.meta()
```

### Exchange Class
Executes trading operations:
```python
from hyperliquid.exchange import Exchange

# Initialize Exchange client
exchange = Exchange(wallet, constants.MAINNET_API_URL)

# Place order
order = exchange.place_order(
    coin="BTC",
    is_buy=True,
    sz=0.01,
    limit_px=50000,
    order_type={"limit": {"tif": "Gtc"}}
)

# Cancel order
cancel_result = exchange.cancel_order(
    coin="BTC",
    o=order_id
)

# Cancel all orders
exchange.cancel_all_orders()
```

## Main Trading Operations

### 1. Place Order
```python
order_result = exchange.place_order(
    coin="BTC",                    # Trading pair
    is_buy=True,                   # True for buy, False for sell
    sz=0.01,                        # Size in base currency
    limit_px=50000,                 # Limit price
    order_type={                    # Order type configuration
        "limit": {"tif": "Gtc"}    # Good-til-cancelled
    },
    reduce_only=False,              # Optional: reduce-only order
    post_only=False                 # Optional: post-only order
)
```

### 2. Cancel Order
```python
cancel_result = exchange.cancel_order(
    coin="BTC",
    o=order_id  # Order ID to cancel
)
```

### 3. Modify Order
```python
modify_result = exchange.modify_order(
    coin="BTC",
    oid=order_id,
    new_sz=0.02,        # New size
    new_limit_px=51000  # New limit price
)
```

### 4. Get Positions
```python
positions = info.user_state(address)["assetPositions"]
```

### 5. Get Account Info
```python
account_info = info.user_state(address)
# Returns: balances, positions, open orders, margin info
```

### 6. Get Open Orders
```python
open_orders = info.user_state(address)["openOrders"]
```

### 7. Get Order History
```python
fills = info.user_fills(address)
```

## WebSocket Support

### Connection
```python
from hyperliquid.info import Info

# Initialize with WebSocket
info = Info(constants.MAINNET_API_URL, skip_ws=False)

# Subscribe to channels
info.subscribe({
    "type": "orderUpdates",
    "user": "0xaddress"
})

# Subscribe to market data
info.subscribe({
    "type": "l2Book",
    "coin": "BTC"
})
```

### Available Channels
- `orderUpdates` - Order status updates
- `userFills` - Trade executions
- `l2Book` - Order book updates
- `trades` - Recent trades
- `allMids` - Mid prices for all markets
- `notification` - Account notifications

### WebSocket Features
- Automatic reconnection
- Heartbeat mechanism
- Request-response pattern support
- Subscription management

## Rate Limits

### Standard Limits
- Info requests: 20 requests per second
- Exchange requests: 10 requests per second
- WebSocket connections: 5 per IP

### Enhanced Limits (with API key)
- Info requests: 100 requests per second
- Exchange requests: 50 requests per second
- WebSocket connections: 10 per IP

### Rate Limit Headers
Response headers include:
- `X-RateLimit-Limit`: Request limit
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Reset timestamp

## Market Data

### Get All Markets
```python
meta = info.meta()
markets = meta["universe"]  # List of all trading pairs
```

### Get Order Book
```python
l2_data = info.l2_snapshot(coin="BTC")
# Returns: {"bids": [[price, size], ...], "asks": [[price, size], ...]}
```

### Get Recent Trades
```python
trades = info.trades(coin="BTC")
```

### Get Funding Rate
```python
funding = info.funding_history(coin="BTC", start_time=start_ts)
```

## Order Types

### Limit Orders
```python
order_type = {"limit": {"tif": "Gtc"}}  # Good-til-cancelled
order_type = {"limit": {"tif": "Alo"}}  # Add-liquidity-only (post-only)
order_type = {"limit": {"tif": "Ioc"}}  # Immediate-or-cancel
```

### Market Orders
```python
order_type = {"market": {}}
```

### Stop Orders
```python
order_type = {
    "stop": {
        "trigger_px": 55000,
        "is_market": True,  # Market order when triggered
        "tpsl": "tp"       # Take-profit
    }
}
```

## Error Handling

### Common Error Codes
- `INSUFFICIENT_BALANCE`: Not enough margin
- `INVALID_PRICE`: Price outside valid range
- `INVALID_SIZE`: Size below minimum or above maximum
- `RATE_LIMIT_EXCEEDED`: Too many requests
- `ORDER_NOT_FOUND`: Order ID doesn't exist
- `REDUCE_ONLY_VIOLATION`: Position would increase

### Error Response Format
```python
{
    "error": "ERROR_CODE",
    "message": "Detailed error message"
}
```

## Best Practices

### Connection Management
1. Reuse connection instances
2. Implement exponential backoff for retries
3. Handle WebSocket disconnections gracefully
4. Use connection pooling for high throughput

### Order Management
1. Always store order IDs for tracking
2. Implement idempotency with client order IDs
3. Use reduce-only orders for closing positions
4. Monitor order status via WebSocket

### Risk Management
1. Check available margin before placing orders
2. Implement position size limits
3. Use stop-loss orders for risk management
4. Monitor funding rates for perpetuals

## Code Examples

### Complete Trading Flow
```python
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants
import json

# Load configuration
with open("config.json") as f:
    config = json.load(f)

# Initialize clients
info = Info(constants.MAINNET_API_URL)
exchange = Exchange(config["secret_key"], constants.MAINNET_API_URL)

# Get account info
account = info.user_state(config["account_address"])
print(f"Balance: {account['marginSummary']['accountValue']}")

# Get market data
l2 = info.l2_snapshot("BTC")
best_bid = l2["bids"][0][0] if l2["bids"] else 0
best_ask = l2["asks"][0][0] if l2["asks"] else 0

# Place limit order
order = exchange.place_order(
    coin="BTC",
    is_buy=True,
    sz=0.001,
    limit_px=best_bid,
    order_type={"limit": {"tif": "Gtc"}}
)
print(f"Order placed: {order}")

# Monitor position
positions = info.user_state(config["account_address"])["assetPositions"]
for position in positions:
    if position["coin"] == "BTC":
        print(f"Position: {position['szi']} @ {position['entryPx']}")

# Cancel order
if order["response"]["data"]["statuses"][0]["resting"]:
    order_id = order["response"]["data"]["statuses"][0]["oid"]
    cancel = exchange.cancel_order(coin="BTC", o=order_id)
    print(f"Order cancelled: {cancel}")
```

## Testing

### Testnet Configuration
```python
from hyperliquid.utils import constants

# Use testnet URL
info = Info(constants.TESTNET_API_URL)
exchange = Exchange(wallet, constants.TESTNET_API_URL)
```

### Testnet Faucet
- Get testnet funds at: https://app.hyperliquid-testnet.xyz/faucet

## Additional Resources

- Official Documentation: https://hyperliquid.gitbook.io/hyperliquid-docs/
- API Reference: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api
- GitHub Examples: https://github.com/hyperliquid-dex/hyperliquid-python-sdk/tree/master/examples
- Discord Community: For technical support

## Implementation Notes for Our Backend

### Priority Features
1. Use official Python SDK for stability
2. Implement WebSocket for real-time updates
3. Handle rate limits with request queuing
4. Store order IDs for tracking and reconciliation

### Architecture Considerations
1. Single WebSocket connection per account
2. Separate Info client for read operations
3. Exchange client pool for concurrent orders
4. Redis cache for market data

### Security Considerations
1. Never log private keys
2. Use environment variables for credentials
3. Implement request signing verification
4. Rate limit client requests before forwarding