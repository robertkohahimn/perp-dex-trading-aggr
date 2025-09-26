"""
Integration tests for services working together.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from services.account_manager import AccountManager
from services.order_executor import OrderExecutor, OrderRequest
from services.position_tracker import PositionTracker, PositionUpdate
from models.orders import OrderSide, OrderType, OrderStatus, TimeInForce
from models.positions import PositionSide, PositionStatus


@pytest.mark.asyncio
@pytest.mark.integration
class TestServicesIntegration:
    """Integration tests for multiple services."""
    
    async def test_account_to_order_flow(self, test_session, sample_user_account, test_settings):
        """Test complete flow from account creation to order placement."""
        # Patch settings before creating services
        import services.account_manager
        import services.order_executor
        original_am_settings = services.account_manager.settings
        original_oe_settings = services.order_executor.settings
        services.account_manager.settings = test_settings
        services.order_executor.settings = test_settings
        
        account_manager = AccountManager(session=test_session)
        order_executor = OrderExecutor(session=test_session)
        
        # Step 1: Add a new account
        with patch.object(account_manager.connector_factory, 'create_connector') as mock_connector:
            mock_connector.return_value.get_account_info = AsyncMock(
                return_value={'balance': 10000.0}
            )
            
            account = await account_manager.add_account(
                user_id=sample_user_account.id,
                dex="mock",
                name="integration_test",
                credentials={"api_key": "test", "api_secret": "secret"},
                is_testnet=True
            )
        
        assert account is not None
        assert account.balance == 10000.0
        
        # Step 2: Place an order using the account
        with patch.object(order_executor.connector_factory, 'create_connector') as mock_connector:
            mock_connector.return_value.place_order = AsyncMock(
                return_value={
                    "orderId": "INT-TEST-001",
                    "status": "NEW",
                    "executedQty": 0,
                    "avgPrice": 0
                }
            )
            
            request = OrderRequest(
                symbol="BTC-PERP",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=0.1,
                price=50000.0
            )
            
            with patch.object(order_executor, '_get_credentials', return_value={}):
                result = await order_executor.place_order(
                    account_id=sample_user_account.id,
                    dex="mock",
                    request=request
                )
        
        assert result.order_id == "INT-TEST-001"
        assert result.status == OrderStatus.NEW
        
        # Step 3: Verify order is in database
        orders = await order_executor.get_orders(
            account_id=sample_user_account.id,
            dex="mock"
        )
        
        assert len(orders) == 1
        assert orders[0].symbol == "BTC-PERP"
    
    async def test_order_to_position_flow(self, test_session, sample_user_account, sample_dex_account):
        """Test flow from order execution to position tracking."""
        order_executor = OrderExecutor(session=test_session)
        position_tracker = PositionTracker(session=test_session)
        
        # Step 1: Place an order
        with patch.object(order_executor.connector_factory, 'create_connector') as mock_connector:
            mock_connector.return_value.place_order = AsyncMock(
                return_value={
                    "orderId": "POS-TEST-001",
                    "status": "FILLED",
                    "executedQty": 0.1,
                    "avgPrice": 50000.0
                }
            )
            
            request = OrderRequest(
                symbol="ETH-PERP",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=1.0
            )
            
            with patch.object(order_executor, '_get_credentials', return_value={}):
                with patch.object(order_executor, '_validate_order', return_value=None):
                    order_result = await order_executor.place_order(
                        account_id=sample_user_account.id,
                        dex="mock",
                        request=request
                    )
        
        # Step 2: Update position based on filled order
        position_update = PositionUpdate(
            symbol="ETH-PERP",
            size_delta=0.1,
            mark_price=50000.0,
            realized_pnl=0.0
        )
        
        updated_position = await position_tracker.update_position(
            account_id=sample_user_account.id,
            dex="mock",
            update=position_update
        )
        
        assert updated_position.symbol == "ETH-PERP"
        assert updated_position.size == 0.1
        assert updated_position.entry_price == 50000.0
        
        # Step 3: Verify position exists
        position = await position_tracker.get_position(
            account_id=sample_user_account.id,
            dex="mock",
            symbol="ETH-PERP"
        )
        
        assert position is not None
        assert position.status == PositionStatus.OPEN
    
    async def test_complete_trading_cycle(self, test_session, sample_user_account):
        """Test complete trading cycle: account -> order -> position -> close."""
        account_manager = AccountManager(session=test_session)
        order_executor = OrderExecutor(session=test_session)
        position_tracker = PositionTracker(session=test_session)
        
        # Step 1: Create account
        with patch.object(account_manager.connector_factory, 'create_connector') as mock_connector:
            mock_connector.return_value.get_account_info = AsyncMock(
                return_value={'balance': 50000.0}
            )
            
            account = await account_manager.add_account(
                user_id=sample_user_account.id,
                dex="mock",
                name="cycle_test",
                credentials={"api_key": "test"},
                is_testnet=True
            )
        
        # Step 2: Open position with buy order
        with patch.object(order_executor.connector_factory, 'create_connector') as mock_connector:
            mock_connector.return_value.place_order = AsyncMock(
                return_value={
                    "orderId": "OPEN-001",
                    "status": "FILLED",
                    "executedQty": 1.0,
                    "avgPrice": 3000.0
                }
            )
            
            buy_request = OrderRequest(
                symbol="SOL-PERP",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=1.0
            )
            
            with patch.object(order_executor, '_get_credentials', return_value={}):
                with patch.object(order_executor, '_validate_order', return_value=None):
                    buy_result = await order_executor.place_order(
                        account_id=sample_user_account.id,
                        dex="mock",
                        request=buy_request
                    )
        
        # Step 3: Create position from filled order
        await position_tracker.update_position(
            account_id=sample_user_account.id,
            dex="mock",
            update=PositionUpdate(
                symbol="SOL-PERP",
                size_delta=1.0,
                mark_price=3000.0
            )
        )
        
        # Step 4: Update position with profit
        await position_tracker.update_position(
            account_id=sample_user_account.id,
            dex="mock",
            update=PositionUpdate(
                symbol="SOL-PERP",
                size_delta=0,
                mark_price=3100.0  # Price increased
            )
        )
        
        # Step 5: Close position with sell order
        with patch.object(order_executor.connector_factory, 'create_connector') as mock_connector:
            mock_connector.return_value.place_order = AsyncMock(
                return_value={
                    "orderId": "CLOSE-001",
                    "status": "FILLED",
                    "executedQty": 1.0,
                    "avgPrice": 3100.0
                }
            )
            
            sell_request = OrderRequest(
                symbol="SOL-PERP",
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=1.0
            )
            
            with patch.object(order_executor, '_get_credentials', return_value={}):
                with patch.object(order_executor, '_validate_order', return_value=None):
                    sell_result = await order_executor.place_order(
                        account_id=sample_user_account.id,
                        dex="mock",
                        request=sell_request
                    )
        
        # Step 6: Close position
        pnl = await position_tracker.close_position(
            account_id=sample_user_account.id,
            dex="mock",
            symbol="SOL-PERP",
            exit_price=3100.0
        )
        
        # Verify PnL
        assert pnl['final_pnl'] == 100.0  # (3100 - 3000) * 1.0
        
        # Step 7: Verify position is closed
        position = await position_tracker.get_position(
            account_id=sample_user_account.id,
            dex="mock",
            symbol="SOL-PERP"
        )
        
        assert position is None  # Closed positions not returned
        
        # Step 8: Calculate final metrics
        metrics = await position_tracker.calculate_metrics(
            account_id=sample_user_account.id,
            dex="mock"
        )
        
        assert metrics.total_positions >= 1
        assert metrics.total_realized_pnl >= 100.0
    
    async def test_multi_account_isolation(self, test_session, sample_user_account):
        """Test that multiple accounts are properly isolated."""
        account_manager = AccountManager(session=test_session)
        
        # Create two accounts on different DEXes
        with patch.object(account_manager.connector_factory, 'create_connector') as mock_connector:
            mock_connector.return_value.get_account_info = AsyncMock(
                return_value={'balance': 5000.0}
            )
            
            account1 = await account_manager.add_account(
                user_id=sample_user_account.id,
                dex="mock",
                name="account1",
                credentials={"api_key": "key1"},
                is_testnet=True
            )
            
            account2 = await account_manager.add_account(
                user_id=sample_user_account.id,
                dex="hyperliquid",
                name="account2",
                credentials={"api_key": "key2"},
                is_testnet=True
            )
        
        # Update balance for one account
        await account_manager.update_balance(
            user_id=sample_user_account.id,
            dex="mock",
            name="account1",
            new_balance=7000.0
        )
        
        # Verify isolation
        account1_updated = await account_manager.get_account(
            user_id=sample_user_account.id,
            dex="mock",
            name="account1"
        )
        
        account2_unchanged = await account_manager.get_account(
            user_id=sample_user_account.id,
            dex="hyperliquid",
            name="account2"
        )
        
        assert account1_updated.balance == 7000.0
        assert account2_unchanged.balance == 5000.0
    
    async def test_concurrent_position_updates(self, test_session, sample_user_account, sample_dex_account):
        """Test handling concurrent position updates."""
        position_tracker = PositionTracker(session=test_session)
        
        # Create initial position
        await position_tracker.update_position(
            account_id=sample_user_account.id,
            dex="mock",
            update=PositionUpdate(
                symbol="CONCURRENT-PERP",
                size_delta=1.0,
                mark_price=100.0
            )
        )
        
        # Simulate concurrent updates
        import asyncio
        
        async def update_position(delta: float):
            await position_tracker.update_position(
                account_id=sample_user_account.id,
                dex="mock",
                update=PositionUpdate(
                    symbol="CONCURRENT-PERP",
                    size_delta=delta,
                    mark_price=100.0
                )
            )
        
        # Run multiple updates concurrently
        await asyncio.gather(
            update_position(0.1),
            update_position(0.2),
            update_position(-0.1)
        )
        
        # Verify final position
        position = await position_tracker.get_position(
            account_id=sample_user_account.id,
            dex="mock",
            symbol="CONCURRENT-PERP"
        )
        
        assert position is not None
        # 1.0 + 0.1 + 0.2 - 0.1 = 1.2
        assert position.size == 1.2
    
    async def test_error_recovery(self, test_session, sample_user_account):
        """Test service error recovery and rollback."""
        order_executor = OrderExecutor(session=test_session)
        
        # Simulate order placement failure after database insert
        with patch.object(order_executor.connector_factory, 'create_connector') as mock_connector:
            mock_connector.return_value.place_order = AsyncMock(
                side_effect=Exception("DEX connection failed")
            )
            
            request = OrderRequest(
                symbol="ERROR-PERP",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=1.0,
                price=100.0
            )
            
            with patch.object(order_executor, '_get_account', return_value=Mock(
                id=1, balance=10000.0, is_testnet=True
            )):
                with patch.object(order_executor, '_get_credentials', return_value={}):
                    with patch.object(order_executor, '_validate_order', return_value=None):
                        with pytest.raises(Exception) as exc_info:
                            await order_executor.place_order(
                                account_id=sample_user_account.id,
                                dex="mock",
                                request=request
                            )
        
        assert "Failed to place order" in str(exc_info.value)
        
        # Verify order was marked as rejected
        orders = await order_executor.get_orders(
            account_id=sample_user_account.id,
            symbol="ERROR-PERP"
        )
        
        if orders:  # If order was saved before failure
            assert orders[0].status == OrderStatus.REJECTED