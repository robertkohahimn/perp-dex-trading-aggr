"""
Unit tests for the OrderExecutor service.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from services.order_executor import OrderExecutor, OrderRequest, OrderResult
from models.orders import OrderSide, OrderType, OrderStatus, TimeInForce
from app.core.exceptions import (
    OrderNotFoundError,
    InsufficientBalanceError,
    OrderExecutionError
)


@pytest.mark.asyncio
@pytest.mark.unit
class TestOrderExecutor:
    """Test cases for OrderExecutor service."""
    
    async def test_place_order_success(self, test_order_executor, sample_user_account, sample_dex_account, mock_connector_response):
        """Test successfully placing an order."""
        # Mock the connector
        with patch.object(test_order_executor.connector_factory, 'create_connector') as mock_create_connector:
            mock_connector = AsyncMock()
            mock_connector.place_order = AsyncMock(return_value=mock_connector_response["place_order"])
            mock_create_connector.return_value = mock_connector
            
            # Create order request
            request = OrderRequest(
                symbol="BTC-PERP",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=0.1,
                price=50000.0,
                time_in_force=TimeInForce.GTC
            )
            
            # Mock internal methods
            with patch.object(test_order_executor, '_get_account', return_value=sample_dex_account):
                with patch.object(test_order_executor, '_get_credentials', return_value={}):
                    with patch.object(test_order_executor, '_validate_order', return_value=None):
                        # Place order
                        result = await test_order_executor.place_order(
                            account_id=sample_user_account.id,
                            dex="mock",
                            request=request
                        )
            
            # Assertions
            assert result.order_id == "MOCK-ORDER-123"
            assert result.status == OrderStatus.NEW
            assert result.filled_qty == 0
            mock_connector.place_order.assert_called_once()
    
    async def test_place_order_insufficient_balance(self, test_order_executor, sample_user_account, sample_dex_account):
        """Test placing order with insufficient balance."""
        request = OrderRequest(
            symbol="BTC-PERP",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=10.0,  # Large quantity
            price=50000.0,   # High price - requires 500k balance
            time_in_force=TimeInForce.GTC
        )
        
        with patch.object(test_order_executor, '_get_account', return_value=sample_dex_account):
            with patch.object(test_order_executor, '_get_credentials', return_value={}):
                with pytest.raises(InsufficientBalanceError) as exc_info:
                    await test_order_executor.place_order(
                        account_id=sample_user_account.id,
                        dex="mock",
                        request=request
                    )
                
                assert "Insufficient balance" in str(exc_info.value)
    
    async def test_place_order_validation_errors(self, test_order_executor, sample_user_account, sample_dex_account):
        """Test order validation errors."""
        # Limit order without price
        request = OrderRequest(
            symbol="BTC-PERP",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=0.1,
            price=None  # Missing price for limit order
        )
        
        with patch.object(test_order_executor, '_get_account', return_value=sample_dex_account):
            with patch.object(test_order_executor, '_get_credentials', return_value={}):
                with pytest.raises(OrderExecutionError) as exc_info:
                    await test_order_executor.place_order(
                        account_id=sample_user_account.id,
                        dex="mock",
                        request=request
                    )
                
                assert "Limit order requires price" in str(exc_info.value)
    
    async def test_cancel_order_success(self, test_order_executor, sample_user_account, sample_order, mock_connector_response):
        """Test successfully cancelling an order."""
        with patch.object(test_order_executor.connector_factory, 'create_connector') as mock_create_connector:
            mock_connector = AsyncMock()
            mock_connector.cancel_order = AsyncMock(return_value=True)
            mock_create_connector.return_value = mock_connector
            
            with patch.object(test_order_executor, '_get_order', return_value=sample_order):
                with patch.object(test_order_executor, '_get_credentials', return_value={}):
                    result = await test_order_executor.cancel_order(
                        account_id=sample_user_account.id,
                        dex="mock",
                        order_id="TEST-ORDER-001"
                    )
            
            assert result == True
            mock_connector.cancel_order.assert_called_once_with("TEST-ORDER-001")
    
    async def test_cancel_nonexistent_order(self, test_order_executor, sample_user_account):
        """Test cancelling a non-existent order."""
        with patch.object(test_order_executor, '_get_order', return_value=None):
            with pytest.raises(OrderNotFoundError):
                await test_order_executor.cancel_order(
                    account_id=sample_user_account.id,
                    dex="mock",
                    order_id="NONEXISTENT"
                )
    
    async def test_modify_order_success(self, test_order_executor, sample_user_account, sample_order):
        """Test successfully modifying an order."""
        modifications = {
            "quantity": 0.2,
            "price": 51000.0
        }
        
        with patch.object(test_order_executor.connector_factory, 'create_connector') as mock_create_connector:
            mock_connector = AsyncMock()
            mock_connector.modify_order = AsyncMock(return_value={"success": True})
            mock_create_connector.return_value = mock_connector
            
            with patch.object(test_order_executor, '_get_order', return_value=sample_order):
                with patch.object(test_order_executor, '_get_credentials', return_value={}):
                    result = await test_order_executor.modify_order(
                        account_id=sample_user_account.id,
                        dex="mock",
                        order_id="TEST-ORDER-001",
                        modifications=modifications
                    )
            
            assert result.order_id == "TEST-ORDER-001"
            assert result.message == "Order modified successfully"
            mock_connector.modify_order.assert_called_once()
    
    async def test_modify_closed_order_fails(self, test_order_executor, sample_user_account, sample_order):
        """Test that modifying a closed order fails."""
        sample_order.status = OrderStatus.FILLED
        
        with patch.object(test_order_executor, '_get_order', return_value=sample_order):
            with pytest.raises(OrderExecutionError) as exc_info:
                await test_order_executor.modify_order(
                    account_id=sample_user_account.id,
                    dex="mock",
                    order_id="TEST-ORDER-001",
                    modifications={"quantity": 0.2}
                )
            
            assert "Cannot modify order" in str(exc_info.value)
    
    async def test_get_orders_with_filters(self, test_order_executor, sample_user_account, sample_order):
        """Test retrieving orders with various filters."""
        # Get all orders
        orders = await test_order_executor.get_orders(
            account_id=sample_user_account.id
        )
        assert len(orders) == 1
        assert orders[0].symbol == "BTC-PERP"
        
        # Filter by DEX
        orders = await test_order_executor.get_orders(
            account_id=sample_user_account.id,
            dex="mock"
        )
        assert len(orders) == 1
        
        # Filter by status
        orders = await test_order_executor.get_orders(
            account_id=sample_user_account.id,
            status=OrderStatus.NEW
        )
        assert len(orders) == 1
        
        # Filter by symbol
        orders = await test_order_executor.get_orders(
            account_id=sample_user_account.id,
            symbol="BTC-PERP"
        )
        assert len(orders) == 1
        
        # Non-matching filter
        orders = await test_order_executor.get_orders(
            account_id=sample_user_account.id,
            symbol="ETH-PERP"
        )
        assert len(orders) == 0
    
    async def test_get_active_orders(self, test_order_executor, sample_user_account, sample_order):
        """Test retrieving only active orders."""
        orders = await test_order_executor.get_active_orders(
            account_id=sample_user_account.id
        )
        
        assert len(orders) == 1
        assert orders[0].status == OrderStatus.NEW
    
    async def test_sync_orders(self, test_order_executor, sample_user_account, sample_dex_account, mock_connector_response):
        """Test syncing orders with DEX."""
        with patch.object(test_order_executor.connector_factory, 'create_connector') as mock_create_connector:
            mock_connector = AsyncMock()
            mock_connector.get_orders = AsyncMock(return_value=mock_connector_response["get_orders"])
            mock_create_connector.return_value = mock_connector
            
            with patch.object(test_order_executor, '_get_credentials', return_value={}):
                synced_count = await test_order_executor.sync_orders(
                    account_id=sample_user_account.id,
                    dex="mock"
                )
            
            assert synced_count == 1
            mock_connector.get_orders.assert_called_once()
    
    async def test_calculate_pnl_no_trades(self, test_order_executor, sample_order):
        """Test PnL calculation for order with no trades."""
        with patch.object(test_order_executor, '_get_order', return_value=sample_order):
            pnl = await test_order_executor.calculate_pnl("TEST-ORDER-001")
            
            assert pnl['realized_pnl'] == 0.0
            assert pnl['fees'] == 0.0
    
    async def test_batch_place_orders(self, test_order_executor, sample_user_account, sample_dex_account):
        """Test placing multiple orders in batch."""
        orders = [
            OrderRequest(
                symbol="BTC-PERP",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=0.1,
                price=50000.0
            ),
            OrderRequest(
                symbol="ETH-PERP",
                side=OrderSide.SELL,
                order_type=OrderType.LIMIT,
                quantity=1.0,
                price=3000.0
            )
        ]
        
        with patch.object(test_order_executor.connector_factory, 'create_connector') as mock_create_connector:
            mock_connector = AsyncMock()
            mock_connector.place_order = AsyncMock(return_value={"orderId": "TEST-123", "status": "NEW"})
            mock_create_connector.return_value = mock_connector
            
            with patch.object(test_order_executor, '_get_account', return_value=sample_dex_account):
                with patch.object(test_order_executor, '_get_credentials', return_value={}):
                    with patch.object(test_order_executor, '_validate_order', return_value=None):
                        results = await test_order_executor.batch_place_orders(
                            account_id=sample_user_account.id,
                            dex="mock",
                            orders=orders
                        )
            
            assert len(results) == 2
            assert all(r.status in [OrderStatus.NEW, OrderStatus.REJECTED] for r in results)
    
    async def test_cancel_all_orders(self, test_order_executor, sample_user_account, sample_order):
        """Test cancelling all orders."""
        with patch.object(test_order_executor, 'get_active_orders', return_value=[sample_order]):
            with patch.object(test_order_executor, 'cancel_order', return_value=True) as mock_cancel:
                cancelled_count = await test_order_executor.cancel_all_orders(
                    account_id=sample_user_account.id,
                    dex="mock"
                )
            
            assert cancelled_count == 1
            mock_cancel.assert_called_once()
    
    async def test_cancel_all_orders_by_symbol(self, test_order_executor, sample_user_account, sample_order):
        """Test cancelling all orders for a specific symbol."""
        # Create another order with different symbol
        other_order = sample_order
        other_order.symbol = "ETH-PERP"
        
        with patch.object(test_order_executor, 'get_active_orders', return_value=[sample_order, other_order]):
            with patch.object(test_order_executor, 'cancel_order', return_value=True) as mock_cancel:
                cancelled_count = await test_order_executor.cancel_all_orders(
                    account_id=sample_user_account.id,
                    dex="mock",
                    symbol="BTC-PERP"
                )
            
            assert cancelled_count == 1
    
    async def test_order_status_mapping(self, test_order_executor):
        """Test DEX status to internal status mapping."""
        assert test_order_executor._map_order_status("NEW") == OrderStatus.NEW
        assert test_order_executor._map_order_status("PARTIALLY_FILLED") == OrderStatus.PARTIALLY_FILLED
        assert test_order_executor._map_order_status("FILLED") == OrderStatus.FILLED
        assert test_order_executor._map_order_status("CANCELED") == OrderStatus.CANCELED
        assert test_order_executor._map_order_status("REJECTED") == OrderStatus.REJECTED
        assert test_order_executor._map_order_status("EXPIRED") == OrderStatus.EXPIRED
        assert test_order_executor._map_order_status("UNKNOWN") == OrderStatus.NEW  # Default