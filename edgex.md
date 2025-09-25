# EdgeX API Documentation

## Overview
EdgeX is a perpetual DEX with REST and WebSocket APIs. Currently in beta with active development.

## API Endpoints
- **HTTP Base URL**: https://pro.edgex.exchange
- **WebSocket URL**: wss://quote.edgex.exchange
- **API Documentation**: https://edgex-1.gitbook.io/edgeX-documentation/api

## Official SDK
- **Python SDK**: Not available (must implement REST client)
- **Status**: Beta version, actively under development

## Authentication

### Method
Third-party API authentication requires two request headers (differs from web authentication):

```python
headers = {
    "X-API-KEY": "your-api-key",
    "X-API-SECRET": "your-api-secret"  # Or signature depending on implementation
}
```

Note: Exact authentication headers to be confirmed from latest documentation or Discord support.

## REST Client Implementation

Since there's no official SDK, we'll implement a REST client:

```python
import httpx
import hmac
import hashlib
import time
import json
from typing import Dict, Optional, List, Any
from dataclasses import dataclass

@dataclass
class EdgeXConfig:
    api_key: str
    api_secret: str
    base_url: str = "https://pro.edgex.exchange"
    ws_url: str = "wss://quote.edgex.exchange"
    timeout: int = 30

class EdgeXClient:
    def __init__(self, config: EdgeXConfig):
        self.config = config
        self.client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout
        )
    
    async def _sign_request(self, method: str, path: str, params: Dict = None) -> Dict:
        """Generate signature for authenticated requests"""
        timestamp = str(int(time.time() * 1000))
        
        # Construct message to sign (adjust based on actual requirements)
        if params:
            query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
            message = f"{timestamp}{method}{path}?{query_string}"
        else:
            message = f"{timestamp}{method}{path}"
        
        # Generate signature
        signature = hmac.new(
            self.config.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return {
            "X-API-KEY": self.config.api_key,
            "X-TIMESTAMP": timestamp,
            "X-SIGNATURE": signature
        }
    
    async def _request(
        self, 
        method: str, 
        endpoint: str, 
        params: Dict = None, 
        authenticated: bool = False
    ) -> Dict:
        """Execute HTTP request"""
        headers = {}
        
        if authenticated:
            headers.update(await self._sign_request(method, endpoint, params))
        
        try:
            if method == "GET":
                response = await self.client.get(endpoint, params=params, headers=headers)
            elif method == "POST":
                response = await self.client.post(endpoint, json=params, headers=headers)
            elif method == "DELETE":
                response = await self.client.delete(endpoint, params=params, headers=headers)
            elif method == "PUT":
                response = await self.client.put(endpoint, json=params, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            error_data = e.response.json() if e.response.content else {}
            raise Exception(f"EdgeX API error: {e.response.status_code} - {error_data}")
        except Exception as e:
            raise Exception(f"Request failed: {e}")
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
```

## API Categories

### 1. Public APIs

#### Metadata API
Get exchange and market information:

```python
class EdgeXPublicAPI(EdgeXClient):
    async def get_markets(self) -> List[Dict]:
        """Get all available markets"""
        return await self._request("GET", "/api/v1/markets")
    
    async def get_market_info(self, symbol: str) -> Dict:
        """Get specific market information"""
        return await self._request("GET", f"/api/v1/markets/{symbol}")
    
    async def get_exchange_info(self) -> Dict:
        """Get exchange configuration"""
        return await self._request("GET", "/api/v1/exchange/info")
```

#### Quote API
Market data and order book:

```python
    async def get_orderbook(self, symbol: str, depth: int = 20) -> Dict:
        """Get order book for a symbol"""
        params = {"symbol": symbol, "depth": depth}
        return await self._request("GET", "/api/v1/orderbook", params=params)
    
    async def get_ticker(self, symbol: str) -> Dict:
        """Get 24h ticker statistics"""
        params = {"symbol": symbol}
        return await self._request("GET", "/api/v1/ticker", params=params)
    
    async def get_trades(self, symbol: str, limit: int = 100) -> List[Dict]:
        """Get recent trades"""
        params = {"symbol": symbol, "limit": limit}
        return await self._request("GET", "/api/v1/trades", params=params)
    
    async def get_klines(
        self, 
        symbol: str, 
        interval: str, 
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500
    ) -> List[List]:
        """Get candlestick data"""
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        return await self._request("GET", "/api/v1/klines", params=params)
```

#### Funding API
Funding rate information:

