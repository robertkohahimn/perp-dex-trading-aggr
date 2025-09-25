# Vest Markets API Documentation

## Overview
Vest Markets is a perpetual DEX supporting crypto, equities, and indices trading with cross-chain capabilities.

## API Endpoints
- **Production**: https://server-prod.hz.vestmarkets.com/v2
- **Development**: https://server-dev.hz.vestmarkets.com/v2
- **WebSocket Production**: wss://ws-prod.hz.vestmarkets.com/ws-api?version=1.0
- **WebSocket Development**: wss://ws-dev.hz.vestmarkets.com/ws-api?version=1.0
- **API Documentation**: https://docs.vestmarkets.com/vest-api

## Official SDK
- **Python SDK**: Not available (must implement REST client)
- **Authentication**: Ethereum-style signing with typed data

## Authentication

### Setup Process
1. Generate signing key and address (Ethereum wallet)
2. Register with the exchange to get API key
3. Sign requests using typed data structure

### Registration
```python
async def register_account(base_url: str, address: str, signature: str) -> Dict:
    """Register account and get API key"""
    endpoint = f"{base_url}/register"
    payload = {
        "address": address,
        "signature": signature,
        "timestamp": int(time.time() * 1000)
    }
    response = await httpx.post(endpoint, json=payload)
    return response.json()  # Returns API key
```

### Request Signing
```python
from eth_account import Account
from eth_account.messages import encode_typed_data
import time
import json

def sign_request(private_key: str, method: str, path: str, body: Dict = None) -> Dict:
    """Sign request using Ethereum-style typed data"""
    timestamp = int(time.time() * 1000)
    
    # Construct typed data
    typed_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"}
            ],
            "Message": [
                {"name": "method", "type": "string"},
                {"name": "path", "type": "string"},
                {"name": "body", "type": "string"},
                {"name": "timestamp", "type": "uint256"}
            ]
        },
        "domain": {
            "name": "Vest Markets",
            "version": "1.0",
            "chainId": 1  # Ethereum mainnet
        },
        "primaryType": "Message",
        "message": {
            "method": method,
            "path": path,
            "body": json.dumps(body) if body else "",
            "timestamp": timestamp
        }
    }
    
    # Sign the typed data
    account = Account.from_key(private_key)
    encoded = encode_typed_data(typed_data)
    signature = account.sign_message(encoded).signature.hex()
    
    return {
        "X-VEST-ADDRESS": account.address,
        "X-VEST-SIGNATURE": signature,
        "X-VEST-TIMESTAMP": str(timestamp)
    }
```

## REST Client Implementation

```python
import httpx
import asyncio
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
from enum import Enum

class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"

class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"

class TimeInForce(Enum):
    GTC = "GTC"  # Good Till Cancel
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill

@dataclass
class VestConfig:
    api_key: str
    private_key: str
    address: str
    base_url: str = "https://server-prod.hz.vestmarkets.com/v2"
    ws_url: str = "wss://ws-prod.hz.vestmarkets.com/ws-api?version=1.0"
    timeout: int = 30

class VestClient:
    def __init__(self, config: VestConfig):
        self.config = config
        self.client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout
        )
    
    async def _request(
        self, 
        method: str, 
        endpoint: str, 
        params: Dict = None, 
        authenticated: bool = False
    ) -> Dict:
        """Execute HTTP request"""
        headers = {"Content-Type": "application/json"}
        
        if authenticated:
            # Add authentication headers
            auth_headers = sign_request(
                self.config.private_key,
                method,
                endpoint,
                params
            )
            headers.update(auth_headers)
            headers["X-VEST-API-KEY"] = self.config.api_key
        
        try:
            if method == "GET":
                response = await self.client.get(endpoint, params=params, headers=headers)
            elif method == "POST":
                response = await self.client.post(endpoint, json=params, headers=headers)
            elif method == "DELETE":
                response = await self.client.delete(endpoint, json=params, headers=headers)
            elif method == "PUT":
                response = await self.client.put(endpoint, json=params, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            error_data = e.response.json() if e.response.content else {}
            raise Exception(f"Vest API error: {e.response.status_code} - {error_data}")
        except Exception as e:
            raise Exception(f"Request failed: {e}")
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
```

