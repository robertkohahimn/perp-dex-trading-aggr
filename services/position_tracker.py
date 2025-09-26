"""
Position tracking service for managing and monitoring positions across DEXes.
"""
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
import asyncio
import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from models.positions import Position, PositionHistory, PositionSide, PositionStatus
from models.accounts import DexAccount
from models.orders import Order, Trade
from database.session import get_session
from connectors.factory import ConnectorFactory
from app.core.exceptions import (
    PositionNotFoundException,
    InsufficientBalanceError,
    RiskLimitExceededException
)

logger = logging.getLogger(__name__)


@dataclass
class PositionInfo:
    """Detailed position information."""
    id: int
    symbol: str
    side: PositionSide
    size: float
    entry_price: float
    mark_price: float
    liquidation_price: Optional[float]
    unrealized_pnl: float
    realized_pnl: float
    margin: float
    leverage: int
    status: PositionStatus
    created_at: datetime
    updated_at: datetime
    dex: str
    account_name: str


@dataclass
class PositionUpdate:
    """Position update data."""
    symbol: str
    size_delta: float = 0.0
    realized_pnl: float = 0.0
    fees: float = 0.0
    mark_price: Optional[float] = None
    liquidation_price: Optional[float] = None


@dataclass 
class PositionMetrics:
    """Position performance metrics."""
    total_positions: int = 0
    open_positions: int = 0
    total_unrealized_pnl: float = 0.0
    total_realized_pnl: float = 0.0
    total_margin: float = 0.0
    total_value: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0


