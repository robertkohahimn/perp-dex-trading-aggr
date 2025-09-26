"""
Integration tests for Hyperliquid connector.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from decimal import Decimal
from datetime import datetime, timezone
import json

from connectors.hyperliquid.connector import HyperliquidConnector
from connectors.base import OrderRequest, OrderType, OrderSide, TimeInForce
from app.core.exceptions import (
    AuthenticationError,
    OrderNotFoundError,
    InsufficientBalanceError,
    InvalidOrderError,
    RateLimitError,
    ConnectorError,
)


@pytest.fixture
def mock_credentials():
    """Mock credentials for testing."""
    return {
        "private_key": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "vault_address": None,
    }


@pytest.fixture
def mock_account():
    """Mock Ethereum account."""
    with patch("connectors.hyperliquid.connector.EthAccount") as mock:
        account = Mock()
        account.address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb8"
        mock.from_key.return_value = account
        yield mock


@pytest.fixture
async def connector(mock_credentials, mock_account):
    """Create a Hyperliquid connector instance."""
    conn = HyperliquidConnector(use_testnet=True)
    await conn.authenticate(mock_credentials)
    return conn


@pytest.mark.asyncio
class TestHyperliquidAuthentication:
    """Test authentication functionality."""
    
    async def test_authenticate_success(self, mock_credentials, mock_account):
        """Test successful authentication."""
        connector = HyperliquidConnector(use_testnet=True)
        result = await connector.authenticate(mock_credentials)
        
        assert result is True
        assert connector.account is not None
        assert connector.address == "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb8"
        mock_account.from_key.assert_called_once_with(mock_credentials["private_key"])
    
    async def test_authenticate_with_vault(self, mock_credentials, mock_account):
        """Test authentication with vault address."""
        mock_credentials["vault_address"] = "0x123456789abcdef"
        connector = HyperliquidConnector(use_testnet=True)
        result = await connector.authenticate(mock_credentials)
        
        assert result is True
        assert connector.vault_address == "0x123456789abcdef"
    
    async def test_authenticate_missing_key(self):
        """Test authentication with missing private key."""
        connector = HyperliquidConnector(use_testnet=True)
        
        with pytest.raises(AuthenticationError):
            await connector.authenticate({})
    
    async def test_authenticate_invalid_key(self, mock_account):
        """Test authentication with invalid private key."""
        mock_account.from_key.side_effect = ValueError("Invalid key")
        connector = HyperliquidConnector(use_testnet=True)
        
        with pytest.raises(AuthenticationError):
            await connector.authenticate({"private_key": "invalid"})


@pytest.mark.asyncio
class TestHyperliquidOrders:
    """Test order management functionality."""
    
    async def test_place_order_success(self, connector):
        """Test successful order placement."""
        order_request = OrderRequest(
            symbol="BTC-PERP",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.1"),
            price=Decimal("50000"),
            time_in_force=TimeInForce.GTC,
        )
        
        mock_response = {
            "status": "ok",
            "response": {
                "type": "order",
                "data": {
                    "statuses": [{"resting": {"oid": "123456"}}]
                }
            }
        }
        
        with patch.object(connector, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            response = await connector.place_order(order_request)
            
            assert response.order_id == "123456"
            assert response.status == "NEW"
            assert response.symbol == "BTC-PERP"
            assert response.side == OrderSide.BUY
            assert response.quantity == Decimal("0.1")
            assert response.price == Decimal("50000")
    
    async def test_place_order_market(self, connector):
        """Test market order placement."""
        order_request = OrderRequest(
            symbol="ETH-PERP",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal("1.5"),
        )
        
        mock_response = {
            "status": "ok",
            "response": {
                "type": "order",
                "data": {
                    "statuses": [{"filled": {"totalSz": "1.5", "avgPx": "3000.50"}}]
                }
            }
        }
        
        with patch.object(connector, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            response = await connector.place_order(order_request)
            
            assert response.status == "FILLED"
            assert response.filled_quantity == Decimal("1.5")
            assert response.average_price == Decimal("3000.50")
    
    async def test_cancel_order_success(self, connector):
        """Test successful order cancellation."""
        mock_response = {"status": "ok"}
        
        with patch.object(connector, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            result = await connector.cancel_order("123456")
            
            assert result is True
            mock_request.assert_called_once()
    
    async def test_cancel_order_not_found(self, connector):
        """Test cancelling non-existent order."""
        mock_response = {"status": "error", "error": "Order not found"}
        
        with patch.object(connector, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            with pytest.raises(OrderNotFoundError):
                await connector.cancel_order("999999")
    
    async def test_modify_order_success(self, connector):
        """Test successful order modification."""
        modifications = {
            "price": Decimal("51000"),
            "quantity": Decimal("0.2"),
        }
        
        # Mock cancel and place
        with patch.object(connector, 'cancel_order', new_callable=AsyncMock) as mock_cancel:
            with patch.object(connector, 'get_orders', new_callable=AsyncMock) as mock_get:
                with patch.object(connector, 'place_order', new_callable=AsyncMock) as mock_place:
                    mock_cancel.return_value = True
                    mock_get.return_value = [{
                        "order_id": "123456",
                        "symbol": "BTC-PERP",
                        "side": "BUY",
                        "quantity": Decimal("0.1"),
                        "price": Decimal("50000"),
                        "time_in_force": "GTC",
                    }]
                    mock_place.return_value = Mock(
                        order_id="789012",
                        symbol="BTC-PERP",
                        side=OrderSide.BUY,
                        quantity=Decimal("0.2"),
                        price=Decimal("51000"),
                    )
                    
                    response = await connector.modify_order("123456", modifications)
                    
                    assert response.order_id == "789012"
                    assert response.price == Decimal("51000")
                    assert response.quantity == Decimal("0.2")
    
    async def test_get_orders_success(self, connector):
        """Test retrieving orders."""
        mock_response = [
            {
                "coin": "BTC",
                "oid": "123456",
                "side": "B",
                "sz": "0.1",
                "limitPx": "50000",
                "timestamp": 1704067200000,
                "origSz": "0.1",
            },
            {
                "coin": "ETH",
                "oid": "789012",
                "side": "A",
                "sz": "1.5",
                "limitPx": "3000",
                "timestamp": 1704067300000,
                "origSz": "1.5",
            }
        ]
        
        with patch.object(connector, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            orders = await connector.get_orders()
            
            assert len(orders) == 2
            assert orders[0]["order_id"] == "123456"
            assert orders[0]["symbol"] == "BTC-PERP"
            assert orders[0]["side"] == "BUY"
            assert orders[1]["order_id"] == "789012"
            assert orders[1]["symbol"] == "ETH-PERP"
            assert orders[1]["side"] == "SELL"


@pytest.mark.asyncio
class TestHyperliquidPositions:
    """Test position management functionality."""
    
    async def test_get_positions_success(self, connector):
        """Test retrieving positions."""
        mock_response = [
            {
                "coin": "BTC",
                "szi": "0.5",
                "entryPx": "49500.50",
                "unrealizedPnl": "250.00",
                "returnOnEquity": "0.05",
                "marginUsed": "5000.00",
                "positionValue": "24750.25",
                "maxTradeSz": "2.0",
            },
            {
                "coin": "ETH",
                "szi": "-1.0",
                "entryPx": "3100.00",
                "unrealizedPnl": "-50.00",
                "returnOnEquity": "-0.01",
                "marginUsed": "310.00",
                "positionValue": "-3100.00",
                "maxTradeSz": "10.0",
            }
        ]
        
        with patch.object(connector, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            positions = await connector.get_positions()
            
            assert len(positions) == 2
            assert positions[0]["symbol"] == "BTC-PERP"
            assert positions[0]["quantity"] == Decimal("0.5")
            assert positions[0]["side"] == "LONG"
            assert positions[0]["entry_price"] == Decimal("49500.50")
            assert positions[0]["unrealized_pnl"] == Decimal("250.00")
            
            assert positions[1]["symbol"] == "ETH-PERP"
            assert positions[1]["quantity"] == Decimal("1.0")
            assert positions[1]["side"] == "SHORT"
            assert positions[1]["entry_price"] == Decimal("3100.00")
            assert positions[1]["unrealized_pnl"] == Decimal("-50.00")
    
    async def test_get_positions_empty(self, connector):
        """Test retrieving positions when no positions exist."""
        with patch.object(connector, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = []
            
            positions = await connector.get_positions()
            
            assert positions == []


@pytest.mark.asyncio
class TestHyperliquidAccount:
    """Test account management functionality."""
    
    async def test_get_account_info_success(self, connector):
        """Test retrieving account information."""
        mock_response = {
            "marginSummary": {
                "accountValue": "10000.50",
                "totalMarginUsed": "2500.00",
                "totalNtlPos": "5000.00",
                "totalRawUsd": "7500.50",
            },
            "withdrawable": "7500.50",
        }
        
        with patch.object(connector, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            account_info = await connector.get_account_info()
            
            assert account_info["equity"] == Decimal("10000.50")
            assert account_info["margin_used"] == Decimal("2500.00")
            assert account_info["free_margin"] == Decimal("7500.50")
            assert account_info["position_value"] == Decimal("5000.00")


@pytest.mark.asyncio
class TestHyperliquidMarketData:
    """Test market data functionality."""
    
    async def test_get_market_data_success(self, connector):
        """Test retrieving market data."""
        mock_meta_response = {
            "universe": [
                {"name": "BTC", "szDecimals": 5},
                {"name": "ETH", "szDecimals": 4},
            ]
        }
        
        mock_prices_response = [
            {
                "coin": "BTC",
                "markPx": "50000.50",
                "midPx": "50000.00",
                "prevDayPx": "49000.00",
                "dayNtlVlm": "1000000.00",
                "fundingRate": "0.0001",
                "openInterest": "5000.0",
            }
        ]
        
        with patch.object(connector, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [mock_meta_response, mock_prices_response]
            
            market_data = await connector.get_market_data("BTC-PERP")
            
            assert market_data["symbol"] == "BTC-PERP"
            assert market_data["mark_price"] == Decimal("50000.50")
            assert market_data["mid_price"] == Decimal("50000.00")
            assert market_data["volume_24h"] == Decimal("1000000.00")
            assert market_data["funding_rate"] == Decimal("0.0001")
            assert market_data["open_interest"] == Decimal("5000.0")
    
    async def test_get_order_book_success(self, connector):
        """Test retrieving order book."""
        mock_response = {
            "coin": "BTC",
            "levels": [
                [
                    {"px": "49900.00", "sz": "0.5", "n": 2},
                    {"px": "49800.00", "sz": "1.0", "n": 3},
                ],
                [
                    {"px": "50100.00", "sz": "0.8", "n": 2},
                    {"px": "50200.00", "sz": "1.2", "n": 4},
                ]
            ],
            "time": 1704067200000,
        }
        
        with patch.object(connector, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            order_book = await connector.get_order_book("BTC-PERP", depth=2)
            
            assert len(order_book["bids"]) == 2
            assert len(order_book["asks"]) == 2
            assert order_book["bids"][0] == [Decimal("49900.00"), Decimal("0.5")]
            assert order_book["asks"][0] == [Decimal("50100.00"), Decimal("0.8")]
            assert order_book["symbol"] == "BTC-PERP"


@pytest.mark.asyncio
class TestHyperliquidWebSocket:
    """Test WebSocket functionality."""
    
    async def test_subscribe_to_updates(self, connector):
        """Test subscribing to WebSocket updates."""
        mock_ws = AsyncMock()
        mock_messages = [
            json.dumps({
                "channel": "trades",
                "data": {
                    "coin": "BTC",
                    "px": "50000.00",
                    "sz": "0.1",
                    "side": "buy",
                    "time": 1704067200000,
                }
            }),
            json.dumps({
                "channel": "orderbook",
                "data": {
                    "coin": "BTC",
                    "levels": [[["49900", "0.5"]], [["50100", "0.8"]]],
                }
            }),
        ]
        
        async def mock_recv():
            if mock_messages:
                return mock_messages.pop(0)
            raise asyncio.CancelledError()
        
        mock_ws.recv = mock_recv
        mock_ws.send = AsyncMock()
        
        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value.__aenter__.return_value = mock_ws
            
            updates = []
            try:
                async for update in connector.subscribe_to_updates(["trades", "orderbook"]):
                    updates.append(update)
                    if len(updates) >= 2:
                        break
            except asyncio.CancelledError:
                pass
            
            assert len(updates) >= 1
            assert updates[0]["channel"] == "trades"
            
            # Verify subscription message was sent
            mock_ws.send.assert_called()


@pytest.mark.asyncio
class TestHyperliquidErrorHandling:
    """Test error handling."""
    
    async def test_rate_limit_error(self, connector):
        """Test rate limit error handling."""
        with patch.object(connector, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = RateLimitError("Rate limit exceeded")
            
            with pytest.raises(RateLimitError):
                await connector.get_market_data("BTC-PERP")
    
    async def test_insufficient_balance_error(self, connector):
        """Test insufficient balance error."""
        order_request = OrderRequest(
            symbol="BTC-PERP",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("100"),
            price=Decimal("50000"),
        )
        
        mock_response = {
            "status": "error",
            "error": "Insufficient margin",
        }
        
        with patch.object(connector, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            with pytest.raises(InsufficientBalanceError):
                await connector.place_order(order_request)
    
    async def test_invalid_order_error(self, connector):
        """Test invalid order error."""
        order_request = OrderRequest(
            symbol="INVALID-PERP",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.001"),
            price=Decimal("50000"),
        )
        
        mock_response = {
            "status": "error",
            "error": "Invalid symbol",
        }
        
        with patch.object(connector, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            with pytest.raises(InvalidOrderError):
                await connector.place_order(order_request)
    
    async def test_connector_error(self, connector):
        """Test generic connector error."""
        with patch.object(connector.session, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = Exception("Connection failed")
            
            with pytest.raises(ConnectorError):
                await connector.get_account_info()