```python
    async def get_funding_rate(self, symbol: str) -> Dict:
        """Get current funding rate"""
        params = {"symbol": symbol}
        return await self._request("GET", "/api/v1/funding/rate", params=params)
    
    async def get_funding_history(
        self, 
        symbol: str, 
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[Dict]:
        """Get funding rate history"""
        params = {"symbol": symbol}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        return await self._request("GET", "/api/v1/funding/history", params=params)
```

### 2. Private APIs

#### Account API
Account management and information:

```python
class EdgeXPrivateAPI(EdgeXClient):
    async def get_account_info(self) -> Dict:
        """Get account information including balances"""
        return await self._request("GET", "/api/v1/account", authenticated=True)
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get current positions"""
        params = {"symbol": symbol} if symbol else {}
        return await self._request("GET", "/api/v1/positions", params=params, authenticated=True)
    
    async def get_balance(self) -> Dict:
        """Get account balance"""
        return await self._request("GET", "/api/v1/account/balance", authenticated=True)
    
    async def set_leverage(self, symbol: str, leverage: int) -> Dict:
        """Set leverage for a symbol"""
        params = {
            "symbol": symbol,
            "leverage": leverage
        }
        return await self._request("POST", "/api/v1/account/leverage", params=params, authenticated=True)
```

#### Order API
Order management operations:

```python
    async def place_order(
        self,
        symbol: str,
        side: str,  # BUY or SELL
        order_type: str,  # LIMIT, MARKET, etc.
        quantity: float,
        price: Optional[float] = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
        post_only: bool = False,
        client_order_id: Optional[str] = None
    ) -> Dict:
        """Place a new order"""
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
            "timeInForce": time_in_force,
            "reduceOnly": reduce_only,
            "postOnly": post_only
        }
        
        if price:
            params["price"] = price
        if client_order_id:
            params["clientOrderId"] = client_order_id
        
        return await self._request("POST", "/api/v1/orders", params=params, authenticated=True)
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """Cancel an order"""
        params = {
            "symbol": symbol,
            "orderId": order_id
        }
        return await self._request("DELETE", "/api/v1/orders", params=params, authenticated=True)
    
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> Dict:
        """Cancel all open orders"""
        params = {"symbol": symbol} if symbol else {}
        return await self._request("DELETE", "/api/v1/orders/all", params=params, authenticated=True)
    
    async def get_order(self, symbol: str, order_id: str) -> Dict:
        """Get order details"""
        params = {
            "symbol": symbol,
            "orderId": order_id
        }
        return await self._request("GET", "/api/v1/orders", params=params, authenticated=True)
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get all open orders"""
        params = {"symbol": symbol} if symbol else {}
        return await self._request("GET", "/api/v1/orders/open", params=params, authenticated=True)
    
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
        return await self._request("GET", "/api/v1/orders/history", params=params, authenticated=True)
```

#### Transfer API
Asset transfers:

```python
    async def transfer(
        self,
        asset: str,
        amount: float,
        from_account: str,
        to_account: str
    ) -> Dict:
        """Transfer assets between accounts"""
        params = {
            "asset": asset,
            "amount": amount,
            "from": from_account,
            "to": to_account
        }
        return await self._request("POST", "/api/v1/transfer", params=params, authenticated=True)
    
    async def get_transfer_history(
        self,
        asset: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[Dict]:
        """Get transfer history"""
        params = {}
        if asset:
            params["asset"] = asset
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        return await self._request("GET", "/api/v1/transfer/history", params=params, authenticated=True)
```

#### Asset API
Asset management:

```python
    async def get_assets(self) -> List[Dict]:
        """Get all supported assets"""
        return await self._request("GET", "/api/v1/assets", authenticated=True)
    
    async def get_deposit_address(self, asset: str) -> Dict:
        """Get deposit address for an asset"""
        params = {"asset": asset}
        return await self._request("GET", "/api/v1/assets/deposit/address", params=params, authenticated=True)
    
    async def withdraw(
        self,
        asset: str,
        amount: float,
        address: str,
        tag: Optional[str] = None
    ) -> Dict:
        """Initiate withdrawal"""
        params = {
            "asset": asset,
            "amount": amount,
            "address": address
        }
        if tag:
            params["tag"] = tag
        return await self._request("POST", "/api/v1/assets/withdraw", params=params, authenticated=True)
```

## WebSocket Implementation

