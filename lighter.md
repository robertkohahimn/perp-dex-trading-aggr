# Lighter API/SDK Documentation

## Overview
Lighter is a perpetual DEX built on zkSync with a Python SDK for API integration.

## API Endpoints
- **Mainnet**: https://mainnet.zklighter.elliot.ai/
- **API Documentation**: https://apibetadocs.lighter.xyz/

## Official SDK
- **Python SDK**: https://github.com/elliottech/lighter-python

## Python SDK Installation
```bash
pip install git+https://github.com/elliottech/lighter-python.git
```

Requirements:
- Python 3.8+
- asyncio support

## Authentication

### API Key Setup
- API key authentication supported
- Configuration through environment variables or direct initialization
- No explicit wallet signing mentioned in documentation

### Client Initialization
```python
import lighter

# Initialize API client
client = lighter.ApiClient()

# Or with custom configuration
client = lighter.ApiClient(
    host="https://mainnet.zklighter.elliot.ai"
)
```

## Core SDK Classes

### ApiClient
Base client for all API interactions:
```python
client = lighter.ApiClient()
```

### AccountApi
Account-related operations:
```python
account_api = lighter.AccountApi(client)

# Get account details
account = await account_api.get_account(by="index", value="1")
account = await account_api.get_account(by="address", value="0x...")

# Get account limits
limits = await account_api.get_account_limits(address="0x...")

# Get active orders
active_orders = await account_api.get_account_active_orders(address="0x...")

# Get inactive orders
inactive_orders = await account_api.get_account_inactive_orders(address="0x...")
```

### OrderApi
Order management operations:
```python
order_api = lighter.OrderApi(client)

# Get order book
order_book = await order_api.get_order_books(market="BTC-USDT")

# Get specific order
order = await order_api.get_order(order_id="...")

# Place order (structure TBD from SDK)
order_result = await order_api.create_order(...)

# Cancel order
cancel_result = await order_api.cancel_order(order_id="...")
```

### TransactionApi
Transaction history and details:
```python
tx_api = lighter.TransactionApi(client)

# Get account transactions
txs = await tx_api.get_account_txs(address="0x...")

# Get all transactions
all_txs = await tx_api.get_txs()

# Get transaction by ID
tx = await tx_api.get_tx(tx_id="...")
```

### BlockApi
Block information:
```python
block_api = lighter.BlockApi(client)

# Get latest block
latest_block = await block_api.get_latest_block()

# Get specific block
block = await block_api.get_block(block_number=12345)
```

## Main Trading Operations

### 1. Place Order
```python
import lighter
import asyncio

async def place_order():
    client = lighter.ApiClient()
    order_api = lighter.OrderApi(client)
    
    # Order placement details to be confirmed from SDK
    order = await order_api.create_order(
        market="BTC-USDT",
        side="buy",
        type="limit",
        size=0.01,
        price=50000,
        # Additional parameters as per SDK
    )
    return order
```

### 2. Cancel Order
```python
async def cancel_order(order_id):
    client = lighter.ApiClient()
    order_api = lighter.OrderApi(client)
    
    result = await order_api.cancel_order(order_id=order_id)
    return result
```

### 3. Get Positions
```python
async def get_positions(address):
    client = lighter.ApiClient()
    account_api = lighter.AccountApi(client)
    
    # Get account details including positions
    account = await account_api.get_account(by="address", value=address)
    positions = account.positions  # Structure depends on API response
    return positions
```

### 4. Get Account Balance
```python
async def get_balance(address):
    client = lighter.ApiClient()
    account_api = lighter.AccountApi(client)
    
    account = await account_api.get_account(by="address", value=address)
    balance = account.balance  # Structure depends on API response
    return balance
```

### 5. Get Open Orders
```python
async def get_open_orders(address):
    client = lighter.ApiClient()
    account_api = lighter.AccountApi(client)
    
    active_orders = await account_api.get_account_active_orders(address=address)
    return active_orders
```

## WebSocket Support

### WebSocket Connection
```python
# From examples/ws.py
import lighter
import asyncio

async def sync_orderbook():
    client = lighter.ApiClient()
    ws = lighter.WebSocketClient(client)
    
    # Subscribe to order book updates
    await ws.subscribe_orderbook("BTC-USDT")
    
    async for update in ws.stream_orderbook():
        print(f"Order book update: {update}")

async def sync_account(address):
    client = lighter.ApiClient()
    ws = lighter.WebSocketClient(client)
    
    # Subscribe to account updates
    await ws.subscribe_account(address)
    
    async for update in ws.stream_account():
        print(f"Account update: {update}")
```

### Available Subscriptions
- Order book updates
- Account updates (positions, orders, balances)
- Trade executions
- Market data

## Market Data Endpoints

### Get Order Book
```python
async def get_orderbook(market):
    client = lighter.ApiClient()
    order_api = lighter.OrderApi(client)
    
    orderbook = await order_api.get_order_books(market=market)
    return orderbook
```

### Get Recent Trades
```python
async def get_recent_trades(market):
    client = lighter.ApiClient()
    # Endpoint available through API
    trades = await client.get("/recentTrades", params={"market": market})
    return trades
```

### Get Candlestick Data
```python
async def get_candles(market, interval):
    client = lighter.ApiClient()
    candlestick_api = lighter.CandlestickApi(client)
    
    candles = await candlestick_api.get_candlesticks(
        market=market,
        interval=interval
    )
    return candles
```

