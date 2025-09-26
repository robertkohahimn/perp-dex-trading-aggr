"""
Hyperliquid DEX connector implementation using official SDK.
"""
import asyncio
from typing import Dict, List, Optional, Any, AsyncIterator
from decimal import Decimal
from datetime import datetime, timezone
import logging

from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants
from hyperliquid.utils.signing import OrderType as HLOrderType
from eth_account import Account as EthAccount

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
    Connector for Hyperliquid DEX using the official SDK.
    """
    
    def __init__(self, use_testnet: bool = False, config: Optional[ConnectorConfig] = None):
        """
        Initialize Hyperliquid connector.
        
        Args:
            use_testnet: Whether to use testnet
            config: Optional connector configuration
        """
        # Create default config if not provided
        if config is None:
            config = ConnectorConfig(
                name="hyperliquid",
                api_key="",
                api_secret="",
                testnet=use_testnet
            )
        super().__init__(config)
        self.use_testnet = use_testnet
        self.base_url = constants.TESTNET_API_URL if use_testnet else constants.MAINNET_API_URL
        self.wallet = None
        self.exchange = None
        self.info = None
        self.address = None
        self.vault_address = None
        
    async def connect(self) -> bool:
        """Connect to Hyperliquid."""
        try:
            # Initialize info client (public data, no auth needed)
            self.info = Info(base_url=self.base_url, skip_ws=True)
            logger.info(f"Connected to Hyperliquid {'testnet' if self.use_testnet else 'mainnet'}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Hyperliquid: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from Hyperliquid."""
        self.wallet = None
        self.exchange = None
        self.info = None
        self.address = None
        return True
    
    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authenticate with Hyperliquid using private key.
        
        Args:
            credentials: Dict containing 'private_key' and optionally 'vault_address'
        """
        try:
            private_key = credentials.get('private_key')
            if not private_key:
                raise AuthenticationError("Private key required")
            
            # Add 0x prefix if not present
            if not private_key.startswith('0x'):
                private_key = '0x' + private_key
            
            # Create wallet from private key
            self.wallet = EthAccount.from_key(private_key)
            self.address = self.wallet.address
            self.vault_address = credentials.get('vault_address')
            
            # Initialize exchange client with wallet
            self.exchange = Exchange(
                wallet=self.wallet,
                base_url=self.base_url,
                vault_address=self.vault_address
            )
            
            # Test authentication by getting user state
            user_state = self.info.user_state(self.address)
            if user_state is None:
                # New user, no state yet is ok
                logger.info(f"New user authenticated: {self.address}")
            else:
                logger.info(f"Authenticated as {self.address}")
            
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise AuthenticationError(f"Authentication failed: {str(e)}")
    
    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """Place an order on Hyperliquid."""
        if not self.exchange:
            raise AuthenticationError("Not authenticated")
        
        try:
            # Convert symbol format (BTC-PERP -> BTC)
            coin = order.symbol.replace('-PERP', '')
            
            # Build order type - SDK uses HLOrderType which is a TypedDict
            if order.order_type == OrderType.LIMIT:
                order_type = HLOrderType(limit={"tif": self._convert_tif(order.time_in_force)})
            else:  # Market order
                order_type = HLOrderType()  # Empty dict for market orders
            
            # Place order using SDK
            result = self.exchange.order(
                name=coin,  # SDK uses 'name' instead of 'coin'
                is_buy=order.side == OrderSide.BUY,
                sz=float(order.quantity),
                limit_px=float(order.price) if order.order_type == OrderType.LIMIT else None,
                order_type=order_type,
                reduce_only=getattr(order, 'reduce_only', False)
            )
            
            # Parse response
            if result.get('status') == 'ok':
                response_data = result.get('response', {}).get('data', {})
                statuses = response_data.get('statuses', [{}])
                
                order_id = None
                status = OrderStatus.NEW
                filled_quantity = Decimal("0")
                average_price = None
                
                if statuses and statuses[0].get('resting'):
                    # Limit order resting on book
                    order_id = str(statuses[0]['resting'].get('oid'))
                    status = OrderStatus.NEW
                elif statuses and statuses[0].get('filled'):
                    # Order filled immediately
                    filled = statuses[0]['filled']
                    order_id = str(filled.get('oid'))
                    status = OrderStatus.FILLED
                    filled_quantity = Decimal(str(filled.get('totalSz', '0')))
                    average_price = Decimal(str(filled.get('avgPx', '0')))
                else:
                    # Unknown status, generate an ID
                    order_id = f"HL_{int(datetime.now().timestamp() * 1000)}"
                
                return OrderResponse(
                    order_id=order_id,
                    client_order_id=order.client_order_id,
                    symbol=order.symbol,
                    side=order.side,
                    order_type=order.order_type,
                    status=status,
                    price=order.price if order.order_type == OrderType.LIMIT else average_price,
                    quantity=order.quantity,
                    filled_quantity=filled_quantity,
                    remaining_quantity=order.quantity - filled_quantity,
                    timestamp=datetime.now(timezone.utc),
                    fee=Decimal("0"),
                )
            else:
                error_msg = result.get('response', {}).get('error', 'Unknown error')
                if 'insufficient' in error_msg.lower() or 'margin' in error_msg.lower():
                    raise InsufficientBalanceError(error_msg)
                elif 'invalid' in error_msg.lower():
                    raise InvalidOrderError(error_msg)
                else:
                    raise ConnectorError(dex="hyperliquid", detail=f"Order placement failed: {error_msg}")
                    
        except Exception as e:
            if isinstance(e, (InsufficientBalanceError, InvalidOrderError, ConnectorError)):
                raise
            logger.error(f"Failed to place order: {e}")
            raise ConnectorError(dex="hyperliquid", detail=f"Order placement failed: {str(e)}")
    
    async def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        """Cancel an order on Hyperliquid."""
        if not self.exchange:
            raise AuthenticationError("Not authenticated")
        
        try:
            coin = symbol.replace('-PERP', '') if symbol else None
            
            # If we don't have the coin, try to find it from open orders
            if not coin:
                orders = await self.get_orders()
                for order in orders:
                    if order.get('order_id') == order_id:
                        coin = order.get('symbol', '').replace('-PERP', '')
                        break
                
                if not coin:
                    logger.warning(f"Order {order_id} not found in open orders")
                    return False
            
            # Cancel using SDK
            result = self.exchange.cancel(name=coin, oid=int(order_id))
            
            if result.get('status') == 'ok':
                response_data = result.get('response', {}).get('data', {})
                statuses = response_data.get('statuses', [])
                
                # Check if cancellation was successful
                for status in statuses:
                    if 'canceled' in status:
                        return True
                
                # If no explicit canceled status, assume success if no error
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return False
    
    async def modify_order(
        self, order_id: str, modifications: Dict[str, Any], symbol: Optional[str] = None
    ) -> OrderResponse:
        """Modify an order by canceling and replacing."""
        if not self.exchange:
            raise AuthenticationError("Not authenticated")
        
        try:
            # Cancel existing order
            cancelled = await self.cancel_order(order_id, symbol)
            if not cancelled:
                raise ConnectorError(dex="hyperliquid", detail="Failed to cancel order for modification")
            
            # Get order details from modifications or existing order
            if not symbol:
                orders = await self.get_orders()
                for order in orders:
                    if order.get('order_id') == order_id:
                        symbol = order.get('symbol')
                        break
            
            if not symbol:
                raise OrderNotFoundError(f"Order {order_id} not found")
            
            # Create new order with modifications
            coin = symbol.replace('-PERP', '')
            
            # Place new order
            result = self.exchange.order(
                name=coin,  # SDK uses 'name' instead of 'coin'
                is_buy=modifications.get('side', OrderSide.BUY) == OrderSide.BUY,
                sz=float(modifications.get('quantity', 0)),
                limit_px=float(modifications.get('price', 0)),
                order_type=HLOrderType(limit={"tif": "Gtc"}),
                reduce_only=modifications.get('reduce_only', False)
            )
            
            # Parse and return response
            return self._parse_order_response(result, symbol, modifications)
            
        except Exception as e:
            logger.error(f"Failed to modify order: {e}")
            raise ConnectorError(dex="hyperliquid", detail=f"Order modification failed: {str(e)}")
    
    async def get_orders(
        self, symbol: Optional[str] = None, status: Optional[OrderStatus] = None
    ) -> List[Dict[str, Any]]:
        """Get orders from Hyperliquid."""
        if not self.info or not self.address:
            raise AuthenticationError("Not authenticated")
        
        try:
            # Get open orders from SDK
            open_orders = self.info.open_orders(self.address)
            
            orders = []
            for order_data in open_orders:
                order_symbol = f"{order_data['coin']}-PERP"
                
                # Filter by symbol if specified
                if symbol and order_symbol != symbol:
                    continue
                
                order = {
                    "order_id": str(order_data['oid']),
                    "symbol": order_symbol,
                    "side": "BUY" if order_data['side'] == 'B' else "SELL",
                    "order_type": "LIMIT",
                    "status": "NEW",
                    "price": Decimal(str(order_data['limitPx'])),
                    "quantity": Decimal(str(order_data['sz'])),
                    "filled_quantity": Decimal(str(order_data['sz'])) - Decimal(str(order_data.get('remainingSz', order_data['sz']))),
                    "average_price": None,
                    "fee": Decimal("0"),
                    "timestamp": datetime.fromtimestamp(order_data['timestamp'] / 1000, tz=timezone.utc),
                    "time_in_force": "GTC",
                }
                
                # Filter by status if specified
                if status and status.value != "NEW":
                    continue
                    
                orders.append(order)
            
            return orders
            
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return []
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get positions from Hyperliquid."""
        if not self.info or not self.address:
            raise AuthenticationError("Not authenticated")
        
        try:
            # Get user state which includes positions
            user_state = self.info.user_state(self.address)
            
            positions = []
            if user_state and 'assetPositions' in user_state:
                for asset_position in user_state['assetPositions']:
                    pos_info = asset_position.get('position', {})
                    
                    if pos_info and float(pos_info.get('szi', 0)) != 0:
                        pos_symbol = f"{pos_info['coin']}-PERP"
                        
                        # Filter by symbol if specified
                        if symbol and pos_symbol != symbol:
                            continue
                        
                        size = float(pos_info['szi'])
                        
                        # Extract leverage - it's a dict with 'type' and 'value'
                        leverage_info = pos_info.get('leverage', {})
                        leverage_value = leverage_info.get('value', 1) if isinstance(leverage_info, dict) else 1
                        
                        position = {
                            "symbol": pos_symbol,
                            "side": "LONG" if size > 0 else "SHORT",
                            "quantity": abs(Decimal(str(size))),
                            "entry_price": Decimal(str(pos_info.get('entryPx', 0))),
                            "mark_price": Decimal(str(pos_info.get('markPx', 0))),
                            "unrealized_pnl": Decimal(str(pos_info.get('unrealizedPnl', 0))),
                            "realized_pnl": Decimal(str(pos_info.get('realizedPnl', 0))),
                            "margin_used": Decimal(str(pos_info.get('marginUsed', 0))),
                            "liquidation_price": Decimal(str(pos_info.get('liquidationPx', 0))) if pos_info.get('liquidationPx') else None,
                            "leverage": int(leverage_value),
                            "timestamp": datetime.now(timezone.utc),
                        }
                        positions.append(position)
            
            return positions
            
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information from Hyperliquid."""
        if not self.info or not self.address:
            raise AuthenticationError("Not authenticated")
        
        try:
            # Get user state
            user_state = self.info.user_state(self.address)
            
            if not user_state:
                # New account with no activity
                return {
                    "equity": Decimal("0"),
                    "balance": Decimal("0"),
                    "margin_used": Decimal("0"),
                    "free_margin": Decimal("0"),
                    "margin_ratio": Decimal("0"),
                    "position_value": Decimal("0"),
                    "unrealized_pnl": Decimal("0"),
                    "realized_pnl": Decimal("0"),
                    "timestamp": datetime.now(timezone.utc),
                }
            
            margin_summary = user_state.get('marginSummary', {})
            cross_margin = user_state.get('crossMarginSummary', {})
            
            return {
                "equity": Decimal(str(cross_margin.get('accountValue', 0))),
                "balance": Decimal(str(cross_margin.get('totalRawUsd', 0))),
                "margin_used": Decimal(str(margin_summary.get('totalMarginUsed', 0))),
                "free_margin": Decimal(str(user_state.get('withdrawable', 0))),
                "margin_ratio": Decimal("0"),
                "position_value": Decimal(str(margin_summary.get('totalNtlPos', 0))),
                "unrealized_pnl": Decimal("0"),
                "realized_pnl": Decimal("0"),
                "timestamp": datetime.now(timezone.utc),
            }
            
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            raise ConnectorError(dex="hyperliquid", detail=f"Failed to get account info: {str(e)}")
    
    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get market data for a symbol."""
        if not self.info:
            raise ConnectorError(dex="hyperliquid", detail="Not connected")
        
        try:
            coin = symbol.replace('-PERP', '')
            
            # Get meta and asset contexts for complete market data
            meta_and_contexts = self.info.meta_and_asset_ctxs()
            
            if isinstance(meta_and_contexts, list) and len(meta_and_contexts) >= 2:
                meta = meta_and_contexts[0]
                contexts = meta_and_contexts[1]
                
                # Find the coin's context
                coin_index = None
                for i, asset in enumerate(meta.get('universe', [])):
                    if asset.get('name') == coin:
                        coin_index = i
                        break
                
                if coin_index is not None and coin_index < len(contexts):
                    ctx = contexts[coin_index]
                    
                    return {
                        "symbol": symbol,
                        "mark_price": Decimal(str(ctx.get('markPx', 0))),
                        "mid_price": Decimal(str(ctx.get('midPx', 0))),
                        "index_price": Decimal(str(ctx.get('markPx', 0))),
                        "last_price": Decimal(str(ctx.get('midPx', 0))),
                        "bid_price": Decimal("0"),
                        "ask_price": Decimal("0"),
                        "volume_24h": Decimal(str(ctx.get('dayNtlVlm', 0))),
                        "open_interest": Decimal(str(ctx.get('openInterest', 0))),
                        "funding_rate": Decimal(str(ctx.get('funding', 0))),
                        "next_funding_time": None,
                        "timestamp": datetime.now(timezone.utc),
                    }
            
            # Fallback to simple price data
            all_mids = self.info.all_mids()
            mid_price = Decimal(str(all_mids.get(coin, 0)))
            
            return {
                "symbol": symbol,
                "mark_price": mid_price,
                "mid_price": mid_price,
                "index_price": Decimal("0"),
                "last_price": mid_price,
                "bid_price": Decimal("0"),
                "ask_price": Decimal("0"),
                "volume_24h": Decimal("0"),
                "open_interest": Decimal("0"),
                "funding_rate": Decimal("0"),
                "next_funding_time": None,
                "timestamp": datetime.now(timezone.utc),
            }
            
        except Exception as e:
            logger.error(f"Failed to get market data: {e}")
            raise ConnectorError(dex="hyperliquid", detail=f"Failed to get market data: {str(e)}")
    
    async def get_order_book(
        self, symbol: str, depth: int = 20
    ) -> Dict[str, Any]:
        """Get order book for a symbol."""
        if not self.info:
            raise ConnectorError(dex="hyperliquid", detail="Not connected")
        
        try:
            coin = symbol.replace('-PERP', '')
            
            # Get L2 book from SDK
            book = self.info.l2_snapshot(coin)
            
            bids = []
            asks = []
            
            if book and 'levels' in book:
                # SDK returns levels as [bids_list, asks_list]
                levels = book['levels']
                if isinstance(levels, list) and len(levels) == 2:
                    # First list contains bids
                    for bid in levels[0][:depth]:  # Limit to depth
                        bids.append([
                            Decimal(str(bid['px'])),
                            Decimal(str(bid['sz']))
                        ])
                    
                    # Second list contains asks
                    for ask in levels[1][:depth]:  # Limit to depth
                        asks.append([
                            Decimal(str(ask['px'])),
                            Decimal(str(ask['sz']))
                        ])
                
                # Bids should already be sorted (highest first)
                # Asks should already be sorted (lowest first)
            
            return {
                "symbol": symbol,
                "bids": bids,
                "asks": asks,
                "timestamp": datetime.now(timezone.utc),
            }
            
        except Exception as e:
            logger.error(f"Failed to get order book: {e}")
            raise ConnectorError(dex="hyperliquid", detail=f"Failed to get order book: {str(e)}")
    
    async def subscribe_to_updates(
        self, symbols: List[str], channels: List[str]
    ) -> AsyncIterator[Dict[str, Any]]:
        """Subscribe to WebSocket updates."""
        # WebSocket subscriptions can be implemented using the SDK's WebSocket support
        # For now, return empty iterator
        yield {}
    
    async def unsubscribe_from_updates(self) -> bool:
        """Unsubscribe from all WebSocket updates."""
        return True
    
    async def get_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Get specific order by ID."""
        orders = await self.get_orders(symbol=symbol)
        for order in orders:
            if order.get('order_id') == order_id:
                return order
        raise OrderNotFoundError(f"Order {order_id} not found")
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all open orders."""
        return await self.get_orders(symbol=symbol, status=OrderStatus.NEW)
    
    async def get_balance(self, asset: Optional[str] = None) -> Dict[str, Decimal]:
        """Get balance for specific asset or all assets."""
        account_info = await self.get_account_info()
        if asset:
            # Hyperliquid uses USDC as base currency
            if asset.upper() in ['USDC', 'USD']:
                return {asset: account_info.get('balance', Decimal('0'))}
            return {asset: Decimal('0')}
        return {'USDC': account_info.get('balance', Decimal('0'))}
    
    async def get_funding_rate(self, symbol: str) -> Decimal:
        """Get current funding rate for a symbol."""
        market_data = await self.get_market_data(symbol)
        return market_data.get('funding_rate', Decimal('0'))
    
    async def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent trades for a symbol."""
        if not self.info:
            raise ConnectorError(dex="hyperliquid", detail="Not connected")
        
        try:
            coin = symbol.replace('-PERP', '')
            # The SDK doesn't have a direct recent trades method, so return empty for now
            # This could be implemented using the WebSocket feed
            return []
        except Exception as e:
            logger.error(f"Failed to get recent trades: {e}")
            return []
    
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for a symbol."""
        if not self.exchange:
            raise AuthenticationError("Not authenticated")
        
        try:
            coin = symbol.replace('-PERP', '')
            # Hyperliquid SDK has update_leverage method
            result = self.exchange.update_leverage(leverage, coin)
            return result.get('status') == 'ok'
        except Exception as e:
            logger.error(f"Failed to set leverage: {e}")
            return False
    
    async def close_position(
        self, symbol: str, quantity: Optional[Decimal] = None
    ) -> OrderResponse:
        """Close a position."""
        positions = await self.get_positions(symbol=symbol)
        if not positions:
            raise ConnectorError(dex="hyperliquid", detail=f"No position found for {symbol}")
        
        position = positions[0]
        close_qty = quantity or position.get('quantity')
        close_side = OrderSide.SELL if position.get('side') == "LONG" else OrderSide.BUY
        
        order_request = OrderRequest(
            symbol=symbol,
            side=close_side,
            order_type=OrderType.MARKET,
            quantity=close_qty,
            price=Decimal("0"),
            time_in_force=TimeInForce.IOC,
            reduce_only=True
        )
        
        return await self.place_order(order_request)
    
    # Helper methods
    
    def _convert_tif(self, tif: TimeInForce) -> str:
        """Convert TimeInForce to Hyperliquid format."""
        tif_map = {
            TimeInForce.GTC: "Gtc",
            TimeInForce.IOC: "Ioc",
            TimeInForce.FOK: "Alo",  # All or nothing
            TimeInForce.POST_ONLY: "Gtc",  # Post-only not directly supported
        }
        return tif_map.get(tif, "Gtc")
    
    def _parse_order_response(self, result: Dict, symbol: str, order_data: Dict) -> OrderResponse:
        """Parse order response from SDK."""
        if result.get('status') == 'ok':
            response_data = result.get('response', {}).get('data', {})
            statuses = response_data.get('statuses', [{}])
            
            order_id = None
            status = OrderStatus.NEW
            filled_quantity = Decimal("0")
            average_price = None
            
            if statuses and statuses[0].get('resting'):
                order_id = str(statuses[0]['resting'].get('oid'))
                status = OrderStatus.NEW
            elif statuses and statuses[0].get('filled'):
                filled = statuses[0]['filled']
                order_id = str(filled.get('oid'))
                status = OrderStatus.FILLED
                filled_quantity = Decimal(str(filled.get('totalSz', '0')))
                average_price = Decimal(str(filled.get('avgPx', '0')))
            
            return OrderResponse(
                order_id=order_id or f"HL_{int(datetime.now().timestamp() * 1000)}",
                symbol=symbol,
                side=order_data.get('side', OrderSide.BUY),
                order_type=OrderType.LIMIT,
                status=status,
                price=Decimal(str(order_data.get('price', 0))),
                quantity=Decimal(str(order_data.get('quantity', 0))),
                filled_quantity=filled_quantity,
                average_price=average_price,
                fee=Decimal("0"),
                timestamp=datetime.now(timezone.utc),
            )
        else:
            raise ConnectorError(dex="hyperliquid", detail="Order failed")