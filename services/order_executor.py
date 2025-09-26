"""
Enhanced order execution service with advanced features.
"""
from typing import List, Dict, Optional, Any, Union
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, update

from models.orders import Order, Trade, OrderSide, OrderType, OrderStatus, TimeInForce
from models.accounts import DexAccount
from database.session import get_session
from connectors.factory import ConnectorFactory
from app.core.exceptions import (
    OrderNotFoundError,
    InsufficientBalanceError,
    OrderExecutionError,
    ConnectorNotFoundError
)

logger = logging.getLogger(__name__)


@dataclass
class OrderRequest:
    """Order request parameters."""
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    reduce_only: bool = False
    post_only: bool = False
    client_order_id: Optional[str] = None
    extra_params: Optional[Dict[str, Any]] = None


@dataclass
class OrderResult:
    """Order execution result."""
    order_id: str
    status: OrderStatus
    filled_qty: float = 0.0
    avg_price: float = 0.0
    fee: float = 0.0
    timestamp: datetime = None
    message: Optional[str] = None


class OrderExecutor:
    """Advanced order execution service."""
    
    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session
        self.connector_factory = ConnectorFactory()
        self._active_orders: Dict[str, Order] = {}
        self._order_locks: Dict[str, asyncio.Lock] = {}
    
    async def place_order(self,
                         account_id: int,
                         dex: str,
                         request: OrderRequest) -> OrderResult:
        """Place a new order."""
        async with (self.session or get_session()) as session:
            try:
                # Get account and connector
                account = await self._get_account(session, account_id, dex)
                if not account:
                    raise OrderExecutionError(f"Account not found for {dex}")
                
                credentials = await self._get_credentials(session, account.id)
                connector = self.connector_factory.create_connector(
                    dex,
                    None,  # config will be created from kwargs
                    testnet=account.is_testnet,
                    **credentials
                )
                
                # Validate order
                await self._validate_order(account, request)
                
                # Create database order
                order = Order(
                    account_id=account.account_id,  # Main account ID
                    dex_account_id=account.id,
                    symbol=request.symbol,
                    side=request.side,
                    order_type=request.order_type,
                    quantity=request.quantity,
                    price=request.price,
                    stop_price=request.stop_price,
                    time_in_force=request.time_in_force,
                    status=OrderStatus.PENDING,
                    reduce_only=request.reduce_only,
                    post_only=request.post_only,
                    client_order_id=request.client_order_id
                )
                session.add(order)
                await session.flush()
                
                # Execute on DEX
                try:
                    dex_response = await connector.place_order({
                        'symbol': request.symbol,
                        'side': request.side.value,
                        'type': request.order_type.value,
                        'quantity': request.quantity,
                        'price': request.price,
                        'stopPrice': request.stop_price,
                        'timeInForce': request.time_in_force.value,
                        'reduceOnly': request.reduce_only,
                        'postOnly': request.post_only,
                        'clientOrderId': request.client_order_id,
                        **(request.extra_params or {})
                    })
                    
                    # Update order with DEX response
                    order.exchange_order_id = dex_response.get('orderId')
                    order.status = OrderStatus.NEW
                    order.executed_qty = dex_response.get('executedQty', 0)
                    order.avg_price = dex_response.get('avgPrice', 0)
                    
                    await session.commit()
                    
                    # Cache active order
                    self._active_orders[order.exchange_order_id] = order
                    
                    return OrderResult(
                        order_id=order.exchange_order_id,
                        status=OrderStatus.NEW,
                        filled_qty=order.executed_qty,
                        avg_price=order.avg_price,
                        timestamp=datetime.utcnow()
                    )
                    
                except Exception as e:
                    order.status = OrderStatus.REJECTED
                    order.extra_data = {'error': str(e)}
                    await session.commit()
                    raise OrderExecutionError(f"Failed to place order: {e}")
                    
            except Exception as e:
                await session.rollback()
                logger.error(f"Order placement failed: {e}")
                raise
    
    async def cancel_order(self,
                          account_id: int,
                          dex: str,
                          order_id: str) -> bool:
        """Cancel an existing order."""
        async with (self.session or get_session()) as session:
            try:
                # Get order from database
                order = await self._get_order(session, order_id)
                if not order:
                    raise OrderNotFoundError(f"Order {order_id} not found")
                
                # Get connector
                account = await session.get(DexAccount, order.dex_account_id)
                credentials = await self._get_credentials(session, account.id)
                connector = self.connector_factory.create_connector(
                    dex,
                    None,  # config will be created from kwargs
                    testnet=account.is_testnet,
                    **credentials
                )
                
                # Cancel on DEX
                result = await connector.cancel_order(order_id)
                
                # Update database
                order.status = OrderStatus.CANCELED
                order.cancelled_at = datetime.utcnow()
                await session.commit()
                
                # Remove from cache
                self._active_orders.pop(order_id, None)
                
                return result
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Order cancellation failed: {e}")
                raise OrderExecutionError(f"Failed to cancel order: {e}")
    
    async def modify_order(self,
                          account_id: int,
                          dex: str,
                          order_id: str,
                          modifications: Dict[str, Any]) -> OrderResult:
        """Modify an existing order."""
        async with (self.session or get_session()) as session:
            try:
                # Get order
                order = await self._get_order(session, order_id)
                if not order:
                    raise OrderNotFoundError(f"Order {order_id} not found")
                
                if order.status not in [OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]:
                    raise OrderExecutionError(f"Cannot modify order in status {order.status}")
                
                # Get connector
                account = await session.get(DexAccount, order.dex_account_id)
                credentials = await self._get_credentials(session, account.id)
                connector = self.connector_factory.create_connector(
                    dex,
                    None,  # config will be created from kwargs
                    testnet=account.is_testnet,
                    **credentials
                )
                
                # Modify on DEX
                dex_response = await connector.modify_order(order_id, modifications)
                
                # Update database
                if 'quantity' in modifications:
                    order.quantity = modifications['quantity']
                if 'price' in modifications:
                    order.price = modifications['price']
                if 'stopPrice' in modifications:
                    order.stop_price = modifications['stopPrice']
                
                order.updated_at = datetime.utcnow()
                await session.commit()
                
                return OrderResult(
                    order_id=order_id,
                    status=order.status,
                    timestamp=datetime.utcnow(),
                    message="Order modified successfully"
                )
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Order modification failed: {e}")
                raise
    
    async def get_orders(self,
                        account_id: int,
                        dex: Optional[str] = None,
                        status: Optional[OrderStatus] = None,
                        symbol: Optional[str] = None,
                        limit: int = 100) -> List[Order]:
        """Get orders with optional filters."""
        async with (self.session or get_session()) as session:
            query = select(Order).join(DexAccount).where(
                DexAccount.account_id == account_id
            )
            
            if dex:
                query = query.where(DexAccount.dex == dex)
            if status:
                query = query.where(Order.status == status)
            if symbol:
                query = query.where(Order.symbol == symbol)
            
            query = query.order_by(Order.created_at.desc()).limit(limit)
            
            result = await session.execute(query)
            return result.scalars().all()
    
    async def get_active_orders(self,
                               account_id: int,
                               dex: Optional[str] = None) -> List[Order]:
        """Get all active orders."""
        return await self.get_orders(
            account_id,
            dex,
            status=OrderStatus.NEW
        )
    
    async def sync_orders(self,
                         account_id: int,
                         dex: str) -> int:
        """Sync orders with DEX."""
        async with (self.session or get_session()) as session:
            try:
                # Get account and connector
                accounts = await session.execute(
                    select(DexAccount).where(
                        and_(
                            DexAccount.account_id == account_id,
                            DexAccount.dex == dex
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
                    
                    # Get orders from DEX
                    dex_orders = await connector.get_orders()
                    
                    for dex_order in dex_orders:
                        # Update or create order
                        order = await self._get_order_by_exchange_id(
                            session,
                            dex_order['orderId']
                        )
                        
                        if order:
                            # Update existing order
                            order.status = self._map_order_status(dex_order['status'])
                            order.executed_qty = dex_order.get('executedQty', 0)
                            order.avg_price = dex_order.get('avgPrice', 0)
                            order.updated_at = datetime.utcnow()
                        else:
                            # Create new order
                            order = Order(
                                dex_account_id=account.id,
                                exchange_order_id=dex_order['orderId'],
                                symbol=dex_order['symbol'],
                                side=OrderSide(dex_order['side']),
                                order_type=OrderType(dex_order['type']),
                                quantity=dex_order['quantity'],
                                price=dex_order.get('price'),
                                status=self._map_order_status(dex_order['status']),
                                executed_qty=dex_order.get('executedQty', 0),
                                avg_price=dex_order.get('avgPrice', 0)
                            )
                            session.add(order)
                        
                        synced_count += 1
                
                await session.commit()
                return synced_count
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Order sync failed: {e}")
                raise
    
    async def calculate_pnl(self,
                           order_id: str) -> Dict[str, float]:
        """Calculate PnL for an order."""
        async with (self.session or get_session()) as session:
            order = await self._get_order(session, order_id)
            if not order:
                raise OrderNotFoundError(f"Order {order_id} not found")
            
            if order.executed_qty == 0:
                return {'realized_pnl': 0.0, 'fees': 0.0}
            
            # Get trades for this order
            trades = await session.execute(
                select(Trade).where(Trade.order_id == order.id)
            )
            
            total_pnl = 0.0
            total_fees = 0.0
            
            for trade in trades.scalars():
                # Calculate based on trade direction and prices
                if order.side == OrderSide.BUY:
                    pnl = (trade.exit_price - trade.price) * trade.quantity if trade.exit_price else 0
                else:
                    pnl = (trade.price - trade.exit_price) * trade.quantity if trade.exit_price else 0
                
                total_pnl += pnl
                total_fees += trade.fee
            
            return {
                'realized_pnl': total_pnl,
                'fees': total_fees,
                'net_pnl': total_pnl - total_fees
            }
    
    async def _get_account(self, session: AsyncSession, account_id: int, dex: str) -> Optional[DexAccount]:
        """Get account from database."""
        result = await session.execute(
            select(DexAccount).where(
                and_(
                    DexAccount.account_id == account_id,
                    DexAccount.dex == dex,
                    DexAccount.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _get_credentials(self, session: AsyncSession, dex_account_id: int) -> Dict[str, str]:
        """Get credentials for a DEX account."""
        # This would decrypt and return credentials
        # Simplified for now
        return {}
    
    async def _get_order(self, session: AsyncSession, order_id: str) -> Optional[Order]:
        """Get order by exchange order ID."""
        result = await session.execute(
            select(Order).where(Order.exchange_order_id == order_id)
        )
        return result.scalar_one_or_none()
    
    async def _get_order_by_exchange_id(self, session: AsyncSession, exchange_order_id: str) -> Optional[Order]:
        """Get order by exchange order ID."""
        result = await session.execute(
            select(Order).where(Order.exchange_order_id == exchange_order_id)
        )
        return result.scalar_one_or_none()
    
    async def _validate_order(self, account: DexAccount, request: OrderRequest):
        """Validate order request."""
        # Check balance
        if request.order_type == OrderType.MARKET:
            required_balance = request.quantity * (request.price or 0)  # Estimate
        else:
            required_balance = request.quantity * request.price
        
        if account.balance < required_balance:
            raise InsufficientBalanceError(
                f"Insufficient balance. Required: {required_balance}, Available: {account.balance}"
            )
        
        # Additional validations
        if request.order_type == OrderType.LIMIT and not request.price:
            raise OrderExecutionError("Limit order requires price")
        
        if request.order_type in [OrderType.STOP, OrderType.STOP_LIMIT] and not request.stop_price:
            raise OrderExecutionError("Stop order requires stop price")
    
    def _map_order_status(self, dex_status: str) -> OrderStatus:
        """Map DEX order status to internal status."""
        status_map = {
            'NEW': OrderStatus.NEW,
            'PARTIALLY_FILLED': OrderStatus.PARTIALLY_FILLED,
            'FILLED': OrderStatus.FILLED,
            'CANCELED': OrderStatus.CANCELED,
            'REJECTED': OrderStatus.REJECTED,
            'EXPIRED': OrderStatus.EXPIRED
        }
        return status_map.get(dex_status.upper(), OrderStatus.NEW)
    
    async def batch_place_orders(self,
                                account_id: int,
                                dex: str,
                                orders: List[OrderRequest]) -> List[OrderResult]:
        """Place multiple orders in batch."""
        results = []
        for order_request in orders:
            try:
                result = await self.place_order(account_id, dex, order_request)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to place order: {e}")
                results.append(OrderResult(
                    order_id="",
                    status=OrderStatus.REJECTED,
                    message=str(e)
                ))
        return results
    
    async def cancel_all_orders(self,
                               account_id: int,
                               dex: str,
                               symbol: Optional[str] = None) -> int:
        """Cancel all orders for an account."""
        active_orders = await self.get_active_orders(account_id, dex)
        
        if symbol:
            active_orders = [o for o in active_orders if o.symbol == symbol]
        
        cancelled_count = 0
        for order in active_orders:
            try:
                await self.cancel_order(account_id, dex, order.exchange_order_id)
                cancelled_count += 1
            except Exception as e:
                logger.error(f"Failed to cancel order {order.exchange_order_id}: {e}")
        
        return cancelled_count