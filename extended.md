# Extended API/SDK Documentation

## Overview
Extended is a hybrid perpetuals exchange built on Starknet, offering trustless, self-custodial trading with advanced features and up to 10 sub-accounts per wallet.

## API Endpoints
- **Mainnet**: https://api.starknet.extended.exchange/
- **Testnet**: https://api.starknet.sepolia.extended.exchange/
- **API Documentation**: https://api.docs.extended.exchange/

## Official SDK
- **Python SDK**: https://github.com/x10xchange/python_sdk
- **Package**: x10-python-trading-starknet

## Python SDK Installation
```bash
pip install x10-python-trading-starknet
```

Requirements:
- Python 3.10+
- Rust library for accelerated signing (included)

## Authentication

### Account Setup Process
1. Register at Extended (Testnet: https://testnet.extended.exchange)
2. Generate API key in API Management section
3. Obtain:
   - Vault number
   - Public key (Stark key)
   - Private key
   - API key

### Authentication Method
- **API Key**: Required in `X-Api-Key` header for all requests
- **Stark Signature**: Required for order management operations
- **Account Creation**: Via SDK or UI interface

### SDK Configuration
```python
from x10.perpetual.accounts import StarkPerpetualAccount
from x10.perpetual.configuration import TESTNET_CONFIG, MAINNET_CONFIG
from x10.perpetual.trading_client import PerpetualTradingClient

# Initialize Stark account
stark_account = StarkPerpetualAccount(
    vault=12345,  # Your vault number
    private_key="0x...",  # Your private key
    public_key="0x...",   # Your public key
    api_key="your-api-key"  # Your API key
)

# Create trading client
# For testnet
trading_client = PerpetualTradingClient.create(TESTNET_CONFIG, stark_account)

# For mainnet
trading_client = PerpetualTradingClient.create(MAINNET_CONFIG, stark_account)
```

## Core SDK Classes

### PerpetualTradingClient
Main client for all trading operations:
```python
from x10.perpetual.trading_client import PerpetualTradingClient

client = PerpetualTradingClient.create(config, stark_account)
```

### StarkPerpetualAccount
Account management and authentication:
```python
from x10.perpetual.accounts import StarkPerpetualAccount

account = StarkPerpetualAccount(
    vault=vault_number,
    private_key=private_key,
    public_key=public_key,
    api_key=api_key
)
```

## Main Trading Operations

### 1. Place Order

**Important Starknet Requirements:**
- Price parameter is MANDATORY for all orders (including market orders)
- Fee parameter is REQUIRED
- Expiration timestamp is MANDATORY

```python
# Limit order
order = await client.place_order(
    market="ETH-USD",
    side="BUY",  # or "SELL"
    size=0.1,
    price=3000.0,  # MANDATORY even for market orders
    order_type="LIMIT",
    time_in_force="GTT",  # Good-till-time
    expiration_timestamp=int(time.time()) + 86400,  # Required
    fee=0.001,  # Required fee parameter
    reduce_only=False,
    post_only=False
)

# Market order (simulated via limit order)
market_order = await client.place_order(
    market="ETH-USD",
    side="BUY",
    size=0.1,
    price=3100.0,  # Set higher than market for buy, lower for sell
    order_type="MARKET",
    time_in_force="IOC",  # Immediate-or-cancel
    expiration_timestamp=int(time.time()) + 60,
    fee=0.001
)

# Conditional order (stop-loss)
stop_order = await client.place_order(
    market="ETH-USD",
    side="SELL",
    size=0.1,
    price=2800.0,
    order_type="CONDITIONAL",
    trigger_price=2850.0,  # Trigger when price reaches this level
    time_in_force="GTT",
    expiration_timestamp=int(time.time()) + 86400,
    fee=0.001
)

# Take-profit/Stop-loss order
tpsl_order = await client.place_order(
    market="ETH-USD",
    side="BUY",
    size=0.1,
    price=3000.0,
    order_type="TPSL",
    take_profit_price=3200.0,
    stop_loss_price=2900.0,
    time_in_force="GTT",
    expiration_timestamp=int(time.time()) + 86400,
    fee=0.001
)
```

### 2. Cancel Order
```python
# Cancel single order
cancel_result = await client.cancel_order(
    order_id="0x123abc...",
    market="ETH-USD"
)

# Cancel all orders for a market
cancel_all = await client.cancel_all_orders(market="ETH-USD")

# Cancel all orders across all markets
cancel_all_markets = await client.cancel_all_orders()
```

### 3. Modify Order
```python
modified_order = await client.modify_order(
    order_id="0x123abc...",
    market="ETH-USD",
    new_size=0.2,  # Optional
    new_price=3100.0,  # Optional
    new_expiration=int(time.time()) + 172800  # Optional
)
```

### 4. Get Positions
```python
# Get all positions
positions = await client.get_positions()

# Get position for specific market
position = await client.get_position(market="ETH-USD")

# Position structure
{
    "market": "ETH-USD",
    "side": "LONG",
    "size": 0.5,
    "entry_price": 3000.0,
    "mark_price": 3050.0,
    "unrealized_pnl": 25.0,
    "realized_pnl": 10.0,
    "margin": 150.0,
    "leverage": 10
}
```

### 5. Get Account Balance
```python
# Get account info including balance
account_info = await client.get_account_info()

balance = account_info["balance"]
available_balance = account_info["available_balance"]
margin_used = account_info["margin_used"]
unrealized_pnl = account_info["unrealized_pnl"]
```

### 6. Get Open Orders
```python
# Get all open orders
open_orders = await client.get_open_orders()

# Get open orders for specific market
market_orders = await client.get_open_orders(market="ETH-USD")
```

### 7. Adjust Leverage
```python
# Set leverage for a specific market
leverage_result = await client.set_leverage(
    market="ETH-USD",
    leverage=20  # 1-100 depending on market
)
```

## WebSocket Support

### Public WebSocket Streams
```python
from x10.perpetual.websocket import WebSocketClient

ws_client = WebSocketClient(config)

# Subscribe to order book
await ws_client.subscribe_orderbook("ETH-USD", callback=on_orderbook_update)

# Subscribe to trades
await ws_client.subscribe_trades("ETH-USD", callback=on_trade)

# Subscribe to funding rates
await ws_client.subscribe_funding("ETH-USD", callback=on_funding_update)

# Callback functions
def on_orderbook_update(data):
    print(f"Order book update: {data}")

def on_trade(data):
    print(f"New trade: {data}")

def on_funding_update(data):
    print(f"Funding update: {data}")
```

### Private WebSocket Streams
```python
# Subscribe to account updates
await ws_client.subscribe_account(
    account=stark_account,
    callback=on_account_update
)

# Subscribe to order updates
await ws_client.subscribe_orders(
    account=stark_account,
    callback=on_order_update
)

# Subscribe to position updates
await ws_client.subscribe_positions(
    account=stark_account,
    callback=on_position_update
)

def on_account_update(data):
    print(f"Account update: {data}")

def on_order_update(data):
    print(f"Order update: {data}")

def on_position_update(data):
    print(f"Position update: {data}")
```

## Market Data

### Get Markets Info
```python
# Get all available markets
markets = await client.get_markets()

# Get specific market info
market_info = await client.get_market_info("ETH-USD")
```

### Get Order Book
```python
orderbook = await client.get_orderbook(
    market="ETH-USD",
    depth=20  # Number of levels
)

# Returns
{
    "bids": [[price, size], ...],
    "asks": [[price, size], ...],
    "timestamp": 1234567890
}
```

### Get Recent Trades
```python
trades = await client.get_recent_trades(
    market="ETH-USD",
    limit=100
)
```

### Get Funding Rate
```python
funding = await client.get_funding_rate("ETH-USD")

# Historical funding
funding_history = await client.get_funding_history(
    market="ETH-USD",
    start_time=start_timestamp,
    end_time=end_timestamp
)
```

## Order Types

### Supported Order Types
1. **LIMIT**: Standard limit order
2. **MARKET**: Simulated via limit orders with IOC
3. **CONDITIONAL**: Stop/trigger orders
4. **TPSL**: Take-profit/Stop-loss orders

### Time in Force Options
- **GTT** (Good-Till-Time): Order valid until expiration
- **IOC** (Immediate-Or-Cancel): Execute immediately or cancel
- **FOK** (Fill-Or-Kill): Execute completely or cancel

### Order Options
- **reduce_only**: Only reduce position size
- **post_only**: Only add liquidity (maker order)

## Rate Limits
- **API Rate Limit**: 1,000 requests per minute per IP
- **Order Rate Limit**: 300 orders per minute per account
- **WebSocket Connections**: 10 connections per IP

### Rate Limit Headers
```python
# Response headers
{
    "X-RateLimit-Limit": "1000",
    "X-RateLimit-Remaining": "950",
    "X-RateLimit-Reset": "1234567890"
}
```

## Error Handling

### Common Error Codes
```python
{
    "INSUFFICIENT_BALANCE": "Not enough margin",
    "INVALID_PRICE": "Price outside valid range",
    "INVALID_SIZE": "Size below minimum or above maximum",
    "RATE_LIMIT_EXCEEDED": "Too many requests",
    "INVALID_SIGNATURE": "Stark signature verification failed",
    "ORDER_NOT_FOUND": "Order ID doesn't exist",
    "MARKET_CLOSED": "Market is not open for trading"
}
```

### Error Handling Pattern
```python
from x10.perpetual.exceptions import (
    TradingException,
    AuthenticationException,
    RateLimitException
)

try:
    order = await client.place_order(...)
except AuthenticationException as e:
    print(f"Authentication failed: {e}")
except RateLimitException as e:
    print(f"Rate limit hit: {e}")
    await asyncio.sleep(60)  # Wait before retry
except TradingException as e:
    print(f"Trading error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Sub-Accounts

Extended supports up to 10 sub-accounts per wallet:

```python
# Create sub-account
sub_account = await client.create_sub_account(
    name="Arbitrage Account"
)

# Switch to sub-account
client.switch_account(sub_account_id=1)

# Get all sub-accounts
sub_accounts = await client.get_sub_accounts()

# Transfer between accounts
transfer = await client.transfer_between_accounts(
    from_account=0,  # Main account
    to_account=1,    # Sub-account
    amount=1000.0
)
```

## Complete Trading Example

```python
import asyncio
import time
from x10.perpetual.accounts import StarkPerpetualAccount
from x10.perpetual.configuration import MAINNET_CONFIG
from x10.perpetual.trading_client import PerpetualTradingClient
from x10.perpetual.exceptions import TradingException

class ExtendedTrader:
    def __init__(self, config):
        self.stark_account = StarkPerpetualAccount(
            vault=config["vault"],
            private_key=config["private_key"],
            public_key=config["public_key"],
            api_key=config["api_key"]
        )
        self.client = PerpetualTradingClient.create(
            MAINNET_CONFIG, 
            self.stark_account
        )
    
    async def initialize(self):
        """Set up initial configuration"""
        # Get account info
        self.account_info = await self.client.get_account_info()
        print(f"Account balance: {self.account_info['balance']}")
        
        # Set leverage for markets
        await self.client.set_leverage("ETH-USD", 10)
        await self.client.set_leverage("BTC-USD", 5)
    
    async def place_limit_order_with_sl_tp(self, market, side, size, price):
        """Place limit order with stop-loss and take-profit"""
        try:
            # Calculate SL/TP levels
            if side == "BUY":
                stop_loss = price * 0.98  # 2% stop loss
                take_profit = price * 1.03  # 3% take profit
            else:
                stop_loss = price * 1.02
                take_profit = price * 0.97
            
            # Place main order
            order = await self.client.place_order(
                market=market,
                side=side,
                size=size,
                price=price,
                order_type="LIMIT",
                time_in_force="GTT",
                expiration_timestamp=int(time.time()) + 86400,
                fee=0.001,
                post_only=True  # Ensure maker fee
            )
            
            # Place stop-loss
            sl_order = await self.client.place_order(
                market=market,
                side="SELL" if side == "BUY" else "BUY",
                size=size,
                price=stop_loss,
                order_type="CONDITIONAL",
                trigger_price=stop_loss,
                time_in_force="GTT",
                expiration_timestamp=int(time.time()) + 86400,
                fee=0.001,
                reduce_only=True
            )
            
            # Place take-profit
            tp_order = await self.client.place_order(
                market=market,
                side="SELL" if side == "BUY" else "BUY",
                size=size,
                price=take_profit,
                order_type="CONDITIONAL",
                trigger_price=take_profit,
                time_in_force="GTT",
                expiration_timestamp=int(time.time()) + 86400,
                fee=0.001,
                reduce_only=True
            )
            
            return {
                "main_order": order,
                "stop_loss": sl_order,
                "take_profit": tp_order
            }
            
        except TradingException as e:
            print(f"Order placement failed: {e}")
            return None
    
    async def monitor_positions(self):
        """Monitor and manage positions"""
        while True:
            try:
                positions = await self.client.get_positions()
                
                for position in positions:
                    market = position["market"]
                    unrealized_pnl = position["unrealized_pnl"]
                    margin_ratio = position["margin_ratio"]
                    
                    # Check if position needs attention
                    if margin_ratio > 0.8:  # 80% margin used
                        print(f"Warning: High margin usage for {market}")
                        # Consider reducing position or adding margin
                    
                    # Log position status
                    print(f"{market}: Size={position['size']}, "
                          f"PnL={unrealized_pnl:.2f}, "
                          f"Margin Ratio={margin_ratio:.2%}")
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                print(f"Position monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def execute_market_order(self, market, side, size):
        """Execute market order using IOC limit order"""
        try:
            # Get current market price
            orderbook = await self.client.get_orderbook(market, depth=1)
            
            if side == "BUY":
                # Use ask price + small buffer for buy
                price = orderbook["asks"][0][0] * 1.001
            else:
                # Use bid price - small buffer for sell
                price = orderbook["bids"][0][0] * 0.999
            
            order = await self.client.place_order(
                market=market,
                side=side,
                size=size,
                price=price,
                order_type="MARKET",
                time_in_force="IOC",
                expiration_timestamp=int(time.time()) + 60,
                fee=0.001
            )
            
            return order
            
        except TradingException as e:
            print(f"Market order failed: {e}")
            return None

async def main():
    config = {
        "vault": 12345,
        "private_key": "0x...",
        "public_key": "0x...",
        "api_key": "your-api-key"
    }
    
    trader = ExtendedTrader(config)
    
    # Initialize
    await trader.initialize()
    
    # Place a limit order with SL/TP
    orders = await trader.place_limit_order_with_sl_tp(
        market="ETH-USD",
        side="BUY",
        size=0.1,
        price=3000.0
    )
    
    if orders:
        print(f"Orders placed: {orders}")
    
    # Execute market order
    market_order = await trader.execute_market_order(
        market="BTC-USD",
        side="BUY",
        size=0.01
    )
    
    if market_order:
        print(f"Market order executed: {market_order}")
    
    # Start position monitoring
    await trader.monitor_positions()

if __name__ == "__main__":
    asyncio.run(main())
```

## Starknet-Specific Considerations

### Mandatory Parameters
1. **Price**: Required for ALL orders, including market orders
2. **Fee**: Must be specified for every order
3. **Expiration**: Timestamp required for all orders

### Stark Key Generation
```python
from x10.perpetual.accounts import generate_stark_key_from_eth_account

# Generate Stark key from Ethereum account
stark_keys = generate_stark_key_from_eth_account(
    eth_address="0x...",
    eth_private_key="0x..."
)
```

### Transaction Finality
- Transactions are settled on Starknet
- Finality time varies based on network conditions
- Monitor transaction status for confirmation

## Testing

### Testnet Configuration
```python
from x10.perpetual.configuration import TESTNET_CONFIG

# Use testnet configuration
client = PerpetualTradingClient.create(TESTNET_CONFIG, stark_account)
```

### Testnet Faucet
- Register at https://testnet.extended.exchange
- Request testnet funds from faucet

## Implementation Notes for Our Backend

### Priority Features
1. Handle mandatory Starknet parameters (price, fee, expiration)
2. Implement sub-account management
3. Use WebSocket for real-time updates
4. Handle Stark signature requirements

### Architecture Considerations
1. Store Stark keys securely
2. Implement proper expiration timestamp management
3. Cache order book for market order simulation
4. Handle Starknet transaction finality

### Security Considerations
1. Secure Stark key storage and management
2. Validate all mandatory parameters before submission
3. Implement signature verification
4. Monitor for Starknet-specific errors

### Performance Optimization
1. Batch order submissions where possible
2. Use WebSocket for all real-time data
3. Implement local order book maintenance
4. Cache market info to reduce API calls

## Additional Resources
- API Documentation: https://api.docs.extended.exchange/
- GitHub Repository: https://github.com/x10xchange/python_sdk
- Starknet Documentation: https://docs.starknet.io/
- Extended Exchange UI: https://extended.exchange/