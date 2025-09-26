"""
Unit tests for market data service.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
import asyncio

from services.market_data_service import (
    MarketDataService,
    MarketData,
    OrderBook,
    OrderBookLevel,
    AggregatedMarketData
)
from app.core.exceptions import MarketDataNotAvailableError


@pytest.mark.asyncio
@pytest.mark.unit
class TestMarketDataService:
    """Test cases for MarketDataService."""
    
    @pytest.fixture
    def market_service(self):
        """Create market data service instance."""
        return MarketDataService()
    
    @pytest.fixture
    def mock_connector(self):
        """Create a mock connector."""
        mock = AsyncMock()
        mock.get_market_data = AsyncMock(return_value={
            'bid': 50000.0,
            'ask': 50010.0,
            'last': 50005.0,
            'volume_24h': 1000000.0,
            'open_24h': 49000.0,
            'high_24h': 51000.0,
            'low_24h': 48500.0,
            'mark_price': 50005.0,
            'index_price': 50000.0,
            'funding_rate': 0.0001,
            'open_interest': 5000000.0
        })
        mock.get_order_book = AsyncMock(return_value={
            'bids': [[50000.0, 10.0, 2], [49990.0, 20.0, 3]],
            'asks': [[50010.0, 15.0, 1], [50020.0, 25.0, 2]]
        })
        mock.subscribe_to_updates = AsyncMock()
        return mock
    
    @patch('services.market_data_service.redis_client')
    async def test_get_market_data(self, mock_redis, market_service, mock_connector):
        """Test getting market data for a symbol."""
        mock_redis.hset = AsyncMock()
        mock_redis.expire = AsyncMock()
        
        with patch.object(market_service.connector_factory, 'create_connector', return_value=mock_connector):
            result = await market_service.get_market_data("BTC-PERP", "hyperliquid")
        
        assert isinstance(result, MarketData)
        assert result.symbol == "BTC-PERP"
        assert result.dex == "hyperliquid"
        assert result.bid == 50000.0
        assert result.ask == 50010.0
        assert result.last == 50005.0
        assert result.volume_24h == 1000000.0
        assert result.funding_rate == 0.0001
        
        # Verify connector was called
        mock_connector.get_market_data.assert_called_once_with("BTC-PERP")
        
        # Verify Redis caching
        mock_redis.hset.assert_called_once()
        mock_redis.expire.assert_called_once()
    
    @patch('services.market_data_service.redis_client')
    async def test_get_market_data_error(self, mock_redis, market_service):
        """Test error handling when getting market data fails."""
        mock_connector = AsyncMock()
        mock_connector.get_market_data.side_effect = Exception("API error")
        
        with patch.object(market_service.connector_factory, 'create_connector', return_value=mock_connector):
            with pytest.raises(MarketDataNotAvailableError) as exc:
                await market_service.get_market_data("BTC-PERP", "hyperliquid")
            
            assert "Failed to get market data" in str(exc.value)
    
    async def test_get_aggregated_market_data(self, market_service, mock_connector):
        """Test getting aggregated market data across DEXes."""
        # Mock multiple connectors
        mock_connector2 = AsyncMock()
        mock_connector2.get_market_data = AsyncMock(return_value={
            'bid': 49995.0,
            'ask': 50015.0,
            'last': 50000.0,
            'volume_24h': 800000.0,
            'funding_rate': 0.00015,
            'open_interest': 4000000.0
        })
        
        with patch.object(market_service, 'get_market_data') as mock_get_data:
            # Mock return values for different DEXes
            mock_get_data.side_effect = [
                MarketData(
                    symbol="BTC-PERP",
                    dex="hyperliquid",
                    timestamp=datetime.utcnow(),
                    bid=50000.0,
                    ask=50010.0,
                    last=50005.0,
                    volume_24h=1000000.0,
                    open_24h=49000.0,
                    high_24h=51000.0,
                    low_24h=48500.0,
                    mark_price=50005.0,
                    index_price=50000.0,
                    funding_rate=0.0001,
                    open_interest=5000000.0
                ),
                MarketData(
                    symbol="BTC-PERP",
                    dex="lighter",
                    timestamp=datetime.utcnow(),
                    bid=49995.0,
                    ask=50015.0,
                    last=50000.0,
                    volume_24h=800000.0,
                    open_24h=49000.0,
                    high_24h=50900.0,
                    low_24h=48600.0,
                    mark_price=50000.0,
                    index_price=49995.0,
                    funding_rate=0.00015,
                    open_interest=4000000.0
                )
            ]
            
            result = await market_service.get_aggregated_market_data(
                "BTC-PERP",
                ["hyperliquid", "lighter"]
            )
        
        assert isinstance(result, AggregatedMarketData)
        assert result.symbol == "BTC-PERP"
        assert len(result.best_bid) == 2
        assert result.best_bid["hyperliquid"] == 50000.0
        assert result.best_bid["lighter"] == 49995.0
        assert result.total_volume_24h == 1800000.0
        assert result.total_open_interest == 9000000.0
        assert result.avg_price == pytest.approx(50002.5)
        assert result.avg_funding_rate == pytest.approx(0.000125)
    
    async def test_get_aggregated_market_data_no_data(self, market_service):
        """Test aggregated market data when no data is available."""
        with patch.object(market_service, 'get_market_data') as mock_get_data:
            mock_get_data.side_effect = Exception("No data")
            
            with pytest.raises(MarketDataNotAvailableError) as exc:
                await market_service.get_aggregated_market_data("BTC-PERP", ["hyperliquid"])
            
            assert "No market data available" in str(exc.value)
    
    @patch('services.market_data_service.redis_client')
    async def test_get_order_book(self, mock_redis, market_service, mock_connector):
        """Test getting order book."""
        mock_redis.hset = AsyncMock()
        mock_redis.expire = AsyncMock()
        
        with patch.object(market_service.connector_factory, 'create_connector', return_value=mock_connector):
            result = await market_service.get_order_book("BTC-PERP", "hyperliquid", depth=20)
        
        assert isinstance(result, OrderBook)
        assert result.symbol == "BTC-PERP"
        assert result.dex == "hyperliquid"
        assert len(result.bids) == 2
        assert len(result.asks) == 2
        
        # Check first bid and ask
        assert result.bids[0].price == 50000.0
        assert result.bids[0].size == 10.0
        assert result.bids[0].orders == 2
        assert result.asks[0].price == 50010.0
        assert result.asks[0].size == 15.0
        
        # Check calculated properties
        assert result.spread == 10.0
        assert result.mid_price == 50005.0
        
        # Verify connector was called
        mock_connector.get_order_book.assert_called_once_with("BTC-PERP", 20)
    
    async def test_find_arbitrage_opportunities(self, market_service):
        """Test finding arbitrage opportunities."""
        with patch.object(market_service, 'get_aggregated_market_data') as mock_get_agg:
            mock_get_agg.return_value = AggregatedMarketData(
                symbol="BTC-PERP",
                timestamp=datetime.utcnow(),
                best_bid={"hyperliquid": 50100.0, "lighter": 50000.0},
                best_ask={"hyperliquid": 50110.0, "lighter": 49990.0},  # Arb opportunity
                avg_price=50050.0,
                total_volume_24h=1800000.0,
                avg_funding_rate=0.0001,
                total_open_interest=9000000.0,
                dex_data={}
            )
            
            opportunities = await market_service.find_arbitrage_opportunities(
                "BTC-PERP",
                min_profit_pct=0.1
            )
        
        assert len(opportunities) == 1
        opp = opportunities[0]
        assert opp['symbol'] == "BTC-PERP"
        assert opp['buy_dex'] == "lighter"
        assert opp['sell_dex'] == "hyperliquid"
        assert opp['buy_price'] == 49990.0
        assert opp['sell_price'] == 50100.0
        assert opp['profit_pct'] == pytest.approx(0.22, rel=0.01)
    
    async def test_find_arbitrage_no_opportunities(self, market_service):
        """Test finding arbitrage when no opportunities exist."""
        with patch.object(market_service, 'get_aggregated_market_data') as mock_get_agg:
            mock_get_agg.return_value = AggregatedMarketData(
                symbol="BTC-PERP",
                timestamp=datetime.utcnow(),
                best_bid={"hyperliquid": 50000.0, "lighter": 49990.0},
                best_ask={"hyperliquid": 50010.0, "lighter": 50020.0},
                avg_price=50005.0,
                total_volume_24h=1800000.0,
                avg_funding_rate=0.0001,
                total_open_interest=9000000.0,
                dex_data={}
            )
            
            opportunities = await market_service.find_arbitrage_opportunities(
                "BTC-PERP",
                min_profit_pct=0.1
            )
        
        assert len(opportunities) == 0
    
    async def test_subscribe_to_market_data(self, market_service, mock_connector):
        """Test subscribing to market data updates."""
        updates = []
        
        async def callback(data):
            updates.append(data)
        
        # Mock the update stream
        async def mock_updates():
            yield {'symbol': 'BTC-PERP', 'bid': 50000, 'ask': 50010}
            yield {'symbol': 'ETH-PERP', 'bid': 3000, 'ask': 3001}  # Different symbol
            yield {'symbol': 'BTC-PERP', 'bid': 50100, 'ask': 50110}
        
        mock_connector.subscribe_to_updates.return_value = mock_updates()
        
        with patch.object(market_service.connector_factory, 'create_connector', return_value=mock_connector):
            with patch('services.market_data_service.redis_client') as mock_redis:
                mock_redis.hset = AsyncMock()
                
                sub_id = await market_service.subscribe_to_market_data(
                    "BTC-PERP",
                    "hyperliquid",
                    callback
                )
                
                # Wait for subscription to be created
                await asyncio.sleep(0.1)
        
        assert sub_id in market_service.subscriptions
        
        # Cleanup
        await market_service.unsubscribe(sub_id)
    
    async def test_unsubscribe(self, market_service):
        """Test unsubscribing from market data."""
        # Create a mock task
        mock_task = Mock()
        mock_task.cancel = Mock()
        
        sub_id = "test_subscription"
        market_service.subscriptions[sub_id] = mock_task
        
        await market_service.unsubscribe(sub_id)
        
        assert sub_id not in market_service.subscriptions
        mock_task.cancel.assert_called_once()
    
    @patch('services.market_data_service.redis_client')
    async def test_get_historical_data_cached(self, mock_redis, market_service):
        """Test getting historical data from cache."""
        cached_data = [
            {"time": 1234567890, "open": 50000, "high": 51000, "low": 49000, "close": 50500},
            {"time": 1234567950, "open": 50500, "high": 51500, "low": 50000, "close": 51000}
        ]
        mock_redis.get = AsyncMock(return_value=cached_data)
        
        result = await market_service.get_historical_data(
            "BTC-PERP",
            "hyperliquid",
            interval="1h",
            limit=100
        )
        
        assert result == cached_data
        mock_redis.get.assert_called_once()
    
    @patch('services.market_data_service.redis_client')
    async def test_get_historical_data_not_cached(self, mock_redis, market_service):
        """Test getting historical data when not cached."""
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        
        mock_connector = AsyncMock()
        
        with patch.object(market_service.connector_factory, 'create_connector', return_value=mock_connector):
            result = await market_service.get_historical_data(
                "BTC-PERP",
                "hyperliquid",
                interval="1h",
                limit=100
            )
        
        # Currently returns empty list as placeholder
        assert result == []
        
        # Verify cache was checked and set
        mock_redis.get.assert_called_once()
        mock_redis.set.assert_called_once()


class TestOrderBook:
    """Test cases for OrderBook class."""
    
    def test_order_book_spread(self):
        """Test order book spread calculation."""
        order_book = OrderBook(
            symbol="BTC-PERP",
            dex="hyperliquid",
            timestamp=datetime.utcnow(),
            bids=[OrderBookLevel(50000, 10), OrderBookLevel(49990, 20)],
            asks=[OrderBookLevel(50010, 15), OrderBookLevel(50020, 25)]
        )
        
        assert order_book.spread == 10.0
    
    def test_order_book_mid_price(self):
        """Test order book mid price calculation."""
        order_book = OrderBook(
            symbol="BTC-PERP",
            dex="hyperliquid",
            timestamp=datetime.utcnow(),
            bids=[OrderBookLevel(50000, 10)],
            asks=[OrderBookLevel(50010, 15)]
        )
        
        assert order_book.mid_price == 50005.0
    
    def test_order_book_empty(self):
        """Test order book with no bids or asks."""
        order_book = OrderBook(
            symbol="BTC-PERP",
            dex="hyperliquid",
            timestamp=datetime.utcnow(),
            bids=[],
            asks=[]
        )
        
        assert order_book.spread == 0.0
        assert order_book.mid_price == 0.0
    
    def test_order_book_to_dict(self):
        """Test order book conversion to dictionary."""
        order_book = OrderBook(
            symbol="BTC-PERP",
            dex="hyperliquid",
            timestamp=datetime.utcnow(),
            bids=[OrderBookLevel(50000, 10, 2)],
            asks=[OrderBookLevel(50010, 15, 1)]
        )
        
        result = order_book.to_dict()
        
        assert result['symbol'] == "BTC-PERP"
        assert result['dex'] == "hyperliquid"
        assert len(result['bids']) == 1
        assert result['bids'][0]['price'] == 50000
        assert result['bids'][0]['size'] == 10
        assert result['bids'][0]['orders'] == 2