class PositionTracker:
    """Service for tracking and managing positions."""
    
    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session
        self.connector_factory = ConnectorFactory()
        self._position_cache: Dict[str, PositionInfo] = {}
        self._update_locks: Dict[str, asyncio.Lock] = {}
    
    async def get_position(self,
                          account_id: int,
                          dex: str,
                          symbol: str) -> Optional[PositionInfo]:
        """Get a specific position."""
        async with (self.session or get_session()) as session:
            result = await session.execute(
                select(Position).join(DexAccount).where(
                    and_(
                        DexAccount.account_id == account_id,
                        DexAccount.dex_name == dex,
                        Position.symbol == symbol,
                        Position.status == PositionStatus.OPEN
                    )
                )
            )
            position = result.scalar_one_or_none()
            
            if not position:
                return None
            
            return self._to_position_info(position, dex)
    
    async def get_all_positions(self,
                               account_id: int,
                               dex: Optional[str] = None,
                               status: Optional[PositionStatus] = None) -> List[PositionInfo]:
        """Get all positions for an account."""
        async with (self.session or get_session()) as session:
            query = select(Position, DexAccount).join(DexAccount).where(
                DexAccount.account_id == account_id
            )
            
            if dex:
                query = query.where(DexAccount.dex_name == dex)
            if status:
                query = query.where(Position.status == status)
            else:
                query = query.where(Position.status == PositionStatus.OPEN)
            
            result = await session.execute(query)
            positions = []
            
            for position, account in result:
                positions.append(self._to_position_info(position, account.dex_name, account.account_name))
            
            return positions
    
    async def update_position(self,
                            account_id: int,
                            dex: str,
                            update: PositionUpdate) -> PositionInfo:
        """Update a position with new data."""
        lock_key = f"{account_id}_{dex}_{update.symbol}"
        if lock_key not in self._update_locks:
            self._update_locks[lock_key] = asyncio.Lock()
        
        async with self._update_locks[lock_key]:
            async with (self.session or get_session()) as session:
                # Get or create position
                result = await session.execute(
                    select(Position).join(DexAccount).where(
                        and_(
                            DexAccount.account_id == account_id,
                            DexAccount.dex_name == dex,
                            Position.symbol == update.symbol,
                            Position.status == PositionStatus.OPEN
                        )
                    )
                )
                position = result.scalar_one_or_none()
                
                if not position:
                    # Create new position
                    dex_account = await self._get_dex_account(session, account_id, dex)
                    position = Position(
                        account_id=dex_account.account_id,
                        dex_account_id=dex_account.id,
                        symbol=update.symbol,
                        side=PositionSide.LONG if update.size_delta > 0 else PositionSide.SHORT,
                        quantity=abs(update.size_delta),
                        initial_quantity=abs(update.size_delta),
                        entry_price=update.mark_price or 0,
                        mark_price=update.mark_price or 0,
                        margin=0,  # Should be calculated
                        status=PositionStatus.OPEN,
                        opened_at=datetime.utcnow()
                    )
                    session.add(position)
                else:
                    # Update existing position
                    position.quantity += update.size_delta
                    
                    if position.quantity == 0:
                        position.status = PositionStatus.CLOSED
                        position.closed_at = datetime.utcnow()
                    
                    if update.mark_price:
                        position.mark_price = update.mark_price
                        position.unrealized_pnl = self._calculate_unrealized_pnl(position)
                    
                    if update.liquidation_price:
                        position.liquidation_price = update.liquidation_price
                    
                    position.realized_pnl += update.realized_pnl
                    position.updated_at = datetime.utcnow()
                
                # Record history
                history = PositionHistory(
                    position_id=position.id,
                    size=position.quantity,
                    mark_price=position.mark_price,
                    unrealized_pnl=position.unrealized_pnl,
                    realized_pnl=position.realized_pnl,
                    margin=position.margin,
                    extra_data={
                        'size_delta': update.size_delta,
                        'fees': update.fees
                    }
                )
                session.add(history)
                
                await session.commit()
                
                return self._to_position_info(position, dex)
    
    async def close_position(self,
                           account_id: int,
                           dex: str,
                           symbol: str,
                           exit_price: float) -> Dict[str, float]:
        """Close a position and calculate final PnL."""
        async with (self.session or get_session()) as session:
            result = await session.execute(
                select(Position).join(DexAccount).where(
                    and_(
                        DexAccount.account_id == account_id,
                        DexAccount.dex_name == dex,
                        Position.symbol == symbol,
                        Position.status == PositionStatus.OPEN
                    )
                )
            )
            position = result.scalar_one_or_none()
            
            if not position:
                raise PositionNotFoundException(symbol)
            
            # Calculate final PnL
            entry = float(position.entry_price) if position.entry_price else 0
            qty = float(position.quantity) if position.quantity else 0
            
            if position.side == PositionSide.LONG:
                final_pnl = (exit_price - entry) * qty
            else:
                final_pnl = (entry - exit_price) * qty
            
            position.status = PositionStatus.CLOSED
            position.closed_at = datetime.utcnow()
            position.exit_price = exit_price
            position.realized_pnl += final_pnl
            position.unrealized_pnl = 0
            
            await session.commit()
            
            return {
                'realized_pnl': position.realized_pnl,
                'final_pnl': final_pnl,
                'total_fees': position.extra_data.get('total_fees', 0) if position.extra_data else 0
            }
    
    async def sync_positions(self,
                            account_id: int,
                            dex: str) -> int:
        """Sync positions with DEX."""
        async with (self.session or get_session()) as session:
            try:
                # Get DEX accounts
                accounts = await session.execute(
                    select(DexAccount).where(
                        and_(
                            DexAccount.account_id == account_id,
                            DexAccount.dex_name == dex,
                            DexAccount.is_active == True
                        )
                    )
                )
                
                synced_count = 0
                
                for account in accounts.scalars():
                    credentials = await self._get_credentials(session, account.id)
                    connector = self.connector_factory.create_connector(
                        dex,
                        None,  # config will be created from kwargs
                        testnet=account.is_testnet,
                        **credentials
                    )
                    
                    # Get positions from DEX
                    dex_positions = await connector.get_positions()
                    
                    for dex_pos in dex_positions:
                        # Update or create position
                        result = await session.execute(
                            select(Position).where(
                                and_(
                                    Position.dex_account_id == account.id,
                                    Position.symbol == dex_pos['symbol'],
                                    Position.status == PositionStatus.OPEN
                                )
                            )
                        )
                        position = result.scalar_one_or_none()
                        
                        if position:
                            # Update existing
                            position.quantity = dex_pos['size']
                            position.mark_price = dex_pos['markPrice']
                            position.unrealized_pnl = dex_pos.get('unrealizedPnl', 0)
                            position.realized_pnl = dex_pos.get('realizedPnl', 0)
                            position.liquidation_price = dex_pos.get('liquidationPrice')
                            position.margin = dex_pos.get('margin', 0)
                            position.updated_at = datetime.utcnow()
                        else:
                            # Create new
                            position = Position(
                                account_id=account.account_id,
                                dex_account_id=account.id,
                                symbol=dex_pos['symbol'],
                                side=PositionSide(dex_pos['side']),
                                quantity=dex_pos['size'],
                                initial_quantity=dex_pos['size'],
                                entry_price=dex_pos['entryPrice'],
                                mark_price=dex_pos['markPrice'],
                                unrealized_pnl=dex_pos.get('unrealizedPnl', 0),
                                realized_pnl=dex_pos.get('realizedPnl', 0),
                                liquidation_price=dex_pos.get('liquidationPrice'),
                                margin=dex_pos.get('margin', 0),
                                leverage=dex_pos.get('leverage', 1),
                                status=PositionStatus.OPEN,
                                opened_at=datetime.utcnow()
                            )
                            session.add(position)
                        
                        synced_count += 1
                
                # Close positions not in DEX response
                await self._close_stale_positions(session, account_id, dex, dex_positions)
                
                await session.commit()
                return synced_count
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Position sync failed: {e}")
                raise
    
    async def calculate_metrics(self,
                               account_id: int,
                               dex: Optional[str] = None,
                               period_days: int = 30) -> PositionMetrics:
        """Calculate position metrics for an account."""
        async with (self.session or get_session()) as session:
            # Get positions for period
            since_date = datetime.utcnow() - timedelta(days=period_days)
            
            query = select(Position).join(DexAccount).where(
                and_(
                    DexAccount.account_id == account_id,
                    Position.created_at >= since_date
                )
            )
            
            if dex:
                query = query.where(DexAccount.dex_name == dex)
            
            result = await session.execute(query)
            positions = result.scalars().all()
            
            metrics = PositionMetrics()
            metrics.total_positions = len(positions)
            
            winning_positions = []
            losing_positions = []
            
            for pos in positions:
                if pos.status == PositionStatus.OPEN:
                    metrics.open_positions += 1
                    metrics.total_unrealized_pnl += float(pos.unrealized_pnl) if pos.unrealized_pnl else 0
                    metrics.total_margin += float(pos.margin) if pos.margin else 0
                    metrics.total_value += float(pos.quantity) * float(pos.mark_price) if pos.mark_price else 0
                
                metrics.total_realized_pnl += float(pos.realized_pnl) if pos.realized_pnl else 0
                
                if pos.status == PositionStatus.CLOSED:
                    realized_pnl_float = float(pos.realized_pnl) if pos.realized_pnl else 0
                    if realized_pnl_float > 0:
                        winning_positions.append(realized_pnl_float)
                    elif realized_pnl_float < 0:
                        losing_positions.append(abs(realized_pnl_float))
            
            # Calculate win rate and averages
            if winning_positions or losing_positions:
                total_closed = len(winning_positions) + len(losing_positions)
                metrics.win_rate = len(winning_positions) / total_closed if total_closed > 0 else 0
                
                if winning_positions:
                    metrics.avg_win = sum(winning_positions) / len(winning_positions)
                
                if losing_positions:
                    metrics.avg_loss = sum(losing_positions) / len(losing_positions)
                
                # Profit factor
                total_wins = sum(winning_positions) if winning_positions else 0
                total_losses = sum(losing_positions) if losing_positions else 1
                metrics.profit_factor = total_wins / total_losses if total_losses > 0 else total_wins
            
            # Calculate max drawdown
            metrics.max_drawdown = await self._calculate_max_drawdown(session, account_id, dex, since_date)
            
            return metrics
    
    async def check_liquidation_risk(self,
                                    account_id: int,
                                    dex: str) -> List[Dict[str, Any]]:
        """Check positions at risk of liquidation."""
        positions = await self.get_all_positions(account_id, dex, PositionStatus.OPEN)
        
        at_risk = []
        for pos in positions:
            if pos.liquidation_price:
                # Calculate distance to liquidation
                if pos.side == PositionSide.LONG:
                    distance_pct = ((float(pos.mark_price) - float(pos.liquidation_price)) / float(pos.mark_price)) * 100
                else:
                    distance_pct = ((float(pos.liquidation_price) - float(pos.mark_price)) / float(pos.mark_price)) * 100
                
                if distance_pct < 10:  # Within 10% of liquidation
                    at_risk.append({
                        'symbol': pos.symbol,
                        'side': pos.side.value,
                        'size': float(pos.quantity),
                        'mark_price': float(pos.mark_price) if pos.mark_price else 0,
                        'liquidation_price': float(pos.liquidation_price) if pos.liquidation_price else 0,
                        'distance_pct': distance_pct,
                        'risk_level': 'HIGH' if distance_pct < 5 else 'MEDIUM'
                    })
        
        return at_risk
    
    def _calculate_unrealized_pnl(self, position: Position) -> float:
        """Calculate unrealized PnL for a position."""
        mark = float(position.mark_price) if position.mark_price else 0
        entry = float(position.entry_price) if position.entry_price else 0
        qty = float(position.quantity) if position.quantity else 0
        
        if position.side == PositionSide.LONG:
            return (mark - entry) * qty
        else:
            return (entry - mark) * qty
    
    def _to_position_info(self, position: Position, dex: str, account_name: str = "") -> PositionInfo:
        """Convert database position to PositionInfo."""
        return PositionInfo(
            id=position.id,
            symbol=position.symbol,
            side=position.side,
            size=float(position.quantity),
            entry_price=float(position.entry_price),
            mark_price=float(position.mark_price) if position.mark_price else 0,
            liquidation_price=float(position.liquidation_price) if position.liquidation_price else None,
            unrealized_pnl=float(position.unrealized_pnl) if position.unrealized_pnl else 0,
            realized_pnl=float(position.realized_pnl) if position.realized_pnl else 0,
            margin=float(position.margin) if position.margin else 0,
            leverage=position.leverage or 1,
            status=position.status,
            created_at=position.created_at,
            updated_at=position.updated_at,
            dex=dex,
            account_name=account_name
        )
    
    async def _get_dex_account(self, session: AsyncSession, account_id: int, dex: str) -> DexAccount:
        """Get DEX account."""
        result = await session.execute(
            select(DexAccount).where(
                and_(
                    DexAccount.account_id == account_id,
                    DexAccount.dex_name == dex,
                    DexAccount.is_active == True
                )
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            raise ValueError(f"No active account found for {dex}")
        return account
    
    async def _get_credentials(self, session: AsyncSession, dex_account_id: int) -> Dict[str, str]:
        """Get credentials for a DEX account."""
        # Simplified - would decrypt actual credentials
        return {}
    
    async def _close_stale_positions(self, 
                                    session: AsyncSession,
                                    account_id: int,
                                    dex: str,
                                    active_positions: List[Dict]) -> None:
        """Close positions that are no longer active on DEX."""
        active_symbols = {pos['symbol'] for pos in active_positions}
        
        result = await session.execute(
            select(Position).join(DexAccount).where(
                and_(
                    DexAccount.account_id == account_id,
                    DexAccount.dex_name == dex,
                    Position.status == PositionStatus.OPEN
                )
            )
        )
        
        for position in result.scalars():
            if position.symbol not in active_symbols:
                position.status = PositionStatus.CLOSED
                position.closed_at = datetime.utcnow()
                position.unrealized_pnl = 0
    
    async def _calculate_max_drawdown(self,
                                     session: AsyncSession,
                                     account_id: int,
                                     dex: Optional[str],
                                     since_date: datetime) -> float:
        """Calculate maximum drawdown for the period."""
        # Get position history
        query = select(PositionHistory).join(Position).join(DexAccount).where(
            and_(
                DexAccount.account_id == account_id,
                PositionHistory.created_at >= since_date
            )
        )
        
        if dex:
            query = query.where(DexAccount.dex_name == dex)
        
        query = query.order_by(PositionHistory.created_at)
        
        result = await session.execute(query)
        history = result.scalars().all()
        
        if not history:
            return 0.0
        
        # Calculate cumulative PnL
        cumulative_pnl = []
        running_total = 0
        
        for entry in history:
            running_total += entry.realized_pnl + entry.unrealized_pnl
            cumulative_pnl.append(running_total)
        
        # Find maximum drawdown
        max_drawdown = 0
        peak = cumulative_pnl[0]
        
        for value in cumulative_pnl:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)
        
        return max_drawdown * 100  # Return as percentage