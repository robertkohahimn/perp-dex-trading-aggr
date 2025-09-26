"""
Risk management service for monitoring and controlling trading risks.
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
import asyncio
import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from models.positions import Position, PositionStatus
from models.orders import Order, OrderStatus
from models.accounts import Account, DexAccount
from services.market_data_service import MarketDataService
from app.core.redis_client import redis_client
from app.core.exceptions import (
    RiskLimitExceededException,
    InsufficientBalanceError
)

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level categories."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class RiskMetrics:
    """Risk metrics for an account or position."""
    account_id: int
    timestamp: datetime
    total_exposure: float
    margin_usage_pct: float
    leverage_ratio: float
    var_95: float  # Value at Risk at 95% confidence
    max_drawdown: float
    sharpe_ratio: float
    risk_level: RiskLevel
    alerts: List[str] = field(default_factory=list)


@dataclass
class RiskLimits:
    """Risk limits for an account."""
    max_position_size_usd: float = 100000.0
    max_leverage: float = 10.0
    max_drawdown_pct: float = 20.0
    max_exposure_usd: float = 500000.0
    min_margin_ratio: float = 0.05  # 5%
    max_orders_per_minute: int = 60
    max_daily_loss_usd: float = 10000.0
    position_limits_per_symbol: Dict[str, float] = field(default_factory=dict)


class RiskManagementService:
    """Service for managing trading risks."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.market_data_service = MarketDataService()
        self.monitoring_tasks: Dict[int, asyncio.Task] = {}
    
    async def check_risk_limits(
        self,
        account_id: int,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        leverage: int = 1
    ) -> Tuple[bool, List[str]]:
        """Check if an order violates risk limits."""
        violations = []
        
        # Get account and risk limits
        account = await self._get_account(account_id)
        limits = await self._get_risk_limits(account_id)
        
        # Calculate order value
        order_value = quantity * price
        leveraged_value = order_value * leverage
        
        # Check position size limit
        if order_value > limits.max_position_size_usd:
            violations.append(
                f"Position size ${order_value:.2f} exceeds limit ${limits.max_position_size_usd:.2f}"
            )
        
        # Check leverage limit
        if leverage > limits.max_leverage:
            violations.append(
                f"Leverage {leverage}x exceeds limit {limits.max_leverage}x"
            )
        
        # Check symbol-specific limits
        symbol_limit = limits.position_limits_per_symbol.get(symbol)
        if symbol_limit and order_value > symbol_limit:
            violations.append(
                f"Position size for {symbol} exceeds limit ${symbol_limit:.2f}"
            )
        
        # Check total exposure
        current_exposure = await self._calculate_total_exposure(account_id)
        new_exposure = current_exposure + leveraged_value
        
        if new_exposure > limits.max_exposure_usd:
            violations.append(
                f"Total exposure ${new_exposure:.2f} would exceed limit ${limits.max_exposure_usd:.2f}"
            )
        
        # Check margin requirements
        required_margin = order_value / leverage
        available_balance = await self._get_available_balance(account_id)
        
        if required_margin > available_balance:
            violations.append(
                f"Insufficient margin: required ${required_margin:.2f}, available ${available_balance:.2f}"
            )
        
        # Check order rate limit
        recent_orders = await self._count_recent_orders(account_id, minutes=1)
        if recent_orders >= limits.max_orders_per_minute:
            violations.append(
                f"Order rate limit exceeded: {recent_orders}/{limits.max_orders_per_minute} orders per minute"
            )
        
        # Check daily loss limit
        daily_pnl = await self._calculate_daily_pnl(account_id)
        if daily_pnl < -limits.max_daily_loss_usd:
            violations.append(
                f"Daily loss limit exceeded: ${daily_pnl:.2f}"
            )
        
        return len(violations) == 0, violations
    
    async def calculate_risk_metrics(self, account_id: int) -> RiskMetrics:
        """Calculate comprehensive risk metrics for an account."""
        # Get positions
        positions = await self._get_open_positions(account_id)
        
        # Calculate exposure
        total_exposure = 0.0
        margin_used = 0.0
        position_values = []
        pnl_history = []
        
        for position in positions:
            position_value = float(position.quantity * position.mark_price)
            total_exposure += position_value * position.leverage
            margin_used += float(position.margin)
            position_values.append(position_value)
            pnl_history.append(float(position.unrealized_pnl))
        
        # Get account balance
        total_balance = await self._get_total_balance(account_id)
        
        # Calculate metrics
        margin_usage_pct = (margin_used / total_balance * 100) if total_balance > 0 else 0
        leverage_ratio = total_exposure / total_balance if total_balance > 0 else 0
        
        # Calculate VaR (simplified - would need historical data for accurate calculation)
        var_95 = self._calculate_var(position_values, confidence=0.95)
        
        # Calculate max drawdown
        max_drawdown = await self._calculate_max_drawdown(account_id)
        
        # Calculate Sharpe ratio (simplified)
        sharpe_ratio = await self._calculate_sharpe_ratio(account_id)
        
        # Determine risk level
        risk_level = self._determine_risk_level(
            margin_usage_pct, leverage_ratio, max_drawdown
        )
        
        # Generate alerts
        alerts = []
        if margin_usage_pct > 80:
            alerts.append(f"High margin usage: {margin_usage_pct:.1f}%")
        if leverage_ratio > 8:
            alerts.append(f"High leverage: {leverage_ratio:.1f}x")
        if max_drawdown > 15:
            alerts.append(f"Significant drawdown: {max_drawdown:.1f}%")
        
        return RiskMetrics(
            account_id=account_id,
            timestamp=datetime.utcnow(),
            total_exposure=total_exposure,
            margin_usage_pct=margin_usage_pct,
            leverage_ratio=leverage_ratio,
            var_95=var_95,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            risk_level=risk_level,
            alerts=alerts
        )
    
    async def monitor_positions(
        self,
        account_id: int,
        check_interval: int = 30
    ):
        """Monitor positions for risk events."""
        async def monitor_loop():
            while True:
                try:
                    # Get open positions
                    positions = await self._get_open_positions(account_id)
                    
                    for position in positions:
                        # Check liquidation risk
                        if position.liquidation_price:
                            current_price = position.mark_price
                            distance_pct = abs(
                                (float(current_price - position.liquidation_price) / 
                                 float(position.liquidation_price)) * 100
                            )
                            
                            if distance_pct < 5:
                                await self._send_alert(
                                    account_id,
                                    f"LIQUIDATION WARNING: {position.symbol} within {distance_pct:.1f}% of liquidation"
                                )
                            
                        # Check stop loss
                        if position.stop_loss_price:
                            if (position.side == "LONG" and position.mark_price <= position.stop_loss_price) or \
                               (position.side == "SHORT" and position.mark_price >= position.stop_loss_price):
                                await self._trigger_stop_loss(position)
                    
                    # Calculate and store risk metrics
                    metrics = await self.calculate_risk_metrics(account_id)
                    await self._store_risk_metrics(metrics)
                    
                    # Check for critical risk levels
                    if metrics.risk_level == RiskLevel.CRITICAL:
                        await self._handle_critical_risk(account_id, metrics)
                    
                except Exception as e:
                    logger.error(f"Error monitoring positions for account {account_id}: {e}")
                
                await asyncio.sleep(check_interval)
        
        # Start monitoring task
        task_id = account_id
        if task_id in self.monitoring_tasks:
            self.monitoring_tasks[task_id].cancel()
        
        self.monitoring_tasks[task_id] = asyncio.create_task(monitor_loop())
    
    async def stop_monitoring(self, account_id: int):
        """Stop monitoring positions for an account."""
        task_id = account_id
        if task_id in self.monitoring_tasks:
            self.monitoring_tasks[task_id].cancel()
            del self.monitoring_tasks[task_id]
    
    async def set_risk_limits(self, account_id: int, limits: RiskLimits):
        """Set risk limits for an account."""
        # Store in Redis for quick access
        await redis_client.hset(
            "risk_limits",
            str(account_id),
            {
                'max_position_size_usd': limits.max_position_size_usd,
                'max_leverage': limits.max_leverage,
                'max_drawdown_pct': limits.max_drawdown_pct,
                'max_exposure_usd': limits.max_exposure_usd,
                'min_margin_ratio': limits.min_margin_ratio,
                'max_orders_per_minute': limits.max_orders_per_minute,
                'max_daily_loss_usd': limits.max_daily_loss_usd,
                'position_limits_per_symbol': limits.position_limits_per_symbol
            }
        )
    
    async def emergency_close_all(self, account_id: int):
        """Emergency close all positions for an account."""
        logger.warning(f"Emergency close triggered for account {account_id}")
        
        positions = await self._get_open_positions(account_id)
        
        for position in positions:
            try:
                # Place market order to close position
                await self._close_position(position)
                logger.info(f"Closed position {position.id} for emergency close")
            except Exception as e:
                logger.error(f"Failed to close position {position.id}: {e}")
        
        # Cancel all open orders
        await self._cancel_all_orders(account_id)
        
        # Send notification
        await self._send_alert(
            account_id,
            "EMERGENCY: All positions closed due to risk limits"
        )
    
    # Private helper methods
    
    async def _get_account(self, account_id: int) -> Account:
        """Get account by ID."""
        stmt = select(Account).where(Account.id == account_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()
    
    async def _get_risk_limits(self, account_id: int) -> RiskLimits:
        """Get risk limits for an account."""
        data = await redis_client.hget("risk_limits", str(account_id))
        
        if data:
            return RiskLimits(**data)
        
        # Return default limits if not set
        return RiskLimits()
    
    async def _calculate_total_exposure(self, account_id: int) -> float:
        """Calculate total exposure across all positions."""
        stmt = select(Position).where(
            and_(
                Position.account_id == account_id,
                Position.status == PositionStatus.OPEN
            )
        )
        result = await self.session.execute(stmt)
        positions = result.scalars().all()
        
        total = 0.0
        for position in positions:
            total += float(position.quantity * position.mark_price * position.leverage)
        
        return total
    
    async def _get_available_balance(self, account_id: int) -> float:
        """Get available balance for an account."""
        # This would need to query actual account balance
        # For now, return a placeholder
        return 10000.0
    
    async def _get_total_balance(self, account_id: int) -> float:
        """Get total balance for an account."""
        stmt = select(func.sum(DexAccount.total_balance)).where(
            DexAccount.account_id == account_id
        )
        result = await self.session.execute(stmt)
        return float(result.scalar() or 0.0)
    
    async def _count_recent_orders(self, account_id: int, minutes: int) -> int:
        """Count recent orders."""
        since = datetime.utcnow() - timedelta(minutes=minutes)
        stmt = select(func.count(Order.id)).where(
            and_(
                Order.account_id == account_id,
                Order.created_at >= since
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0
    
    async def _calculate_daily_pnl(self, account_id: int) -> float:
        """Calculate daily P&L."""
        # This would need to query trade history
        # For now, return a placeholder
        return 0.0
    
    async def _get_open_positions(self, account_id: int) -> List[Position]:
        """Get open positions for an account."""
        stmt = select(Position).where(
            and_(
                Position.account_id == account_id,
                Position.status == PositionStatus.OPEN
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    def _calculate_var(self, position_values: List[float], confidence: float) -> float:
        """Calculate Value at Risk."""
        if not position_values:
            return 0.0
        
        # Simplified VaR calculation
        # In practice, would use historical returns and proper statistical methods
        total_value = sum(position_values)
        # Assume 2% daily volatility
        return total_value * 0.02 * 2.33  # 2.33 for 99% confidence
    
    async def _calculate_max_drawdown(self, account_id: int) -> float:
        """Calculate maximum drawdown."""
        # This would need historical account value data
        # For now, return a placeholder
        return 5.0
    
    async def _calculate_sharpe_ratio(self, account_id: int) -> float:
        """Calculate Sharpe ratio."""
        # This would need historical returns data
        # For now, return a placeholder
        return 1.5
    
    def _determine_risk_level(
        self,
        margin_usage_pct: float,
        leverage_ratio: float,
        max_drawdown: float
    ) -> RiskLevel:
        """Determine overall risk level."""
        if margin_usage_pct > 90 or leverage_ratio > 10 or max_drawdown > 25:
            return RiskLevel.CRITICAL
        elif margin_usage_pct > 70 or leverage_ratio > 7 or max_drawdown > 15:
            return RiskLevel.HIGH
        elif margin_usage_pct > 50 or leverage_ratio > 5 or max_drawdown > 10:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    async def _send_alert(self, account_id: int, message: str):
        """Send risk alert."""
        # Publish to Redis pub/sub
        await redis_client.publish(
            f"risk_alerts:{account_id}",
            {
                'timestamp': datetime.utcnow().isoformat(),
                'message': message
            }
        )
        logger.warning(f"Risk alert for account {account_id}: {message}")
    
    async def _store_risk_metrics(self, metrics: RiskMetrics):
        """Store risk metrics in Redis."""
        await redis_client.hset(
            f"risk_metrics:{metrics.account_id}",
            datetime.utcnow().isoformat(),
            {
                'total_exposure': metrics.total_exposure,
                'margin_usage_pct': metrics.margin_usage_pct,
                'leverage_ratio': metrics.leverage_ratio,
                'var_95': metrics.var_95,
                'max_drawdown': metrics.max_drawdown,
                'sharpe_ratio': metrics.sharpe_ratio,
                'risk_level': metrics.risk_level.value,
                'alerts': metrics.alerts
            }
        )
    
    async def _handle_critical_risk(self, account_id: int, metrics: RiskMetrics):
        """Handle critical risk situation."""
        logger.error(f"CRITICAL RISK for account {account_id}: {metrics.alerts}")
        
        # Could trigger automatic risk reduction
        # For now, just send alert
        await self._send_alert(
            account_id,
            f"CRITICAL RISK LEVEL: {', '.join(metrics.alerts)}"
        )
    
    async def _trigger_stop_loss(self, position: Position):
        """Trigger stop loss for a position."""
        logger.info(f"Triggering stop loss for position {position.id}")
        # This would place a market order to close the position
        pass
    
    async def _close_position(self, position: Position):
        """Close a position."""
        # This would place a market order to close the position
        pass
    
    async def _cancel_all_orders(self, account_id: int):
        """Cancel all open orders for an account."""
        stmt = select(Order).where(
            and_(
                Order.account_id == account_id,
                Order.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED])
            )
        )
        result = await self.session.execute(stmt)
        orders = result.scalars().all()
        
        for order in orders:
            order.status = OrderStatus.CANCELED
        
        await self.session.commit()