## Public API Methods

### Market Information

```python
class VestPublicAPI(VestClient):
    async def get_exchange_info(self) -> Dict:
        """Get exchange configuration and available markets"""
        return await self._request("GET", "/exchangeInfo")
    
    async def get_market_info(self, symbol: str) -> Dict:
        """Get specific market information"""
        info = await self.get_exchange_info()
        for market in info.get("symbols", []):
            if market["symbol"] == symbol:
                return market
        return None
    
    async def get_ticker(self, symbol: Optional[str] = None) -> Any:
        """Get latest ticker prices"""
        params = {"symbol": symbol} if symbol else {}
        return await self._request("GET", "/ticker/latest", params=params)
    
    async def get_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        """Get order book depth"""
        params = {
            "symbol": symbol,
            "limit": limit
        }
        return await self._request("GET", "/depth", params=params)
    
    async def get_trades(self, symbol: str, limit: int = 100) -> List[Dict]:
        """Get recent trades"""
        params = {
            "symbol": symbol,
            "limit": limit
        }
        return await self._request("GET", "/trades", params=params)
    
    async def get_klines(
        self,
        symbol: str,
        interval: str,  # 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500
    ) -> List[List]:
        """Get candlestick/kline data"""
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        
        return await self._request("GET", "/klines", params=params)
    
    async def get_funding_rate(self, symbol: str) -> Dict:
        """Get funding rate for perpetual contracts"""
        ticker = await self.get_ticker(symbol)
        return {
            "symbol": symbol,
            "fundingRate": ticker.get("fundingRate"),
            "nextFundingTime": ticker.get("nextFundingTime")
        }
```

## Private API Methods

### Account Management

```python
class VestPrivateAPI(VestClient):
    async def get_account_info(self) -> Dict:
        """Get account information including balances and positions"""
        return await self._request("GET", "/account", authenticated=True)
    
    async def get_balance(self) -> Dict:
        """Get account balance"""
        account = await self.get_account_info()
        return {
            "totalBalance": account.get("totalWalletBalance"),
            "availableBalance": account.get("availableBalance"),
            "marginBalance": account.get("totalMarginBalance"),
            "unrealizedPnl": account.get("totalUnrealizedProfit")
        }
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get current positions"""
        account = await self.get_account_info()
        positions = account.get("positions", [])
        
        if symbol:
            return [p for p in positions if p["symbol"] == symbol]
        return positions
    
    async def set_leverage(self, symbol: str, leverage: int) -> Dict:
        """Set leverage for a symbol"""
        params = {
            "symbol": symbol,
            "leverage": leverage
        }
        return await self._request("POST", "/account/leverage", params=params, authenticated=True)
```

### Order Management

```python
    async def place_order(
        self,
        symbol: str,
        side: str,  # BUY or SELL
        order_type: str,  # MARKET, LIMIT, STOP_LOSS, TAKE_PROFIT
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
        client_order_id: Optional[str] = None
    ) -> Dict:
        """Place a new order"""
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": str(quantity),  # Convert to string as per API requirement
            "timeInForce": time_in_force,
            "reduceOnly": reduce_only
        }
        
        if price:
            params["price"] = str(price)
        
        if stop_price:
            params["stopPrice"] = str(stop_price)
        
        if client_order_id:
            params["newClientOrderId"] = client_order_id
        
        return await self._request("POST", "/orders", params=params, authenticated=True)
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """Cancel an order"""
        params = {
            "symbol": symbol,
            "orderId": order_id
        }
        return await self._request("DELETE", "/orders", params=params, authenticated=True)
    
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> Dict:
        """Cancel all open orders"""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self._request("DELETE", "/orders/all", params=params, authenticated=True)
    
    async def get_order(self, symbol: str, order_id: str) -> Dict:
        """Get order details"""
        params = {
            "symbol": symbol,
            "orderId": order_id
        }
        return await self._request("GET", "/orders", params=params, authenticated=True)
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get all open orders"""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self._request("GET", "/orders/open", params=params, authenticated=True)
    
    async def get_order_history(
        self,
        symbol: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500
    ) -> List[Dict]:
        """Get order history"""
        params = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        
        return await self._request("GET", "/orders/history", params=params, authenticated=True)
```