```python
import websockets
import json
import asyncio
from typing import Callable, Optional

class EdgeXWebSocket:
    def __init__(self, config: EdgeXConfig):
        self.config = config
        self.ws = None
        self.subscriptions = {}
        self.callbacks = {}
    
    async def connect(self):
        """Connect to WebSocket"""
        self.ws = await websockets.connect(self.config.ws_url)
        asyncio.create_task(self._handle_messages())
    
    async def disconnect(self):
        """Disconnect WebSocket"""
        if self.ws:
            await self.ws.close()
    
    async def _handle_messages(self):
        """Handle incoming WebSocket messages"""
        try:
            async for message in self.ws:
                data = json.loads(message)
                await self._process_message(data)
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed")
            # Implement reconnection logic here
    
    async def _process_message(self, data: Dict):
        """Process WebSocket message"""
        # Route message to appropriate callback
        channel = data.get("channel")
        if channel and channel in self.callbacks:
            await self.callbacks[channel](data)
    
    async def subscribe(self, channel: str, params: Dict, callback: Callable):
        """Subscribe to a channel"""
        self.callbacks[channel] = callback
        
        subscribe_msg = {
            "op": "subscribe",
            "channel": channel,
            **params
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
        self.subscriptions[channel] = params
    
    async def unsubscribe(self, channel: str):
        """Unsubscribe from a channel"""
        if channel in self.subscriptions:
            unsubscribe_msg = {
                "op": "unsubscribe",
                "channel": channel
            }
            await self.ws.send(json.dumps(unsubscribe_msg))
            del self.subscriptions[channel]
            del self.callbacks[channel]
    
    # Specific subscription methods
    async def subscribe_orderbook(self, symbol: str, callback: Callable):
        """Subscribe to order book updates"""
        await self.subscribe(
            "orderbook",
            {"symbol": symbol},
            callback
        )
    
    async def subscribe_trades(self, symbol: str, callback: Callable):
        """Subscribe to trade updates"""
        await self.subscribe(
            "trades",
            {"symbol": symbol},
            callback
        )
    
    async def subscribe_ticker(self, symbol: str, callback: Callable):
        """Subscribe to ticker updates"""
        await self.subscribe(
            "ticker",
            {"symbol": symbol},
            callback
        )
    
    async def subscribe_account(self, callback: Callable):
        """Subscribe to account updates (requires authentication)"""
        # Send authentication message first
        auth_msg = {
            "op": "auth",
            "apiKey": self.config.api_key,
            # Add signature/timestamp as required
        }
        await self.ws.send(json.dumps(auth_msg))
        
        # Then subscribe to account channel
        await self.subscribe(
            "account",
            {},
            callback
        )
    
    async def subscribe_orders(self, callback: Callable):
        """Subscribe to order updates"""
        await self.subscribe(
            "orders",
            {},
            callback
        )
    
    async def subscribe_positions(self, callback: Callable):
        """Subscribe to position updates"""
        await self.subscribe(
            "positions",
            {},
            callback
        )
```

## Complete Trading Client

```python
class EdgeXTradingClient:
    def __init__(self, config: EdgeXConfig):
        self.config = config
        self.public = EdgeXPublicAPI(config)
        self.private = EdgeXPrivateAPI(config)
        self.ws = EdgeXWebSocket(config)
    
    async def initialize(self):
        """Initialize client connections"""
        await self.ws.connect()
        
        # Get account info
        account = await self.private.get_account_info()
        print(f"Account initialized: {account}")
        
        return account
    
    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float
    ) -> Dict:
        """Place a limit order"""
        return await self.private.place_order(
            symbol=symbol,
            side=side,
            order_type="LIMIT",
            quantity=quantity,
            price=price,
            time_in_force="GTC"
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
    
    async def get_best_prices(self, symbol: str) -> Dict:
        """Get best bid/ask prices"""
        orderbook = await self.public.get_orderbook(symbol, depth=1)
        return {
            "best_bid": orderbook["bids"][0] if orderbook.get("bids") else None,
            "best_ask": orderbook["asks"][0] if orderbook.get("asks") else None
        }
    
    async def monitor_positions(self):
        """Monitor positions with WebSocket"""
        def on_position_update(data):
            print(f"Position update: {data}")
        
        await self.ws.subscribe_positions(on_position_update)
    
    async def close_position(self, symbol: str) -> Dict:
        """Close position for a symbol"""
        # Get current position
        positions = await self.private.get_positions(symbol)
        
        if not positions:
            return {"message": "No position to close"}
        
        position = positions[0]
        side = "SELL" if position["side"] == "LONG" else "BUY"
        
        # Place reduce-only market order
        return await self.private.place_order(
            symbol=symbol,
            side=side,
            order_type="MARKET",
            quantity=abs(position["quantity"]),
            reduce_only=True
        )
    
    async def cleanup(self):
        """Clean up connections"""
        await self.ws.disconnect()
        await self.public.close()
        await self.private.close()
```