### Get Funding Rates
```python
async def get_funding_rates(market):
    client = lighter.ApiClient()
    funding_api = lighter.FundingApi(client)
    
    funding = await funding_api.get_funding_rates(market=market)
    return funding
```

## API Endpoints Reference

### Account Endpoints
- `GET /account` - Get account details
- `GET /accountLimits` - Get account trading limits
- `GET /accountMetadata` - Get account metadata
- `GET /accountActiveOrders` - Get active orders
- `GET /accountInactiveOrders` - Get inactive orders
- `GET /accountTxs` - Get account transactions

### Order Endpoints
- `GET /orderBooks` - Get order books
- `GET /order/{id}` - Get specific order
- `POST /order` - Create new order
- `DELETE /order/{id}` - Cancel order

### Market Data Endpoints
- `GET /recentTrades` - Get recent trades
- `GET /candlestick` - Get candlestick data
- `GET /funding` - Get funding rates
- `GET /status` - Get system status

### Transaction Endpoints
- `GET /txs` - Get all transactions
- `GET /tx/{id}` - Get specific transaction

### Bridge Endpoints
- `GET /bridge` - Bridge information

## Error Handling

### Common Error Responses
```python
{
    "error": "ERROR_CODE",
    "message": "Error description",
    "details": {}
}
```

### Error Handling Pattern
```python
import lighter
import asyncio

async def safe_place_order():
    try:
        client = lighter.ApiClient()
        order_api = lighter.OrderApi(client)
        
        order = await order_api.create_order(...)
        return {"success": True, "order": order}
    except lighter.ApiException as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {e}"}
```

## Rate Limits
- Not explicitly documented in the available sources
- Recommended to implement client-side rate limiting
- Use exponential backoff for retries

## Order Types

### Supported Order Types
- Limit orders
- Market orders (if supported by the exchange)
- Stop orders (to be confirmed)

### Order Parameters
- market: Trading pair (e.g., "BTC-USDT")
- side: "buy" or "sell"
- type: "limit" or "market"
- size: Order size
- price: Limit price (for limit orders)
- timeInForce: Order time in force (GTC, IOC, etc.)

## Complete Trading Example

```python
import lighter
import asyncio
import json

class LighterTrader:
    def __init__(self, config):
        self.client = lighter.ApiClient()
        self.account_api = lighter.AccountApi(self.client)
        self.order_api = lighter.OrderApi(self.client)
        self.config = config
    
    async def get_account_info(self):
        account = await self.account_api.get_account(
            by="address", 
            value=self.config["address"]
        )
        return account
    
    async def place_limit_order(self, market, side, size, price):
        order = await self.order_api.create_order(
            market=market,
            side=side,
            type="limit",
            size=size,
            price=price
        )
        return order
    
    async def cancel_all_orders(self):
        active_orders = await self.account_api.get_account_active_orders(
            address=self.config["address"]
        )
        
        results = []
        for order in active_orders:
            result = await self.order_api.cancel_order(order_id=order.id)
            results.append(result)
        
        return results
    
    async def get_positions(self):
        account = await self.get_account_info()
        return account.positions
    
    async def monitor_orderbook(self, market):
        orderbook = await self.order_api.get_order_books(market=market)
        return {
            "best_bid": orderbook.bids[0] if orderbook.bids else None,
            "best_ask": orderbook.asks[0] if orderbook.asks else None,
            "spread": (orderbook.asks[0].price - orderbook.bids[0].price) 
                      if orderbook.bids and orderbook.asks else None
        }

async def main():
    config = {
        "address": "0x...",
        "api_key": "..."  # If required
    }
    
    trader = LighterTrader(config)
    
    # Get account info
    account = await trader.get_account_info()
    print(f"Account: {account}")
    
    # Monitor orderbook
    orderbook_info = await trader.monitor_orderbook("BTC-USDT")
    print(f"Orderbook: {orderbook_info}")
    
    # Place an order
    order = await trader.place_limit_order(
        market="BTC-USDT",
        side="buy",
        size=0.001,
        price=50000
    )
    print(f"Order placed: {order}")
    
    # Get positions
    positions = await trader.get_positions()
    print(f"Positions: {positions}")
    
    # Cancel all orders
    cancel_results = await trader.cancel_all_orders()
    print(f"Orders cancelled: {cancel_results}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Testing
- Use testnet endpoints if available
- Implement comprehensive error handling
- Test with small order sizes first
- Monitor rate limits and adjust accordingly

## Implementation Notes for Our Backend

### Priority Features
1. Implement async operations throughout
2. Use WebSocket for real-time updates
3. Handle zkSync-specific requirements
4. Implement proper error handling for network issues

### Architecture Considerations
1. Use asyncio for all Lighter operations
2. Implement connection pooling for efficiency
3. Cache order book data with short TTL
4. Queue orders during high load

### Security Considerations
1. Secure API key storage
2. Validate all input parameters
3. Implement request signing if required
4. Monitor for unusual activity

### Performance Optimization
1. Batch API requests where possible
2. Use WebSocket for real-time data instead of polling
3. Implement local order book maintenance
4. Cache account data with appropriate TTL

## Additional Resources
- API Documentation: https://apibetadocs.lighter.xyz/
- GitHub Repository: https://github.com/elliottech/lighter-python
- zkSync Documentation: For understanding the underlying blockchain