### Transfer Operations

```python
    async def withdraw(
        self,
        asset: str,
        amount: float,
        network: str,
        address: str,
        memo: Optional[str] = None
    ) -> Dict:
        """Initiate withdrawal"""
        params = {
            "asset": asset,
            "amount": str(amount),
            "network": network,
            "address": address
        }
        if memo:
            params["memo"] = memo
        
        return await self._request("POST", "/transfer/withdraw", params=params, authenticated=True)
    
    async def get_deposit_address(self, asset: str, network: str) -> Dict:
        """Get deposit address"""
        params = {
            "asset": asset,
            "network": network
        }
        return await self._request("GET", "/transfer/deposit/address", params=params, authenticated=True)
    
    async def get_transfer_history(
        self,
        transfer_type: str,  # "DEPOSIT" or "WITHDRAW"
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[Dict]:
        """Get transfer history"""
        params = {"type": transfer_type}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        
        return await self._request("GET", "/transfer/history", params=params, authenticated=True)
```

### Liquidity Provider Operations

```python
    async def add_liquidity(
        self,
        pool: str,
        amount: float
    ) -> Dict:
        """Add liquidity to a pool"""
        params = {
            "pool": pool,
            "amount": str(amount)
        }
        return await self._request("POST", "/lp/add", params=params, authenticated=True)
    
    async def remove_liquidity(
        self,
        pool: str,
        shares: float
    ) -> Dict:
        """Remove liquidity from a pool"""
        params = {
            "pool": pool,
            "shares": str(shares)
        }
        return await self._request("POST", "/lp/remove", params=params, authenticated=True)
    
    async def get_lp_positions(self) -> List[Dict]:
        """Get liquidity provider positions"""
        return await self._request("GET", "/lp/positions", authenticated=True)
```

## WebSocket Implementation

