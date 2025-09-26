"""
Hyperliquid DEX connector implementation.
"""
import asyncio
import json
import time
from typing import Dict, List, Optional, Any, AsyncIterator
from decimal import Decimal
from datetime import datetime, timezone
import httpx
import websockets
from eth_account import Account as EthAccount
from eth_account.messages import encode_typed_data
import logging

from connectors.base import (
    BaseConnector,
    ConnectorConfig,
    OrderRequest, 
    OrderResponse, 
    Order,
    Position, 
    AccountInfo, 
    MarketData,
    OrderType,
    OrderSide,
    OrderStatus,
    TimeInForce
)
from app.core.exceptions import (
    AuthenticationError,
    ConnectorError,
    OrderNotFoundError,
    InsufficientBalanceError,
    InvalidOrderError,
    RateLimitError,
)

logger = logging.getLogger(__name__)


class HyperliquidConnector(BaseConnector):
    """
    Connector for Hyperliquid DEX.
    
    Hyperliquid uses EVM-style signing for authentication.
    """
    
    BASE_URL = "https://api.hyperliquid.xyz"
    TESTNET_URL = "https://api.hyperliquid-testnet.xyz"
    WS_URL = "wss://api.hyperliquid.xyz/ws"
    WS_TESTNET_URL = "wss://api.hyperliquid-testnet.xyz/ws"
    
    def __init__(self, use_testnet: bool = False, config: Optional[Any] = None):
        """Initialize Hyperliquid connector."""
        # Handle both dict and ConnectorConfig
        if config is None:
            from dataclasses import dataclass, field
            @dataclass
            class SimpleConfig:
                name: str = "hyperliquid"
                api_key: Optional[str] = None
                api_secret: Optional[str] = None
                testnet: bool = False
                rate_limit: Optional[int] = None
                metadata: Optional[Dict[str, Any]] = None
            config = SimpleConfig(name="hyperliquid", testnet=use_testnet)
        elif isinstance(config, dict):
            from dataclasses import dataclass
            @dataclass
            class SimpleConfig:
                name: str = "hyperliquid"
                api_key: Optional[str] = None
                api_secret: Optional[str] = None
                testnet: bool = False
                rate_limit: Optional[int] = None
                metadata: Optional[Dict[str, Any]] = None
            config = SimpleConfig(**config)
            
        super().__init__(config)
        self.use_testnet = use_testnet or config.testnet
        self.base_url = self.TESTNET_URL if self.use_testnet else self.BASE_URL
        self.ws_url = self.WS_TESTNET_URL if self.use_testnet else self.WS_URL
        self.session = None
        self.ws_connection = None
        self.account = None
        self.address = None
        self.vault_address = None
        
    async def connect(self) -> bool:
        """Establish connection to the DEX."""
        if not self.session:
            self.session = httpx.AsyncClient(timeout=30.0)
        return True
    
    async def disconnect(self) -> None:
        """Disconnect from the DEX."""
        if self.session:
            await self.session.aclose()
            self.session = None
        if self.ws_connection:
            await self.ws_connection.close()
            self.ws_connection = None
            
    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authenticate with Hyperliquid using private key.
        
        Args:
            credentials: Dictionary containing 'private_key' and optional 'vault_address'
            
        Returns:
            True if authentication successful
        """
        try:
            private_key = credentials.get('private_key')
            if not private_key:
                raise AuthenticationError("Private key required for Hyperliquid")
            
            # Ensure private key has 0x prefix
            if not private_key.startswith('0x'):
                private_key = '0x' + private_key
            
            # Create eth account from private key
            self.account = EthAccount.from_key(private_key)
            self.address = self.account.address
            self.vault_address = credentials.get('vault_address')
            
            # Ensure we have a session
            await self.connect()
            
            logger.info(f"Authenticated with Hyperliquid for address {self.address}")
            return True
            
        except ValueError as e:
            raise AuthenticationError(f"Invalid private key: {str(e)}")
        except Exception as e:
            logger.error(f"Hyperliquid authentication failed: {e}")
            raise AuthenticationError(f"Failed to authenticate: {str(e)}")
    
    def _sign_request(self, action: Dict, timestamp: int) -> str:
        """
        Sign request data for Hyperliquid API.
        
        Args:
            action: The action data to sign
            timestamp: Request timestamp
            
        Returns:
            Signature string
        """
        if not self.account:
            raise AuthenticationError("Not authenticated")
        
        # Create typed data structure for EIP-712 signing
        typed_data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                ],
                "HyperliquidTransaction": [
                    {"name": "action", "type": "string"},
                    {"name": "nonce", "type": "uint64"},
                ]
            },
            "primaryType": "HyperliquidTransaction",
            "domain": {
                "name": "HyperliquidSignTransaction",
                "version": "1",
                "chainId": 1337 if self.use_testnet else 42161,  # Arbitrum chainId
            },
            "message": {
                "action": json.dumps(action, separators=(',', ':')),
                "nonce": timestamp,
            }
        }
        
        # Sign the typed data
        encoded_data = encode_typed_data(typed_data)
        signed_message = self.account.sign_message(encoded_data)
        
        return signed_message.signature.hex()
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> Any:
        """
        Make HTTP request to Hyperliquid API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Request parameters
            
        Returns:
            Response data
        """
        if not self.session:
            await self.connect()
            
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = await self.session.get(url, params=params)
            elif method == "POST":
                response = await self.session.post(url, json=params)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            if response.status_code == 429:
                raise RateLimitError("Hyperliquid", "Rate limit exceeded")
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Hyperliquid API error: {e.response.text}")
            raise ConnectorError(f"API error: {e.response.status_code}")
        except Exception as e:
            if isinstance(e, (RateLimitError, ConnectorError)):
                raise
            logger.error(f"Hyperliquid request failed: {e}")
            raise ConnectorError(f"Request failed: {str(e)}")
    
    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """Place an order on Hyperliquid."""
        try:
            # Convert symbol format (BTC-PERP -> BTC)
            coin = order.symbol.replace('-PERP', '')
            
            # Build order action
            order_action = {
                "type": "order",
                "orders": [{
                    "a": int(order.symbol.split('-')[0]),  # Asset ID
                    "b": order.side == OrderSide.BUY,
                    "p": str(order.price) if order.order_type == OrderType.LIMIT else str(0),
                    "s": str(order.quantity),
                    "r": order.reduce_only if hasattr(order, 'reduce_only') else False,
                    "t": {
                        "limit": {"tif": "Gtc"},
                        "market": {},
                    }.get(order.order_type.value.lower(), {"limit": {"tif": "Gtc"}})
                }]
            }
            
            timestamp = int(time.time() * 1000)
            signature = self._sign_request(order_action, timestamp)
            
            request_data = {
                "action": order_action,
                "nonce": timestamp,
                "signature": signature,
            }
            
            if self.vault_address:
                request_data["vaultAddress"] = self.vault_address
            
            result = await self._request("POST", "/exchange", request_data)
            
            if result.get('status') == 'ok':
                response_data = result.get('response', {}).get('data', {})
                statuses = response_data.get('statuses', [{}])
                
                if statuses and statuses[0].get('resting'):
                    order_id = statuses[0]['resting'].get('oid')
                    status = OrderStatus.NEW
                elif statuses and statuses[0].get('filled'):
                    order_id = f"filled_{timestamp}"
                    status = OrderStatus.FILLED
                else:
                    order_id = f"unknown_{timestamp}"
                    status = OrderStatus.NEW
                
                return OrderResponse(
                    order_id=order_id,
                    symbol=order.symbol,
                    side=order.side,
                    order_type=order.order_type,
                    status=status,
                    price=order.price,
                    quantity=order.quantity,
                    filled_quantity=Decimal("0"),
                    average_price=None,
                    fee=Decimal("0"),
                    timestamp=datetime.now(timezone.utc),
                )
            else:
                error_msg = result.get('response', {}).get('error', 'Unknown error')
                if 'margin' in error_msg.lower():
                    raise InsufficientBalanceError(error_msg)
                elif 'invalid' in error_msg.lower():
                    raise InvalidOrderError(error_msg)
                else:
                    raise ConnectorError(f"Order placement failed: {error_msg}")
                    
        except Exception as e:
            if isinstance(e, (InsufficientBalanceError, InvalidOrderError, ConnectorError)):
                raise
            logger.error(f"Failed to place order on Hyperliquid: {e}")
            raise ConnectorError(f"Order placement failed: {str(e)}")
    
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel an order on Hyperliquid."""
        try:
            coin = symbol.replace('-PERP', '')
            
            cancel_action = {
                "type": "cancel",
                "cancels": [{
                    "a": int(coin.split('-')[0]) if coin.isdigit() else 0,
                    "o": order_id
                }]
            }
            
            timestamp = int(time.time() * 1000)
            signature = self._sign_request(cancel_action, timestamp)
            
            request_data = {
                "action": cancel_action,
                "nonce": timestamp,
                "signature": signature,
            }
            
            if self.vault_address:
                request_data["vaultAddress"] = self.vault_address
            
            result = await self._request("POST", "/exchange", request_data)
            
            if result.get('status') == 'ok':
                return True
            elif result.get('status') == 'error':
                error = result.get('response', {}).get('error', '')
                if 'not found' in error.lower():
                    raise OrderNotFoundError(f"Order {order_id} not found")
                return False
            else:
                return False
                
        except OrderNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to cancel order on Hyperliquid: {e}")
            return False
    
    async def modify_order(
        self, symbol: str, order_id: str, modifications: Dict[str, Any]
    ) -> OrderResponse:
        """Modify an existing order by canceling and replacing."""
        try:
            # Get current order
            current_order = await self.get_order(symbol, order_id)
            
            # Cancel existing order
            cancelled = await self.cancel_order(symbol, order_id)
            if not cancelled:
                raise ConnectorError("Failed to cancel order for modification")
            
            # Create new order with modifications
            new_order = OrderRequest(
                symbol=symbol,
                side=current_order.side,
                order_type=current_order.order_type,
                quantity=modifications.get('quantity', current_order.quantity),
                price=modifications.get('price', current_order.price),
                time_in_force=current_order.time_in_force,
            )
            
            return await self.place_order(new_order)
            
        except Exception as e:
            logger.error(f"Failed to modify order: {e}")
            raise ConnectorError(f"Order modification failed: {str(e)}")
    
    async def get_order(self, symbol: str, order_id: str) -> Order:
        """Get specific order by ID."""
        orders = await self.get_orders(symbol=symbol)
        for order in orders:
            if order.order_id == order_id:
                return order
        raise OrderNotFoundError(f"Order {order_id} not found")
    
    async def get_orders(
        self, symbol: Optional[str] = None, status: Optional[OrderStatus] = None
    ) -> List[Order]:
        """Get orders from Hyperliquid."""
        try:
            # Get open orders
            request_data = {
                "type": "openOrders",
                "user": self.address,
            }
            
            result = await self._request("POST", "/info", request_data)
            
            orders = []
            for order_data in result:
                order_symbol = f"{order_data['coin']}-PERP"
                
                # Filter by symbol if specified
                if symbol and order_symbol != symbol:
                    continue
                
                order = Order(
                    order_id=order_data['oid'],
                    symbol=order_symbol,
                    side=OrderSide.BUY if order_data['side'] == 'B' else OrderSide.SELL,
                    order_type=OrderType.LIMIT,
                    status=OrderStatus.NEW,
                    price=Decimal(str(order_data['limitPx'])),
                    quantity=Decimal(str(order_data['sz'])),
                    filled_quantity=Decimal(str(order_data['sz'])) - Decimal(str(order_data.get('remainingSz', order_data['sz']))),
                    average_price=None,
                    fee=Decimal("0"),
                    timestamp=datetime.fromtimestamp(order_data['timestamp'] / 1000, tz=timezone.utc),
                    time_in_force=TimeInForce.GTC,
                )
                
                # Filter by status if specified
                if status and order.status != status:
                    continue
                    
                orders.append(order)
            
            return orders
            
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return []
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get all open orders."""
        return await self.get_orders(symbol=symbol, status=OrderStatus.NEW)
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """Get positions from Hyperliquid."""
        try:
            request_data = {
                "type": "clearinghouseState",
                "user": self.address,
            }
            
            result = await self._request("POST", "/info", request_data)
            
            positions = []
            asset_positions = result.get('assetPositions', [])
            
            for pos_data in asset_positions:
                position_info = pos_data.get('position', {})
                if position_info and float(position_info.get('szi', 0)) != 0:
                    pos_symbol = f"{position_info['coin']}-PERP"
                    
                    # Filter by symbol if specified
                    if symbol and pos_symbol != symbol:
                        continue
                    
                    size = float(position_info['szi'])
                    position = Position(
                        symbol=pos_symbol,
                        side="LONG" if size > 0 else "SHORT",
                        quantity=abs(Decimal(str(size))),
                        entry_price=Decimal(str(position_info['entryPx'])),
                        mark_price=Decimal(str(position_info.get('markPx', 0))),
                        unrealized_pnl=Decimal(str(position_info.get('unrealizedPnl', 0))),
                        realized_pnl=Decimal(str(position_info.get('realizedPnl', 0))),
                        margin_used=Decimal(str(position_info.get('marginUsed', 0))),
                        liquidation_price=Decimal(str(position_info.get('liquidationPx', 0))) if position_info.get('liquidationPx') else None,
                        leverage=int(position_info.get('leverage', 1)),
                        timestamp=datetime.now(timezone.utc),
                    )
                    positions.append(position)
            
            return positions
            
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    async def close_position(
        self, symbol: str, quantity: Optional[Decimal] = None
    ) -> OrderResponse:
        """Close a position."""
        positions = await self.get_positions(symbol=symbol)
        if not positions:
            raise ConnectorError(f"No position found for {symbol}")
        
        position = positions[0]
        close_qty = quantity or position.quantity
        close_side = OrderSide.SELL if position.side == "LONG" else OrderSide.BUY
        
        order_request = OrderRequest(
            symbol=symbol,
            side=close_side,
            order_type=OrderType.MARKET,
            quantity=close_qty,
            reduce_only=True,
        )
        
        return await self.place_order(order_request)
    
    async def get_account_info(self) -> AccountInfo:
        """Get account information from Hyperliquid."""
        try:
            request_data = {
                "type": "clearinghouseState", 
                "user": self.address,
            }
            
            result = await self._request("POST", "/info", request_data)
            
            margin_summary = result.get('marginSummary', {})
            
            return AccountInfo(
                equity=Decimal(str(margin_summary.get('accountValue', 0))),
                balance=Decimal(str(margin_summary.get('totalRawUsd', 0))),
                margin_used=Decimal(str(margin_summary.get('totalMarginUsed', 0))),
                free_margin=Decimal(str(result.get('withdrawable', 0))),
                margin_ratio=Decimal("0"),
                position_value=Decimal(str(margin_summary.get('totalNtlPos', 0))),
                unrealized_pnl=Decimal("0"),
                realized_pnl=Decimal("0"),
                timestamp=datetime.now(timezone.utc),
            )
            
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            raise ConnectorError(f"Failed to get account info: {str(e)}")
    
    async def get_balance(self, asset: Optional[str] = None) -> Dict[str, Decimal]:
        """Get balance for specific asset or all assets."""
        account_info = await self.get_account_info()
        if asset:
            return {asset: account_info.free_margin}
        return {"USDC": account_info.free_margin}
    
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for a symbol."""
        try:
            coin = symbol.replace('-PERP', '')
            
            leverage_action = {
                "type": "updateLeverage",
                "asset": int(coin.split('-')[0]) if coin.isdigit() else 0,
                "isCross": True,
                "leverage": leverage,
            }
            
            timestamp = int(time.time() * 1000)
            signature = self._sign_request(leverage_action, timestamp)
            
            request_data = {
                "action": leverage_action,
                "nonce": timestamp,
                "signature": signature,
            }
            
            if self.vault_address:
                request_data["vaultAddress"] = self.vault_address
            
            result = await self._request("POST", "/exchange", request_data)
            
            return result.get('status') == 'ok'
            
        except Exception as e:
            logger.error(f"Failed to set leverage: {e}")
            return False
    
    async def get_market_data(self, symbol: str) -> MarketData:
        """Get market data for a symbol."""
        try:
            coin = symbol.replace('-PERP', '')
            
            # Get metadata
            meta_result = await self._request("POST", "/info", {"type": "meta"})
            
            # Find asset info
            asset_info = None
            for asset in meta_result.get('universe', []):
                if asset['name'] == coin:
                    asset_info = asset
                    break
            
            if not asset_info:
                raise ConnectorError(f"Symbol {symbol} not found")
            
            # Get current prices
            prices_result = await self._request("POST", "/info", {"type": "allMids"})
            
            # Find price for this coin
            price_info = None
            for price_data in prices_result:
                if price_data['coin'] == coin:
                    price_info = price_data
                    break
            
            return MarketData(
                symbol=symbol,
                mark_price=Decimal(str(price_info['markPx'])) if price_info else Decimal("0"),
                index_price=Decimal("0"),
                last_price=Decimal(str(price_info['midPx'])) if price_info else Decimal("0"),
                bid_price=Decimal("0"),
                ask_price=Decimal("0"),
                volume_24h=Decimal(str(price_info['dayNtlVlm'])) if price_info else Decimal("0"),
                open_interest=Decimal(str(price_info['openInterest'])) if price_info else Decimal("0"),
                funding_rate=Decimal(str(price_info['fundingRate'])) if price_info else Decimal("0"),
                next_funding_time=None,
                timestamp=datetime.now(timezone.utc),
            )
            
        except Exception as e:
            logger.error(f"Failed to get market data: {e}")
            raise ConnectorError(f"Failed to get market data: {str(e)}")
    
    async def get_order_book(
        self, symbol: str, depth: int = 20
    ) -> Dict[str, Any]:
        """Get order book for a symbol."""
        try:
            coin = symbol.replace('-PERP', '')
            
            request_data = {
                "type": "l2Book",
                "coin": coin,
            }
            
            result = await self._request("POST", "/info", request_data)
            
            levels = result.get('levels', [[]])
            bids = levels[0][:depth] if len(levels) > 0 else []
            asks = levels[1][:depth] if len(levels) > 1 else []
            
            return {
                "symbol": symbol,
                "bids": [[Decimal(b['px']), Decimal(b['sz'])] for b in bids],
                "asks": [[Decimal(a['px']), Decimal(a['sz'])] for a in asks],
                "timestamp": datetime.now(timezone.utc),
            }
            
        except Exception as e:
            logger.error(f"Failed to get order book: {e}")
            return {"symbol": symbol, "bids": [], "asks": [], "timestamp": datetime.now(timezone.utc)}
    
    async def get_recent_trades(
        self, symbol: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get recent trades for a symbol."""
        try:
            coin = symbol.replace('-PERP', '')
            
            request_data = {
                "type": "recentTrades",
                "coin": coin,
            }
            
            trades = await self._request("POST", "/info", request_data)
            
            formatted = []
            for trade in trades[:limit]:
                formatted.append({
                    "symbol": symbol,
                    "price": Decimal(str(trade.get("px", 0))),
                    "quantity": Decimal(str(trade.get("sz", 0))),
                    "side": "BUY" if trade.get("side") == "B" else "SELL",
                    "timestamp": datetime.fromtimestamp(trade.get("time", 0) / 1000, tz=timezone.utc),
                })
            
            return formatted
            
        except Exception as e:
            logger.error(f"Failed to get recent trades: {e}")
            return []
    
    async def get_funding_rate(self, symbol: str) -> Dict[str, Any]:
        """Get funding rate for a symbol."""
        market_data = await self.get_market_data(symbol)
        return {
            "symbol": symbol,
            "funding_rate": market_data.funding_rate,
            "next_funding_time": market_data.next_funding_time,
            "timestamp": market_data.timestamp,
        }
    
    async def subscribe_to_updates(
        self, channels: List[str]
    ) -> AsyncIterator[Dict[str, Any]]:
        """Subscribe to real-time updates via WebSocket."""
        ws_url = self.ws_url
        
        async with websockets.connect(ws_url) as ws:
            self.ws_connection = ws
            
            # Subscribe to channels
            for channel in channels:
                sub_msg = {
                    "method": "subscribe",
                    "subscription": {"type": channel},
                }
                await ws.send(json.dumps(sub_msg))
            
            # Yield updates
            try:
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    yield data
            finally:
                self.ws_connection = None
    
    async def unsubscribe_from_updates(self, channels: List[str]) -> bool:
        """Unsubscribe from WebSocket updates."""
        if self.ws_connection:
            for channel in channels:
                unsub_msg = {
                    "method": "unsubscribe",
                    "subscription": {"type": channel},
                }
                await self.ws_connection.send(json.dumps(unsub_msg))
        return True
    
    async def get_server_time(self) -> datetime:
        """Get server time."""
        return datetime.now(timezone.utc)
    
    async def get_exchange_info(self) -> Dict[str, Any]:
        """Get exchange information."""
        meta_result = await self._request("POST", "/info", {"type": "meta"})
        return meta_result
    
    async def get_trading_fees(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Get trading fees."""
        # Hyperliquid has standard fees
        return {
            "maker_fee": Decimal("0.0002"),  # 0.02%
            "taker_fee": Decimal("0.0005"),  # 0.05%
            "symbol": symbol,
        }