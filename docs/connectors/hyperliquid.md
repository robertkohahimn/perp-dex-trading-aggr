# Hyperliquid Connector Documentation

## Overview

The Hyperliquid connector provides integration with the Hyperliquid perpetual DEX, which operates on Arbitrum. It implements the full BaseConnector interface for seamless integration with the trading backend.

## Features

- **EVM-style Authentication**: Uses Ethereum private keys for signing transactions
- **Full Order Management**: Place, cancel, modify orders with multiple order types
- **Position Tracking**: Real-time position monitoring with PnL calculations
- **Market Data**: Access to order books, recent trades, and funding rates
- **WebSocket Support**: Real-time updates for orders, positions, and market data
- **Testnet Support**: Seamless switching between mainnet and testnet environments

## Configuration

### Basic Setup

```python
from connectors.hyperliquid.connector import HyperliquidConnector

# Create connector for testnet
connector = HyperliquidConnector(use_testnet=True)

# Or for mainnet
connector = HyperliquidConnector(use_testnet=False)
```

### Authentication

Hyperliquid requires an Ethereum private key for authentication:

```python
credentials = {
    "private_key": "0x1234567890abcdef...",  # Your private key
    "vault_address": "0xabc123..."  # Optional: vault address for delegated trading
}

await connector.authenticate(credentials)
```

## API Methods

### Order Management

#### Place Order
```python
from connectors.base import OrderRequest, OrderType, OrderSide, TimeInForce
from decimal import Decimal

# Limit order
order = OrderRequest(
    symbol="BTC-PERP",
    side=OrderSide.BUY,
    order_type=OrderType.LIMIT,
    quantity=Decimal("0.1"),
    price=Decimal("50000"),
    time_in_force=TimeInForce.GTC,
    reduce_only=False  # Optional
)

response = await connector.place_order(order)
```

#### Cancel Order
```python
success = await connector.cancel_order(
    symbol="BTC-PERP",
    order_id="123456"
)
```

#### Modify Order
```python
# Hyperliquid uses cancel-and-replace for modifications
modified = await connector.modify_order(
    symbol="BTC-PERP",
    order_id="123456",
    modifications={
        "price": Decimal("51000"),
        "quantity": Decimal("0.2")
    }
)
```

#### Get Orders
```python
# Get all open orders
orders = await connector.get_open_orders()

# Get orders for specific symbol
orders = await connector.get_orders(symbol="BTC-PERP")

# Get specific order
order = await connector.get_order(
    symbol="BTC-PERP",
    order_id="123456"
)
```

### Position Management

#### Get Positions
```python
# Get all positions
positions = await connector.get_positions()

# Get position for specific symbol
positions = await connector.get_positions(symbol="BTC-PERP")
```

#### Close Position
```python
# Close entire position
order_response = await connector.close_position(symbol="BTC-PERP")

# Close partial position
order_response = await connector.close_position(
    symbol="BTC-PERP",
    quantity=Decimal("0.05")
)
```

### Account Information

#### Get Account Info
```python
account_info = await connector.get_account_info()

# Returns AccountInfo with:
# - equity: Total account value
# - balance: Available balance
# - margin_used: Margin in use
# - free_margin: Available margin
# - position_value: Total position value
# - unrealized_pnl: Unrealized profit/loss
# - realized_pnl: Realized profit/loss
```

#### Get Balances
```python
# Get all balances
balances = await connector.get_balance()

# Get specific asset balance
usdc_balance = await connector.get_balance("USDC")
```

#### Set Leverage
```python
success = await connector.set_leverage(
    symbol="BTC-PERP",
    leverage=10
)
```

### Market Data

#### Get Market Data
```python
market_data = await connector.get_market_data("BTC-PERP")

# Returns MarketData with:
# - symbol
# - mark_price
# - index_price
# - last_price
# - bid_price
# - ask_price
# - volume_24h
# - open_interest
# - funding_rate
# - next_funding_time
```

#### Get Order Book
```python
order_book = await connector.get_order_book(
    symbol="BTC-PERP",
    depth=20  # Number of levels
)

# Returns dict with:
# - symbol
# - bids: [[price, quantity], ...]
# - asks: [[price, quantity], ...]
# - timestamp
```

#### Get Recent Trades
```python
trades = await connector.get_recent_trades(
    symbol="BTC-PERP",
    limit=100
)

# Returns list of trades with:
# - symbol
# - price
# - quantity
# - side (BUY/SELL)
# - timestamp
```