```python
import websockets
import json
import asyncio
from typing import Callable, Dict, Optional

class VestWebSocket:
    def __init__(self, config: VestConfig):
        self.config = config
        self.ws = None
        self.listen_key = None
        self.callbacks = {}
        self.running = False
    
    async def connect(self):
        """Connect to WebSocket"""
        # Get listen key for authenticated streams
        self.listen_key = await self._get_listen_key()
        
        url = f"{self.config.ws_url}"
        if self.listen_key:
            url += f"&listenKey={self.listen_key}"
        
        self.ws = await websockets.connect(url)
        self.running = True
        asyncio.create_task(self._handle_messages())
        asyncio.create_task(self._keep_alive())
    
    async def disconnect(self):
        """Disconnect WebSocket"""
        self.running = False
        if self.ws:
            await self.ws.close()
    
    async def _get_listen_key(self) -> str:
        """Get listen key for authenticated WebSocket"""
        client = VestPrivateAPI(self.config)
        response = await client._request("POST", "/userDataStream", authenticated=True)
        await client.close()
        return response.get("listenKey")
    
    async def _keep_alive(self):
        """Keep listen key alive"""
        while self.running:
            await asyncio.sleep(1800)  # 30 minutes
            if self.listen_key:
                client = VestPrivateAPI(self.config)
                await client._request(
                    "PUT", 
                    "/userDataStream", 
                    params={"listenKey": self.listen_key},
                    authenticated=True
                )
                await client.close()
    
    async def _handle_messages(self):
        """Handle incoming WebSocket messages"""
        try:
            async for message in self.ws:
                data = json.loads(message)
                await self._process_message(data)
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed")
            if self.running:
                # Reconnect logic
                await asyncio.sleep(5)
                await self.connect()
    
    async def _process_message(self, data: Dict):
        """Process WebSocket message"""
        event_type = data.get("e")  # Event type
        
        if event_type in self.callbacks:
            callback = self.callbacks[event_type]
            await callback(data)
    
    async def subscribe(self, streams: List[str]):
        """Subscribe to public streams"""
        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": int(time.time())
        }
        await self.ws.send(json.dumps(subscribe_msg))
    
    async def unsubscribe(self, streams: List[str]):
        """Unsubscribe from streams"""
        unsubscribe_msg = {
            "method": "UNSUBSCRIBE",
            "params": streams,
            "id": int(time.time())
        }
        await self.ws.send(json.dumps(unsubscribe_msg))
    
    # Specific subscription methods
    async def subscribe_ticker(self, symbol: str, callback: Callable):
        """Subscribe to ticker updates"""
        stream = f"{symbol.lower()}@ticker"
        await self.subscribe([stream])
        self.callbacks["24hrTicker"] = callback
    
    async def subscribe_orderbook(self, symbol: str, callback: Callable):
        """Subscribe to order book updates"""
        stream = f"{symbol.lower()}@depth"
        await self.subscribe([stream])
        self.callbacks["depthUpdate"] = callback
    
    async def subscribe_trades(self, symbol: str, callback: Callable):
        """Subscribe to trade updates"""
        stream = f"{symbol.lower()}@trade"
        await self.subscribe([stream])
        self.callbacks["trade"] = callback
    
    async def subscribe_klines(self, symbol: str, interval: str, callback: Callable):
        """Subscribe to kline updates"""
        stream = f"{symbol.lower()}@kline_{interval}"
        await self.subscribe([stream])
        self.callbacks["kline"] = callback
    
    # Private stream callbacks (automatically subscribed with listen key)
    def set_account_callback(self, callback: Callable):
        """Set callback for account updates"""
        self.callbacks["ACCOUNT_UPDATE"] = callback
    
    def set_order_callback(self, callback: Callable):
        """Set callback for order updates"""
        self.callbacks["ORDER_TRADE_UPDATE"] = callback
    
    def set_position_callback(self, callback: Callable):
        """Set callback for position updates"""
        self.callbacks["POSITION_UPDATE"] = callback
```

## Complete Trading Client

