"""
Unit tests for risk management service.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from decimal import Decimal

from services.risk_management import (
    RiskManagementService,
    RiskMetrics,
    RiskLimits,
    RiskLevel
)
from models.positions import Position, PositionStatus, PositionSide
from models.orders import Order, OrderStatus
from models.accounts import Account, DexAccount


@pytest.mark.asyncio
@pytest.mark.unit
class TestRiskManagementService:
    """Test cases for RiskManagementService."""
    
    @pytest.fixture
    def risk_service(self, test_session):
        """Create risk management service instance."""
        return RiskManagementService(session=test_session)
    
    @pytest.fixture
    def sample_risk_limits(self):
        """Create sample risk limits."""
        return RiskLimits(
            max_position_size_usd=100000.0,
            max_leverage=10.0,
            max_drawdown_pct=20.0,
            max_exposure_usd=500000.0,
            min_margin_ratio=0.05,
            max_orders_per_minute=60,
            max_daily_loss_usd=10000.0,
            position_limits_per_symbol={"BTC-PERP": 50000.0}
        )
    
    async def test_check_risk_limits_within_limits(self, risk_service, sample_risk_limits):
        """Test risk check when within limits."""
        with patch.object(risk_service, '_get_account') as mock_get_account:
            with patch.object(risk_service, '_get_risk_limits') as mock_get_limits:
                with patch.object(risk_service, '_calculate_total_exposure') as mock_calc_exposure:
                    with patch.object(risk_service, '_get_available_balance') as mock_get_balance:
                        with patch.object(risk_service, '_count_recent_orders') as mock_count_orders:
                            with patch.object(risk_service, '_calculate_daily_pnl') as mock_daily_pnl:
                                mock_get_account.return_value = Mock()
                                mock_get_limits.return_value = sample_risk_limits
                                mock_calc_exposure.return_value = 100000.0
                                mock_get_balance.return_value = 50000.0
                                mock_count_orders.return_value = 10
                                mock_daily_pnl.return_value = -1000.0
                                
                                passed, violations = await risk_service.check_risk_limits(
                                    account_id=1,
                                    symbol="BTC-PERP",
                                    side="BUY",
                                    quantity=1.0,
                                    price=40000.0,
                                    leverage=2
                                )
        
        assert passed is True
        assert len(violations) == 0
    
    async def test_check_risk_limits_position_size_exceeded(self, risk_service, sample_risk_limits):
        """Test risk check when position size limit is exceeded."""
        with patch.object(risk_service, '_get_account') as mock_get_account:
            with patch.object(risk_service, '_get_risk_limits') as mock_get_limits:
                with patch.object(risk_service, '_calculate_total_exposure') as mock_calc_exposure:
                    with patch.object(risk_service, '_get_available_balance') as mock_get_balance:
                        with patch.object(risk_service, '_count_recent_orders') as mock_count_orders:
                            with patch.object(risk_service, '_calculate_daily_pnl') as mock_daily_pnl:
                                mock_get_account.return_value = Mock()
                                mock_get_limits.return_value = sample_risk_limits
                                mock_calc_exposure.return_value = 100000.0
                                mock_get_balance.return_value = 500000.0
                                mock_count_orders.return_value = 10
                                mock_daily_pnl.return_value = -1000.0
                                
                                passed, violations = await risk_service.check_risk_limits(
                                    account_id=1,
                                    symbol="BTC-PERP",
                                    side="BUY",
                                    quantity=5.0,
                                    price=50000.0,  # 5 * 50000 = 250000 > 100000 limit
                                    leverage=1
                                )
        
        assert passed is False
        assert len(violations) == 1
        assert "Position size" in violations[0]
        assert "250000" in violations[0]
    
    async def test_check_risk_limits_leverage_exceeded(self, risk_service, sample_risk_limits):
        """Test risk check when leverage limit is exceeded."""
        with patch.object(risk_service, '_get_account') as mock_get_account:
            with patch.object(risk_service, '_get_risk_limits') as mock_get_limits:
                with patch.object(risk_service, '_calculate_total_exposure') as mock_calc_exposure:
                    with patch.object(risk_service, '_get_available_balance') as mock_get_balance:
                        with patch.object(risk_service, '_count_recent_orders') as mock_count_orders:
                            with patch.object(risk_service, '_calculate_daily_pnl') as mock_daily_pnl:
                                mock_get_account.return_value = Mock()
                                mock_get_limits.return_value = sample_risk_limits
                                mock_calc_exposure.return_value = 100000.0
                                mock_get_balance.return_value = 50000.0
                                mock_count_orders.return_value = 10
                                mock_daily_pnl.return_value = -1000.0
                                
                                passed, violations = await risk_service.check_risk_limits(
                                    account_id=1,
                                    symbol="BTC-PERP",
                                    side="BUY",
                                    quantity=1.0,
                                    price=50000.0,
                                    leverage=15  # > 10 limit
                                )
        
        assert passed is False
        assert len(violations) == 1
        assert "Leverage" in violations[0]
        assert "15x" in violations[0]
    
    async def test_check_risk_limits_insufficient_margin(self, risk_service, sample_risk_limits):
        """Test risk check when insufficient margin."""
        with patch.object(risk_service, '_get_account') as mock_get_account:
            with patch.object(risk_service, '_get_risk_limits') as mock_get_limits:
                with patch.object(risk_service, '_calculate_total_exposure') as mock_calc_exposure:
                    with patch.object(risk_service, '_get_available_balance') as mock_get_balance:
                        with patch.object(risk_service, '_count_recent_orders') as mock_count_orders:
                            with patch.object(risk_service, '_calculate_daily_pnl') as mock_daily_pnl:
                                mock_get_account.return_value = Mock()
                                mock_get_limits.return_value = sample_risk_limits
                                mock_calc_exposure.return_value = 100000.0
                                mock_get_balance.return_value = 1000.0  # Very low balance
                                mock_count_orders.return_value = 10
                                mock_daily_pnl.return_value = -1000.0
                                
                                passed, violations = await risk_service.check_risk_limits(
                                    account_id=1,
                                    symbol="BTC-PERP",
                                    side="BUY",
                                    quantity=1.0,
                                    price=50000.0,
                                    leverage=10
                                )
        
        assert passed is False
        assert any("Insufficient margin" in v for v in violations)
    
    async def test_calculate_risk_metrics(self, risk_service, test_session, sample_user_account):
        """Test calculating risk metrics."""
        # Create positions
        position1 = Position(
            account_id=sample_user_account.id,
            dex_account_id=1,
            symbol="BTC-PERP",
            side=PositionSide.LONG,
            quantity=Decimal("1.0"),
            initial_quantity=Decimal("1.0"),
            entry_price=Decimal("50000"),
            mark_price=Decimal("51000"),
            unrealized_pnl=Decimal("1000"),
            realized_pnl=Decimal("0"),
            margin=Decimal("5000"),
            leverage=10,
            status=PositionStatus.OPEN,
            opened_at=datetime.utcnow()
        )
        
        position2 = Position(
            account_id=sample_user_account.id,
            dex_account_id=1,
            symbol="ETH-PERP",
            side=PositionSide.SHORT,
            quantity=Decimal("10.0"),
            initial_quantity=Decimal("10.0"),
            entry_price=Decimal("3000"),
            mark_price=Decimal("2950"),
            unrealized_pnl=Decimal("500"),
            realized_pnl=Decimal("0"),
            margin=Decimal("3000"),
            leverage=10,
            status=PositionStatus.OPEN,
            opened_at=datetime.utcnow()
        )
        
        test_session.add(position1)
        test_session.add(position2)
        await test_session.commit()
        
        with patch.object(risk_service, '_get_total_balance') as mock_balance:
            with patch.object(risk_service, '_calculate_max_drawdown') as mock_drawdown:
                with patch.object(risk_service, '_calculate_sharpe_ratio') as mock_sharpe:
                    mock_balance.return_value = 100000.0
                    mock_drawdown.return_value = 5.0
                    mock_sharpe.return_value = 1.5
                    
                    metrics = await risk_service.calculate_risk_metrics(sample_user_account.id)
        
        assert isinstance(metrics, RiskMetrics)
        assert metrics.account_id == sample_user_account.id
        assert metrics.total_exposure == (51000 * 10 + 29500 * 10)  # Both positions with leverage
        assert metrics.margin_usage_pct == 8.0  # (5000 + 3000) / 100000 * 100
        assert metrics.leverage_ratio == pytest.approx(8.05, rel=0.01)
        assert metrics.max_drawdown == 5.0
        assert metrics.sharpe_ratio == 1.5
        assert metrics.risk_level == RiskLevel.MEDIUM
        assert len(metrics.alerts) == 0
    
    async def test_calculate_risk_metrics_high_risk(self, risk_service, test_session, sample_user_account):
        """Test risk metrics with high risk levels."""
        # Create high-risk position
        position = Position(
            account_id=sample_user_account.id,
            dex_account_id=1,
            symbol="BTC-PERP",
            side=PositionSide.LONG,
            quantity=Decimal("2.0"),
            initial_quantity=Decimal("2.0"),
            entry_price=Decimal("50000"),
            mark_price=Decimal("51000"),
            unrealized_pnl=Decimal("2000"),
            realized_pnl=Decimal("0"),
            margin=Decimal("9000"),  # 90% of balance
            leverage=10,
            status=PositionStatus.OPEN,
            opened_at=datetime.utcnow()
        )
        
        test_session.add(position)
        await test_session.commit()
        
        with patch.object(risk_service, '_get_total_balance') as mock_balance:
            with patch.object(risk_service, '_calculate_max_drawdown') as mock_drawdown:
                with patch.object(risk_service, '_calculate_sharpe_ratio') as mock_sharpe:
                    mock_balance.return_value = 10000.0
                    mock_drawdown.return_value = 18.0
                    mock_sharpe.return_value = 0.5
                    
                    metrics = await risk_service.calculate_risk_metrics(sample_user_account.id)
        
        assert metrics.risk_level == RiskLevel.HIGH
        assert len(metrics.alerts) >= 2  # High margin and leverage alerts
        assert any("margin" in alert.lower() for alert in metrics.alerts)
    
    @patch('services.risk_management.redis_client')
    async def test_monitor_positions(self, mock_redis, risk_service, test_session, sample_user_account):
        """Test position monitoring."""
        mock_redis.publish = AsyncMock()
        
        # Create position near liquidation
        position = Position(
            account_id=sample_user_account.id,
            dex_account_id=1,
            symbol="BTC-PERP",
            side=PositionSide.LONG,
            quantity=Decimal("1.0"),
            initial_quantity=Decimal("1.0"),
            entry_price=Decimal("50000"),
            mark_price=Decimal("46000"),  # Close to liquidation
            liquidation_price=Decimal("45000"),
            unrealized_pnl=Decimal("-4000"),
            realized_pnl=Decimal("0"),
            margin=Decimal("5000"),
            leverage=10,
            status=PositionStatus.OPEN,
            opened_at=datetime.utcnow()
        )
        
        test_session.add(position)
        await test_session.commit()
        
        with patch.object(risk_service, '_send_alert') as mock_alert:
            with patch.object(risk_service, 'calculate_risk_metrics') as mock_metrics:
                mock_metrics.return_value = RiskMetrics(
                    account_id=sample_user_account.id,
                    timestamp=datetime.utcnow(),
                    total_exposure=460000,
                    margin_usage_pct=50,
                    leverage_ratio=9,
                    var_95=10000,
                    max_drawdown=8,
                    sharpe_ratio=1.2,
                    risk_level=RiskLevel.HIGH,
                    alerts=[]
                )
                
                # Start monitoring (will run in background)
                await risk_service.monitor_positions(sample_user_account.id, check_interval=1)
                
                # Give it time to run one iteration
                await asyncio.sleep(0.1)
                
                # Stop monitoring
                await risk_service.stop_monitoring(sample_user_account.id)
        
        # Should have sent liquidation warning
        mock_alert.assert_called()
        call_args = mock_alert.call_args
        assert "LIQUIDATION WARNING" in call_args[0][1]
    
    @patch('services.risk_management.redis_client')
    async def test_set_risk_limits(self, mock_redis, risk_service):
        """Test setting risk limits."""
        mock_redis.hset = AsyncMock()
        
        limits = RiskLimits(
            max_position_size_usd=200000.0,
            max_leverage=20.0
        )
        
        await risk_service.set_risk_limits(1, limits)
        
        mock_redis.hset.assert_called_once()
        call_args = mock_redis.hset.call_args[0]
        assert call_args[0] == "risk_limits"
        assert call_args[1] == "1"
        assert call_args[2]['max_position_size_usd'] == 200000.0
        assert call_args[2]['max_leverage'] == 20.0
    
    async def test_emergency_close_all(self, risk_service, test_session, sample_user_account):
        """Test emergency close all positions."""
        # Create positions
        position1 = Position(
            id=1,
            account_id=sample_user_account.id,
            dex_account_id=1,
            symbol="BTC-PERP",
            side=PositionSide.LONG,
            quantity=Decimal("1.0"),
            initial_quantity=Decimal("1.0"),
            entry_price=Decimal("50000"),
            mark_price=Decimal("51000"),
            margin=Decimal("5000"),
            leverage=10,
            status=PositionStatus.OPEN,
            opened_at=datetime.utcnow()
        )
        
        position2 = Position(
            id=2,
            account_id=sample_user_account.id,
            dex_account_id=1,
            symbol="ETH-PERP",
            side=PositionSide.SHORT,
            quantity=Decimal("10.0"),
            initial_quantity=Decimal("10.0"),
            entry_price=Decimal("3000"),
            mark_price=Decimal("2950"),
            margin=Decimal("3000"),
            leverage=10,
            status=PositionStatus.OPEN,
            opened_at=datetime.utcnow()
        )
        
        # Create open orders
        order1 = Order(
            account_id=sample_user_account.id,
            dex_account_id=1,
            symbol="BTC-PERP",
            side="BUY",
            order_type="LIMIT",
            quantity=Decimal("0.5"),
            price=Decimal("49000"),
            status=OrderStatus.NEW
        )
        
        test_session.add(position1)
        test_session.add(position2)
        test_session.add(order1)
        await test_session.commit()
        
        with patch.object(risk_service, '_close_position') as mock_close:
            with patch.object(risk_service, '_send_alert') as mock_alert:
                await risk_service.emergency_close_all(sample_user_account.id)
        
        # Should close both positions
        assert mock_close.call_count == 2
        
        # Should cancel the order
        await test_session.refresh(order1)
        assert order1.status == OrderStatus.CANCELED
        
        # Should send alert
        mock_alert.assert_called()
        alert_msg = mock_alert.call_args[0][1]
        assert "EMERGENCY" in alert_msg
    
    def test_determine_risk_level_low(self, risk_service):
        """Test determining low risk level."""
        level = risk_service._determine_risk_level(
            margin_usage_pct=30,
            leverage_ratio=3,
            max_drawdown=5
        )
        assert level == RiskLevel.LOW
    
    def test_determine_risk_level_medium(self, risk_service):
        """Test determining medium risk level."""
        level = risk_service._determine_risk_level(
            margin_usage_pct=60,
            leverage_ratio=6,
            max_drawdown=12
        )
        assert level == RiskLevel.MEDIUM
    
    def test_determine_risk_level_high(self, risk_service):
        """Test determining high risk level."""
        level = risk_service._determine_risk_level(
            margin_usage_pct=80,
            leverage_ratio=8,
            max_drawdown=18
        )
        assert level == RiskLevel.HIGH
    
    def test_determine_risk_level_critical(self, risk_service):
        """Test determining critical risk level."""
        level = risk_service._determine_risk_level(
            margin_usage_pct=95,
            leverage_ratio=12,
            max_drawdown=30
        )
        assert level == RiskLevel.CRITICAL
    
    def test_calculate_var(self, risk_service):
        """Test Value at Risk calculation."""
        position_values = [100000, 50000, 30000]
        
        var = risk_service._calculate_var(position_values, confidence=0.95)
        
        # Simple VaR calculation: total * volatility * z-score
        expected = sum(position_values) * 0.02 * 2.33
        assert var == pytest.approx(expected, rel=0.01)
    
    def test_calculate_var_empty(self, risk_service):
        """Test VaR calculation with no positions."""
        var = risk_service._calculate_var([], confidence=0.95)
        assert var == 0.0