#### Get Funding Rate
```python
funding = await connector.get_funding_rate("BTC-PERP")

# Returns dict with:
# - symbol
# - funding_rate
# - next_funding_time
# - timestamp
```

### WebSocket Subscriptions

```python
# Subscribe to real-time updates
async for update in connector.subscribe_to_updates(["orders", "positions"]):
    print(f"Update received: {update}")

# Available channels:
# - "orders": Order updates
# - "positions": Position updates
# - "ticker:BTC-PERP": Market data for specific symbol
# - "orderbook:BTC-PERP": Order book updates
```

## Error Handling

The connector raises specific exceptions for different error scenarios:

```python
from app.core.exceptions import (
    AuthenticationError,  # Authentication failures
    ConnectorError,       # General connector errors
    OrderNotFoundError,   # Order not found
    InsufficientBalanceError,  # Insufficient balance
    InvalidOrderError,    # Invalid order parameters
    RateLimitError,      # Rate limit exceeded
)

try:
    await connector.place_order(order)
except InsufficientBalanceError as e:
    print(f"Insufficient balance: {e}")
except InvalidOrderError as e:
    print(f"Invalid order: {e}")
except ConnectorError as e:
    print(f"Connector error: {e}")
```

## Trading Fees

Hyperliquid has standard trading fees:
- **Maker Fee**: 0.02% (0.0002)
- **Taker Fee**: 0.05% (0.0005)

```python
fees = await connector.get_trading_fees("BTC-PERP")
```

## Symbol Format

Hyperliquid uses a specific symbol format:
- **Input Format**: `BTC-PERP`, `ETH-PERP`
- **Internal Format**: `BTC`, `ETH` (without -PERP suffix)

The connector handles this conversion automatically.

## Rate Limits

Hyperliquid has rate limits that the connector respects:
- The connector will raise `RateLimitError` when limits are exceeded
- Implement exponential backoff for retries

## Connection Management

```python
# Establish connection
await connector.connect()

# Check connection status
is_connected = connector.session is not None

# Disconnect
await connector.disconnect()
```

## Best Practices

1. **Error Handling**: Always wrap API calls in try-except blocks
2. **Rate Limiting**: Implement retry logic with exponential backoff
3. **WebSocket Reconnection**: Handle disconnections gracefully
4. **Testnet First**: Test thoroughly on testnet before mainnet
5. **Private Key Security**: Never log or expose private keys
6. **Order Validation**: Validate order parameters before submission

## Example: Complete Trading Flow

```python
from connectors.hyperliquid.connector import HyperliquidConnector
from connectors.base import OrderRequest, OrderType, OrderSide, TimeInForce
from decimal import Decimal

async def trading_example():
    # Initialize connector
    connector = HyperliquidConnector(use_testnet=True)
    
    # Authenticate
    await connector.authenticate({
        "private_key": "0x..."
    })
    
    # Check account balance
    account_info = await connector.get_account_info()
    print(f"Available balance: {account_info.free_margin}")
    
    # Get market data
    market_data = await connector.get_market_data("BTC-PERP")
    print(f"Current BTC price: {market_data.mark_price}")
    
    # Place a limit order
    order = OrderRequest(
        symbol="BTC-PERP",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.01"),
        price=market_data.mark_price - Decimal("100"),  # Buy $100 below market
        time_in_force=TimeInForce.GTC
    )
    
    order_response = await connector.place_order(order)
    print(f"Order placed: {order_response.order_id}")
    
    # Monitor position
    positions = await connector.get_positions()
    for position in positions:
        print(f"Position: {position.symbol} {position.side} {position.quantity}")
        print(f"PnL: {position.unrealized_pnl}")
    
    # Close connection
    await connector.disconnect()

# Run the example
import asyncio
asyncio.run(trading_example())
```

## Limitations

1. **Order Modification**: Hyperliquid doesn't support direct order modification; the connector implements modify as cancel-and-replace
2. **Historical Data**: Limited historical data available through the API
3. **Complex Order Types**: Only limit and market orders are fully supported

## Troubleshooting

### Authentication Issues
- Ensure private key has 0x prefix
- Check that the account has sufficient balance
- Verify testnet/mainnet setting matches your key

### Order Placement Failures
- Check symbol format (should be like "BTC-PERP")
- Verify order size meets minimum requirements
- Ensure sufficient margin available

### WebSocket Disconnections
- Implement reconnection logic with exponential backoff
- Monitor connection status and reconnect as needed

## Support

For issues or questions:
1. Check the error messages and logs
2. Verify API status at Hyperliquid's status page
3. Consult the main project documentation
4. Open an issue in the project repository