```python
class VestTradingClient:
    def __init__(self, config: VestConfig):
        self.config = config
        self.public = VestPublicAPI(config)
        self.private = VestPrivateAPI(config)
        self.ws = VestWebSocket(config)
    
    async def initialize(self):
        """Initialize client connections"""
        # Connect WebSocket
        await self.ws.connect()
        
        # Get account info
        account = await self.private.get_account_info()
        print(f"Account initialized: Balance = {account.get('totalWalletBalance')} USDC")
        
        # Set up private stream callbacks
        self.ws.set_account_callback(self._on_account_update)
        self.ws.set_order_callback(self._on_order_update)
        self.ws.set_position_callback(self._on_position_update)
        
        return account
    
    async def _on_account_update(self, data: Dict):
        """Handle account updates"""
        print(f"Account update: {data}")
    
    async def _on_order_update(self, data: Dict):
        """Handle order updates"""
        print(f"Order update: {data}")
    
    async def _on_position_update(self, data: Dict):
        """Handle position updates"""
        print(f"Position update: {data}")
    
    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        post_only: bool = False
    ) -> Dict:
        """Place a limit order"""
        time_in_force = "GTC" if not post_only else "GTX"  # GTX for post-only
        
        return await self.private.place_order(
            symbol=symbol,
            side=side,
            order_type="LIMIT",
            quantity=quantity,
            price=price,
            time_in_force=time_in_force
        )
    
    async def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float
    ) -> Dict:
        """Place a market order"""
        return await self.private.place_order(
            symbol=symbol,
            side=side,
            order_type="MARKET",
            quantity=quantity
        )
    
    async def place_stop_loss(
        self,
        symbol: str,
        quantity: float,
        stop_price: float,
        limit_price: Optional[float] = None
    ) -> Dict:
        """Place a stop loss order"""
        # Determine side based on position
        positions = await self.private.get_positions(symbol)
        if not positions:
            raise Exception("No position to protect")
        
        position = positions[0]
        side = "SELL" if position["positionSide"] == "LONG" else "BUY"
        
        return await self.private.place_order(
            symbol=symbol,
            side=side,
            order_type="STOP_LOSS",
            quantity=quantity,
            stop_price=stop_price,
            price=limit_price,
            reduce_only=True
        )
    
    async def close_position(self, symbol: str) -> Dict:
        """Close position for a symbol"""
        positions = await self.private.get_positions(symbol)
        
        if not positions:
            return {"message": "No position to close"}
        
        position = positions[0]
        side = "SELL" if position["positionSide"] == "LONG" else "BUY"
        quantity = abs(float(position["positionAmt"]))
        
        return await self.private.place_order(
            symbol=symbol,
            side=side,
            order_type="MARKET",
            quantity=quantity,
            reduce_only=True
        )
    
    async def get_pnl(self, symbol: Optional[str] = None) -> Dict:
        """Get P&L for positions"""
        positions = await self.private.get_positions(symbol)
        
        total_pnl = 0
        position_pnl = {}
        
        for pos in positions:
            pnl = float(pos.get("unrealizedProfit", 0))
            total_pnl += pnl
            position_pnl[pos["symbol"]] = {
                "unrealized": pnl,
                "realized": float(pos.get("realizedProfit", 0)),
                "percentage": float(pos.get("percentage", 0))
            }
        
        return {
            "total_unrealized": total_pnl,
            "positions": position_pnl
        }
    
    async def monitor_market(self, symbol: str):
        """Monitor market with WebSocket"""
        # Subscribe to multiple streams
        await self.ws.subscribe_ticker(symbol, self._on_ticker)
        await self.ws.subscribe_orderbook(symbol, self._on_orderbook)
        await self.ws.subscribe_trades(symbol, self._on_trade)
    
    async def _on_ticker(self, data: Dict):
        """Handle ticker updates"""
        print(f"Ticker: {data['s']} - Price: {data['c']}, 24h Change: {data['P']}%")
    
    async def _on_orderbook(self, data: Dict):
        """Handle orderbook updates"""
        print(f"Orderbook update for {data['s']}")
    
    async def _on_trade(self, data: Dict):
        """Handle trade updates"""
        print(f"Trade: {data['s']} - Price: {data['p']}, Qty: {data['q']}")
    
    async def cleanup(self):
        """Clean up connections"""
        await self.ws.disconnect()
        await self.public.close()
        await self.private.close()
```

## Usage Example

```python
import asyncio
from eth_account import Account

async def main():
    # Generate or load Ethereum account for signing
    private_key = "0x..."  # Your Ethereum private key
    account = Account.from_key(private_key)
    
    # Register with Vest to get API key (one-time setup)
    # api_key = await register_with_vest(account.address, private_key)
    
    config = VestConfig(
        api_key="your-api-key",
        private_key=private_key,
        address=account.address,
        base_url="https://server-dev.hz.vestmarkets.com/v2"  # Use dev for testing
    )
    
    client = VestTradingClient(config)
    
    try:
        # Initialize
        await client.initialize()
        
        # Get exchange info
        exchange_info = await client.public.get_exchange_info()
        print(f"Available markets: {len(exchange_info['symbols'])}")
        
        # Get ticker
        ticker = await client.public.get_ticker("BTC-PERP")
        print(f"BTC-PERP Price: {ticker['lastPrice']}")
        
        # Place limit order
        order = await client.place_limit_order(
            symbol="BTC-PERP",
            side="BUY",
            quantity=0.001,
            price=50000
        )
        print(f"Order placed: {order}")
        
        # Monitor market
        await client.monitor_market("BTC-PERP")
        
        # Get positions
        positions = await client.private.get_positions()
        print(f"Current positions: {positions}")
        
        # Get P&L
        pnl = await client.get_pnl()
        print(f"Total Unrealized P&L: {pnl['total_unrealized']} USDC")
        
        # Wait for updates
        await asyncio.sleep(60)
        
        # Close all positions
        for position in positions:
            await client.close_position(position["symbol"])
        
        # Cancel all orders
        await client.private.cancel_all_orders()
        
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
```

