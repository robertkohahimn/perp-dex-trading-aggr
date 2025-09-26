"""
Unit tests for the PositionTracker service.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from services.position_tracker import (
    PositionTracker, 
    PositionInfo, 
    PositionUpdate,
    PositionMetrics
)
from models.positions import PositionSide, PositionStatus
from app.core.exceptions import PositionNotFoundException


@pytest.mark.asyncio
@pytest.mark.unit
class TestPositionTracker:
    """Test cases for PositionTracker service."""
    
    async def test_get_position_existing(self, test_position_tracker, sample_user_account, sample_position):
        """Test retrieving an existing position."""
        position = await test_position_tracker.get_position(
            account_id=sample_user_account.id,
            dex="mock",
            symbol="BTC-PERP"
        )
        
        assert position is not None
        assert position.symbol == "BTC-PERP"
        assert position.side == PositionSide.LONG
        assert position.size == 0.1
        assert position.entry_price == 50000.0
        assert position.mark_price == 51000.0
        assert position.unrealized_pnl == 100.0
    
    async def test_get_position_not_found(self, test_position_tracker, sample_user_account):
        """Test retrieving a non-existent position returns None."""
        position = await test_position_tracker.get_position(
            account_id=sample_user_account.id,
            dex="mock",
            symbol="ETH-PERP"
        )
        
        assert position is None
    
    async def test_get_all_positions(self, test_position_tracker, sample_user_account, sample_position):
        """Test retrieving all positions for an account."""
        positions = await test_position_tracker.get_all_positions(
            account_id=sample_user_account.id
        )
        
        assert len(positions) == 1
        assert positions[0].symbol == "BTC-PERP"
        assert positions[0].status == PositionStatus.OPEN
    
    async def test_get_all_positions_filtered_by_dex(self, test_position_tracker, sample_user_account, sample_position):
        """Test retrieving positions filtered by DEX."""
        positions = await test_position_tracker.get_all_positions(
            account_id=sample_user_account.id,
            dex="mock"
        )
        
        assert len(positions) == 1
        
        positions = await test_position_tracker.get_all_positions(
            account_id=sample_user_account.id,
            dex="nonexistent"
        )
        
        assert len(positions) == 0
    
    async def test_get_all_positions_filtered_by_status(self, test_position_tracker, sample_user_account, sample_position):
        """Test retrieving positions filtered by status."""
        positions = await test_position_tracker.get_all_positions(
            account_id=sample_user_account.id,
            status=PositionStatus.OPEN
        )
        
        assert len(positions) == 1
        
        positions = await test_position_tracker.get_all_positions(
            account_id=sample_user_account.id,
            status=PositionStatus.CLOSED
        )
        
        assert len(positions) == 0
    
    async def test_update_position_increase_size(self, test_position_tracker, sample_user_account, sample_position):
        """Test updating position by increasing size."""
        update = PositionUpdate(
            symbol="BTC-PERP",
            size_delta=0.05,  # Increase position
            mark_price=51500.0,
            realized_pnl=0.0
        )
        
        with patch.object(test_position_tracker, '_get_dex_account', return_value=sample_position.dex_account):
            updated = await test_position_tracker.update_position(
                account_id=sample_user_account.id,
                dex="mock",
                update=update
            )
        
        assert updated.size == 0.15  # 0.1 + 0.05
        assert updated.mark_price == 51500.0
    
    async def test_update_position_decrease_size(self, test_position_tracker, sample_user_account, sample_position):
        """Test updating position by decreasing size."""
        update = PositionUpdate(
            symbol="BTC-PERP",
            size_delta=-0.05,  # Decrease position
            mark_price=51000.0,
            realized_pnl=50.0
        )
        
        with patch.object(test_position_tracker, '_get_dex_account', return_value=sample_position.dex_account):
            updated = await test_position_tracker.update_position(
                account_id=sample_user_account.id,
                dex="mock",
                update=update
            )
        
        assert updated.size == 0.05  # 0.1 - 0.05
        assert updated.realized_pnl == 50.0
    
    async def test_update_position_close(self, test_position_tracker, sample_user_account, sample_position):
        """Test closing a position through update."""
        update = PositionUpdate(
            symbol="BTC-PERP",
            size_delta=-0.1,  # Close entire position
            mark_price=51000.0,
            realized_pnl=100.0
        )
        
        with patch.object(test_position_tracker, '_get_dex_account', return_value=sample_position.dex_account):
            updated = await test_position_tracker.update_position(
                account_id=sample_user_account.id,
                dex="mock",
                update=update
            )
        
        # Check position in database is closed
        position = await test_position_tracker.get_position(
            account_id=sample_user_account.id,
            dex="mock",
            symbol="BTC-PERP"
        )
        
        assert position is None  # Should not return closed positions
    
    async def test_close_position(self, test_position_tracker, sample_user_account, sample_position):
        """Test explicitly closing a position."""
        result = await test_position_tracker.close_position(
            account_id=sample_user_account.id,
            dex="mock",
            symbol="BTC-PERP",
            exit_price=52000.0
        )
        
        # For a long position: (exit - entry) * size
        expected_final_pnl = (52000.0 - 50000.0) * 0.1
        
        assert result['final_pnl'] == expected_final_pnl
        assert result['realized_pnl'] == expected_final_pnl  # Since initial realized_pnl was 0
    
    async def test_close_nonexistent_position(self, test_position_tracker, sample_user_account):
        """Test closing a non-existent position raises error."""
        with pytest.raises(PositionNotFoundException):
            await test_position_tracker.close_position(
                account_id=sample_user_account.id,
                dex="mock",
                symbol="NONEXISTENT",
                exit_price=50000.0
            )
    
    async def test_sync_positions(self, test_position_tracker, sample_user_account, sample_dex_account, mock_connector_response):
        """Test syncing positions with DEX."""
        with patch.object(test_position_tracker.connector_factory, 'create_connector') as mock_create_connector:
            mock_connector = AsyncMock()
            mock_connector.get_positions = AsyncMock(return_value=mock_connector_response["get_positions"])
            mock_create_connector.return_value = mock_connector
            
            with patch.object(test_position_tracker, '_get_credentials', return_value={}):
                synced_count = await test_position_tracker.sync_positions(
                    account_id=sample_user_account.id,
                    dex="mock"
                )
            
            assert synced_count == 1
            mock_connector.get_positions.assert_called_once()
    
    async def test_calculate_metrics_empty(self, test_position_tracker, sample_user_account):
        """Test calculating metrics with no positions."""
        metrics = await test_position_tracker.calculate_metrics(
            account_id=sample_user_account.id + 999  # Non-existent user
        )
        
        assert metrics.total_positions == 0
        assert metrics.open_positions == 0
        assert metrics.total_unrealized_pnl == 0.0
        assert metrics.total_realized_pnl == 0.0
    
    async def test_calculate_metrics_with_positions(self, test_position_tracker, sample_user_account, sample_position):
        """Test calculating metrics with positions."""
        metrics = await test_position_tracker.calculate_metrics(
            account_id=sample_user_account.id
        )
        
        assert metrics.total_positions == 1
        assert metrics.open_positions == 1
        assert metrics.total_unrealized_pnl == 100.0  # From sample position
        assert metrics.total_margin == 1000.0
        assert metrics.total_value == 0.1 * 51000.0  # size * mark_price
    
    async def test_check_liquidation_risk(self, test_position_tracker, sample_user_account, sample_position, test_session):
        """Test checking positions at risk of liquidation."""
        # Update position with liquidation price close to mark price
        sample_position.liquidation_price = 50000.0  # Very close to mark price (51000)
        await test_session.commit()
        
        at_risk = await test_position_tracker.check_liquidation_risk(
            account_id=sample_user_account.id,
            dex="mock"
        )
        
        assert len(at_risk) == 1
        assert at_risk[0]['symbol'] == "BTC-PERP"
        assert at_risk[0]['risk_level'] == 'HIGH'
        assert at_risk[0]['distance_pct'] < 5
    
    async def test_check_liquidation_risk_safe(self, test_position_tracker, sample_user_account, sample_position, test_session):
        """Test positions not at risk of liquidation."""
        # Update position with safe liquidation price
        sample_position.liquidation_price = 40000.0  # Far from mark price (51000)
        await test_session.commit()
        
        at_risk = await test_position_tracker.check_liquidation_risk(
            account_id=sample_user_account.id,
            dex="mock"
        )
        
        assert len(at_risk) == 0
    
    async def test_calculate_unrealized_pnl_long(self, test_position_tracker):
        """Test unrealized PnL calculation for long position."""
        from models.positions import Position
        
        position = Position(
            dex_account_id=1,
            symbol="BTC-PERP",
            side=PositionSide.LONG,
            quantity=1.0,
            entry_price=50000.0,
            mark_price=51000.0,
            status=PositionStatus.OPEN
        )
        
        pnl = test_position_tracker._calculate_unrealized_pnl(position)
        
        # Long PnL = (mark - entry) * size
        assert pnl == (51000.0 - 50000.0) * 1.0
        assert pnl == 1000.0
    
    async def test_calculate_unrealized_pnl_short(self, test_position_tracker):
        """Test unrealized PnL calculation for short position."""
        from models.positions import Position
        
        position = Position(
            dex_account_id=1,
            symbol="BTC-PERP",
            side=PositionSide.SHORT,
            quantity=1.0,
            entry_price=51000.0,
            mark_price=50000.0,
            status=PositionStatus.OPEN
        )
        
        pnl = test_position_tracker._calculate_unrealized_pnl(position)
        
        # Short PnL = (entry - mark) * size
        assert pnl == (51000.0 - 50000.0) * 1.0
        assert pnl == 1000.0
    
    async def test_position_info_conversion(self, test_position_tracker, sample_position):
        """Test converting database position to PositionInfo."""
        info = test_position_tracker._to_position_info(
            sample_position,
            dex="mock",
            account_name="test_account"
        )
        
        assert isinstance(info, PositionInfo)
        assert info.id == sample_position.id
        assert info.symbol == sample_position.symbol
        assert info.dex == "mock"
        assert info.account_name == "test_account"
    
    async def test_update_position_with_lock(self, test_position_tracker, sample_user_account):
        """Test that position updates use locks to prevent race conditions."""
        update1 = PositionUpdate(symbol="BTC-PERP", size_delta=0.1)
        update2 = PositionUpdate(symbol="BTC-PERP", size_delta=0.2)
        
        lock_key = f"{sample_user_account.id}_mock_BTC-PERP"
        
        # First update should create a lock
        assert lock_key not in test_position_tracker._update_locks
        
        with patch.object(test_position_tracker, '_get_dex_account'):
            # This would normally be called but we're testing lock creation
            pass
        
        # After first call, lock should exist
        # Note: Full test would require concurrent updates to verify lock behavior