## Usage Example

```python
import asyncio

async def main():
    config = EdgeXConfig(
        api_key="your-api-key",
        api_secret="your-api-secret"
    )
    
    client = EdgeXTradingClient(config)
    
    try:
        # Initialize
        await client.initialize()
        
        # Get market info
        markets = await client.public.get_markets()
        print(f"Available markets: {markets}")
        
        # Get best prices
        prices = await client.get_best_prices("BTC-USDT")
        print(f"Best prices: {prices}")
        
        # Place limit order
        order = await client.place_limit_order(
            symbol="BTC-USDT",
            side="BUY",
            quantity=0.001,
            price=50000
        )
        print(f"Order placed: {order}")
        
        # Monitor positions
        await client.monitor_positions()
        
        # Get positions
        positions = await client.private.get_positions()
        print(f"Current positions: {positions}")
        
        # Cancel all orders
        await client.private.cancel_all_orders("BTC-USDT")
        
        # Wait for updates
        await asyncio.sleep(60)
        
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
```

## Error Handling

```python
class EdgeXException(Exception):
    """Base exception for EdgeX errors"""
    pass

class EdgeXAPIException(EdgeXException):
    """API request exceptions"""
    def __init__(self, status_code: int, message: str, details: Dict = None):
        self.status_code = status_code
        self.message = message
        self.details = details or {}
        super().__init__(f"[{status_code}] {message}")

class EdgeXAuthException(EdgeXException):
    """Authentication exceptions"""
    pass

class EdgeXRateLimitException(EdgeXException):
    """Rate limit exceptions"""
    pass

# Enhanced error handling in client
async def safe_request(self, *args, **kwargs):
    try:
        return await self._request(*args, **kwargs)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise EdgeXAuthException("Authentication failed")
        elif e.response.status_code == 429:
            raise EdgeXRateLimitException("Rate limit exceeded")
        else:
            raise EdgeXAPIException(
                e.response.status_code,
                str(e),
                e.response.json() if e.response.content else {}
            )
```

## Rate Limits
- Specific rate limits not documented in beta version
- Implement client-side rate limiting:

```python
from asyncio import Semaphore
from functools import wraps

class RateLimiter:
    def __init__(self, calls_per_minute: int = 60):
        self.semaphore = Semaphore(calls_per_minute)
        self.reset_time = 60  # seconds
    
    def limit(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with self.semaphore:
                result = await func(*args, **kwargs)
                asyncio.create_task(self._release_after_delay())
                return result
        return wrapper
    
    async def _release_after_delay(self):
        await asyncio.sleep(self.reset_time)
        self.semaphore.release()
```

## Testing Considerations

```python
# Mock client for testing
class MockEdgeXClient:
    async def place_order(self, **kwargs):
        return {
            "orderId": "test-order-123",
            "status": "NEW",
            **kwargs
        }
    
    async def get_positions(self, symbol=None):
        return [{
            "symbol": "BTC-USDT",
            "side": "LONG",
            "quantity": 0.01,
            "entryPrice": 50000,
            "markPrice": 51000,
            "pnl": 10
        }]
```

## Implementation Notes for Our Backend

### Priority Considerations
1. **Beta Status**: Implement comprehensive error handling and fallbacks
2. **No Official SDK**: Build robust REST client with proper authentication
3. **Discord Support**: Monitor Discord for API updates and issues
4. **Testing**: Extensive testing required due to beta status

### Architecture Recommendations
1. Implement comprehensive request/response logging
2. Build retry logic with exponential backoff
3. Create abstraction layer for easy updates
4. Monitor API changes actively

### Security Considerations
1. Secure API key and secret storage
2. Implement request signing correctly
3. Validate all responses
4. Monitor for unexpected behavior

### Performance Optimization
1. Connection pooling for HTTP requests
2. WebSocket connection management
3. Local caching where appropriate
4. Rate limit management

## Support and Resources

- **API Documentation**: https://edgex-1.gitbook.io/edgeX-documentation/api
- **Discord**: Primary support channel for beta issues
- **Status**: Beta version - expect changes and potential issues

## Important Notes

⚠️ **Beta Warning**: EdgeX API is in beta and actively under development. Expect:
- Potential breaking changes
- Documentation updates
- New features being added
- Possible instability

Recommendations:
- Implement robust error handling
- Monitor Discord for updates
- Test thoroughly in testnet first
- Maintain fallback mechanisms