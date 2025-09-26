"""
Market data aggregation service.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from decimal import Decimal
import asyncio
import logging
from dataclasses import dataclass, asdict
from enum import Enum

from app.core.redis_client import redis_client, cache_result
from connectors.factory import ConnectorFactory
from app.core.exceptions import (
    ConnectorNotFoundError,
    MarketDataNotAvailableError
)

logger = logging.getLogger(__name__)


@dataclass
class MarketData:
    """Market data snapshot."""
    symbol: str
    dex: str
    timestamp: datetime
    bid: float
    ask: float
    last: float
    volume_24h: float
    open_24h: float
    high_24h: float
    low_24h: float
    mark_price: float
    index_price: float
    funding_rate: float
    open_interest: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class OrderBookLevel:
    """Order book level."""
    price: float
    size: float
    orders: int = 1


@dataclass
class OrderBook:
    """Order book snapshot."""
    symbol: str
    dex: str
    timestamp: datetime
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'dex': self.dex,
            'timestamp': self.timestamp.isoformat(),
            'bids': [{'price': b.price, 'size': b.size, 'orders': b.orders} for b in self.bids],
            'asks': [{'price': a.price, 'size': a.size, 'orders': a.orders} for a in self.asks]
        }
    
    @property
    def spread(self) -> float:
        """Calculate bid-ask spread."""
        if self.bids and self.asks:
            return self.asks[0].price - self.bids[0].price
        return 0.0
    
    @property
    def mid_price(self) -> float:
        """Calculate mid price."""
        if self.bids and self.asks:
            return (self.asks[0].price + self.bids[0].price) / 2
        return 0.0


@dataclass
class AggregatedMarketData:
    """Aggregated market data across DEXes."""
    symbol: str
    timestamp: datetime
    best_bid: Dict[str, float]  # {dex: price}
    best_ask: Dict[str, float]  # {dex: price}
    avg_price: float
    total_volume_24h: float
    avg_funding_rate: float
    total_open_interest: float
    dex_data: Dict[str, MarketData]


class MarketDataService:
    """Service for aggregating and managing market data."""
    
    def __init__(self):
        self.connector_factory = ConnectorFactory()
        self.cache_ttl = 5  # Cache for 5 seconds
        self.subscriptions: Dict[str, asyncio.Task] = {}
    
    @cache_result(expire_seconds=5, key_prefix="market_data")
    async def get_market_data(self, symbol: str, dex: str) -> MarketData:
        """Get market data for a symbol from a specific DEX."""
        try:
            connector = self.connector_factory.create_connector(dex)
            data = await connector.get_market_data(symbol)
            
            market_data = MarketData(
                symbol=symbol,
                dex=dex,
                timestamp=datetime.utcnow(),
                bid=data.get('bid', 0.0),
                ask=data.get('ask', 0.0),
                last=data.get('last', 0.0),
                volume_24h=data.get('volume_24h', 0.0),
                open_24h=data.get('open_24h', 0.0),
                high_24h=data.get('high_24h', 0.0),
                low_24h=data.get('low_24h', 0.0),
                mark_price=data.get('mark_price', 0.0),
                index_price=data.get('index_price', 0.0),
                funding_rate=data.get('funding_rate', 0.0),
                open_interest=data.get('open_interest', 0.0)
            )
            
            # Store in Redis for quick access
            await redis_client.hset(
                f"market:{symbol}",
                dex,
                market_data.to_dict()
            )
            await redis_client.expire(f"market:{symbol}", 60)  # Expire after 1 minute
            
            return market_data
            
        except Exception as e:
            logger.error(f"Error getting market data for {symbol} from {dex}: {e}")
            raise MarketDataNotAvailableError(f"Failed to get market data: {str(e)}")
    
    async def get_aggregated_market_data(
        self, 
        symbol: str, 
        dexes: Optional[List[str]] = None
    ) -> AggregatedMarketData:
        """Get aggregated market data across multiple DEXes."""
        if not dexes:
            dexes = self.connector_factory.get_available_connectors()
        
        # Fetch data from all DEXes in parallel
        tasks = [self.get_market_data(symbol, dex) for dex in dexes]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out errors
        market_data_list = [r for r in results if isinstance(r, MarketData)]
        
        if not market_data_list:
            raise MarketDataNotAvailableError(f"No market data available for {symbol}")
        
        # Aggregate data
        best_bid = {}
        best_ask = {}
        dex_data = {}
        total_volume = 0.0
        total_oi = 0.0
        funding_rates = []
        prices = []
        
        for data in market_data_list:
            dex_data[data.dex] = data
            
            if data.bid > 0:
                best_bid[data.dex] = data.bid
            if data.ask > 0:
                best_ask[data.dex] = data.ask
            
            total_volume += data.volume_24h
            total_oi += data.open_interest
            
            if data.funding_rate != 0:
                funding_rates.append(data.funding_rate)
            
            if data.last > 0:
                prices.append(data.last)
        
        return AggregatedMarketData(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            best_bid=best_bid,
            best_ask=best_ask,
            avg_price=sum(prices) / len(prices) if prices else 0.0,
            total_volume_24h=total_volume,
            avg_funding_rate=sum(funding_rates) / len(funding_rates) if funding_rates else 0.0,
            total_open_interest=total_oi,
            dex_data=dex_data
        )
    
    @cache_result(expire_seconds=2, key_prefix="order_book")
    async def get_order_book(
        self, 
        symbol: str, 
        dex: str, 
        depth: int = 20
    ) -> OrderBook:
        """Get order book for a symbol from a specific DEX."""
        try:
            connector = self.connector_factory.create_connector(dex)
            data = await connector.get_order_book(symbol, depth)
            
            bids = [
                OrderBookLevel(price=b[0], size=b[1], orders=b[2] if len(b) > 2 else 1)
                for b in data.get('bids', [])
            ]
            
            asks = [
                OrderBookLevel(price=a[0], size=a[1], orders=a[2] if len(a) > 2 else 1)
                for a in data.get('asks', [])
            ]
            
            order_book = OrderBook(
                symbol=symbol,
                dex=dex,
                timestamp=datetime.utcnow(),
                bids=bids[:depth],
                asks=asks[:depth]
            )
            
            # Store in Redis
            await redis_client.hset(
                f"orderbook:{symbol}",
                dex,
                order_book.to_dict()
            )
            await redis_client.expire(f"orderbook:{symbol}", 10)  # Expire after 10 seconds
            
            return order_book
            
        except Exception as e:
            logger.error(f"Error getting order book for {symbol} from {dex}: {e}")
            raise MarketDataNotAvailableError(f"Failed to get order book: {str(e)}")
    
    async def find_arbitrage_opportunities(
        self,
        symbol: str,
        min_profit_pct: float = 0.1
    ) -> List[Dict[str, Any]]:
        """Find arbitrage opportunities across DEXes."""
        try:
            aggregated = await self.get_aggregated_market_data(symbol)
            opportunities = []
            
            # Check for cross-DEX arbitrage
            if aggregated.best_bid and aggregated.best_ask:
                for bid_dex, bid_price in aggregated.best_bid.items():
                    for ask_dex, ask_price in aggregated.best_ask.items():
                        if bid_dex != ask_dex and bid_price > ask_price:
                            profit_pct = ((bid_price - ask_price) / ask_price) * 100
                            
                            if profit_pct >= min_profit_pct:
                                opportunities.append({
                                    'symbol': symbol,
                                    'buy_dex': ask_dex,
                                    'sell_dex': bid_dex,
                                    'buy_price': ask_price,
                                    'sell_price': bid_price,
                                    'profit_pct': profit_pct,
                                    'timestamp': datetime.utcnow().isoformat()
                                })
            
            return opportunities
            
        except Exception as e:
            logger.error(f"Error finding arbitrage opportunities: {e}")
            return []
    
    async def subscribe_to_market_data(
        self,
        symbol: str,
        dex: str,
        callback: callable
    ) -> str:
        """Subscribe to real-time market data updates."""
        subscription_id = f"{symbol}:{dex}:{id(callback)}"
        
        async def update_loop():
            """Update loop for market data."""
            connector = self.connector_factory.create_connector(dex)
            
            try:
                async for update in connector.subscribe_to_updates(['ticker']):
                    if update.get('symbol') == symbol:
                        market_data = MarketData(
                            symbol=symbol,
                            dex=dex,
                            timestamp=datetime.utcnow(),
                            bid=update.get('bid', 0.0),
                            ask=update.get('ask', 0.0),
                            last=update.get('last', 0.0),
                            volume_24h=update.get('volume_24h', 0.0),
                            open_24h=update.get('open_24h', 0.0),
                            high_24h=update.get('high_24h', 0.0),
                            low_24h=update.get('low_24h', 0.0),
                            mark_price=update.get('mark_price', 0.0),
                            index_price=update.get('index_price', 0.0),
                            funding_rate=update.get('funding_rate', 0.0),
                            open_interest=update.get('open_interest', 0.0)
                        )
                        
                        await callback(market_data)
                        
                        # Update cache
                        await redis_client.hset(
                            f"market:{symbol}",
                            dex,
                            market_data.to_dict()
                        )
                        
            except Exception as e:
                logger.error(f"Error in market data subscription {subscription_id}: {e}")
        
        # Start subscription task
        self.subscriptions[subscription_id] = asyncio.create_task(update_loop())
        
        return subscription_id
    
    async def unsubscribe(self, subscription_id: str):
        """Unsubscribe from market data updates."""
        if subscription_id in self.subscriptions:
            self.subscriptions[subscription_id].cancel()
            del self.subscriptions[subscription_id]
    
    async def get_historical_data(
        self,
        symbol: str,
        dex: str,
        interval: str = "1h",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get historical price data."""
        cache_key = f"history:{symbol}:{dex}:{interval}:{limit}"
        
        # Try cache first
        cached = await redis_client.get(cache_key)
        if cached:
            return cached
        
        try:
            connector = self.connector_factory.create_connector(dex)
            
            # This would need to be implemented in each connector
            # For now, return empty list as placeholder
            data = []
            
            # Cache for 5 minutes
            await redis_client.set(cache_key, data, expire=300)
            
            return data
            
        except Exception as e:
            logger.error(f"Error getting historical data: {e}")
            return []