## Trading Strategies

### Grid Trading Example
```python
async def grid_trading_strategy(
    client: VestTradingClient,
    symbol: str,
    grid_levels: int = 10,
    grid_spacing: float = 0.01,  # 1% spacing
    order_size: float = 0.001
):
    """Simple grid trading strategy"""
    # Get current price
    ticker = await client.public.get_ticker(symbol)
    current_price = float(ticker["lastPrice"])
    
    # Place buy orders below current price
    for i in range(1, grid_levels // 2 + 1):
        buy_price = current_price * (1 - grid_spacing * i)
        await client.place_limit_order(
            symbol=symbol,
            side="BUY",
            quantity=order_size,
            price=buy_price
        )
        print(f"Buy order placed at {buy_price}")
    
    # Place sell orders above current price
    for i in range(1, grid_levels // 2 + 1):
        sell_price = current_price * (1 + grid_spacing * i)
        await client.place_limit_order(
            symbol=symbol,
            side="SELL",
            quantity=order_size,
            price=sell_price
        )
        print(f"Sell order placed at {sell_price}")
```

## Error Handling

```python
class VestException(Exception):
    """Base exception for Vest errors"""
    pass

class VestAPIException(VestException):
    """API request exceptions"""
    pass

class VestAuthException(VestException):
    """Authentication exceptions"""
    pass

# Enhanced error handling
async def safe_order_placement(client: VestTradingClient, **kwargs):
    """Safe order placement with retry logic"""
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            return await client.private.place_order(**kwargs)
        except VestAPIException as e:
            if "INSUFFICIENT_BALANCE" in str(e):
                raise  # Don't retry on insufficient balance
            elif "RATE_LIMIT" in str(e):
                await asyncio.sleep(retry_delay * (2 ** attempt))
            else:
                raise
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(retry_delay)
```

## Important Considerations

### Monetary Values
- All monetary values are in USDC
- Decimal values must be sent as strings to preserve precision
- Timestamps are in milliseconds

### Network Types
Vest supports multiple networks for deposits/withdrawals:
- Ethereum
- Polygon
- Arbitrum
- Optimism
- BSC
- Avalanche

### Order Types
- **MARKET**: Immediate execution at best available price
- **LIMIT**: Execute at specified price or better
- **STOP_LOSS**: Trigger market/limit order when stop price is reached
- **TAKE_PROFIT**: Close position at profit target
- **REDUCE_ONLY**: Only reduce existing position

### Margin and Leverage
- Isolated margin mode available
- Cross margin mode available
- Leverage adjustable per market
- Automatic liquidation when margin ratio exceeds threshold

## Implementation Notes for Our Backend

### Priority Features
1. Implement Ethereum-style signing for authentication
2. Handle all values as strings for precision
3. Support multiple asset types (crypto, equities, indices)
4. Implement WebSocket for real-time updates

### Architecture Considerations
1. Store private keys securely (use HSM/KMS)
2. Implement proper typed data signing
3. Handle multiple network types for transfers
4. Manage listen key lifecycle for WebSocket

### Security Considerations
1. Never log private keys or signatures
2. Validate all signatures before sending
3. Use secure key storage solutions
4. Implement request replay protection

### Performance Optimization
1. Reuse HTTP client connections
2. Batch operations where possible
3. Cache exchange info and market data
4. Maintain single WebSocket per account

## Additional Resources

- **API Documentation**: https://docs.vestmarkets.com/vest-api
- **Exchange Interface**: https://vestmarkets.com/
- **Support**: Contact through official website

## Notes

- Vest supports trading of crypto perpetuals, equity perpetuals, and index perpetuals
- Cross-chain transfers supported for multiple networks
- All values in USDC for simplicity
- Comprehensive margin and leverage management
- Real-time P&L tracking available