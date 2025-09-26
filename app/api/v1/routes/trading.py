"""
Trading API routes.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.core.auth import get_current_active_user
from app.api.v1.schemas.trading import (
    OrderRequest,
    OrderResponse,
    OrderModifyRequest,
    PositionResponse,
    TradeResponse
)
from database.session import get_session
from models.accounts import Account
from models.orders import OrderStatus
from services.order_executor import OrderExecutor
from services.position_tracker import PositionTracker
from app.core.exceptions import (
    OrderNotFoundError,
    InsufficientBalanceError,
    OrderExecutionError
)

router = APIRouter(prefix="/trading", tags=["trading"])


@router.post("/orders", response_model=OrderResponse)
async def place_order(
    order: OrderRequest,
    current_user: Account = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """Place a new order."""
    try:
        executor = OrderExecutor(session=session)
        
        result = await executor.place_order(
            account_id=current_user.id,
            dex=order.dex,
            request=order
        )
        
        return OrderResponse(
            id=result.order_id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price,
            status=result.status,
            executed_quantity=result.executed_quantity,
            executed_price=result.executed_price,
            fee=result.fee
        )
        
    except InsufficientBalanceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except OrderExecutionError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/orders/{order_id}")
async def cancel_order(
    order_id: int,
    current_user: Account = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """Cancel an order."""
    try:
        executor = OrderExecutor(session=session)
        
        success = await executor.cancel_order(
            account_id=current_user.id,
            order_id=order_id
        )
        
        if success:
            return {"message": f"Order {order_id} cancelled successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to cancel order"
            )
            
    except OrderNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.patch("/orders/{order_id}", response_model=OrderResponse)
async def modify_order(
    order_id: int,
    modifications: OrderModifyRequest,
    current_user: Account = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """Modify an existing order."""
    try:
        executor = OrderExecutor(session=session)
        
        result = await executor.modify_order(
            account_id=current_user.id,
            order_id=order_id,
            modifications=modifications.dict(exclude_unset=True)
        )
        
        return OrderResponse(
            id=result.order_id,
            symbol=result.symbol,
            side=result.side,
            order_type=result.order_type,
            quantity=result.quantity,
            price=result.price,
            status=result.status,
            executed_quantity=result.executed_quantity,
            executed_price=result.executed_price,
            fee=result.fee
        )
        
    except OrderNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except OrderExecutionError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/orders", response_model=List[OrderResponse])
async def get_orders(
    dex: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    status: Optional[OrderStatus] = Query(None),
    limit: int = Query(100, le=500),
    current_user: Account = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """Get orders with optional filters."""
    executor = OrderExecutor(session=session)
    
    orders = await executor.get_orders(
        account_id=current_user.id,
        dex=dex,
        symbol=symbol,
        status=status,
        limit=limit
    )
    
    return [
        OrderResponse(
            id=order.id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=float(order.quantity),
            price=float(order.price) if order.price else None,
            status=order.status,
            executed_quantity=float(order.executed_quantity) if order.executed_quantity else 0,
            executed_price=float(order.executed_price) if order.executed_price else None,
            fee=float(order.total_fees) if order.total_fees else 0
        )
        for order in orders
    ]


@router.get("/orders/active", response_model=List[OrderResponse])
async def get_active_orders(
    dex: Optional[str] = Query(None),
    current_user: Account = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """Get all active orders."""
    executor = OrderExecutor(session=session)
    
    orders = await executor.get_active_orders(
        account_id=current_user.id,
        dex=dex
    )
    
    return [
        OrderResponse(
            id=order.id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=float(order.quantity),
            price=float(order.price) if order.price else None,
            status=order.status,
            executed_quantity=float(order.executed_quantity) if order.executed_quantity else 0,
            executed_price=float(order.executed_price) if order.executed_price else None,
            fee=float(order.total_fees) if order.total_fees else 0
        )
        for order in orders
    ]


@router.delete("/orders")
async def cancel_all_orders(
    dex: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    current_user: Account = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """Cancel all orders with optional filters."""
    executor = OrderExecutor(session=session)
    
    count = await executor.cancel_all_orders(
        account_id=current_user.id,
        dex=dex,
        symbol=symbol
    )
    
    return {"message": f"Cancelled {count} orders"}


@router.get("/positions", response_model=List[PositionResponse])
async def get_positions(
    dex: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    current_user: Account = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """Get all positions."""
    tracker = PositionTracker(session=session)
    
    positions = await tracker.get_all_positions(
        account_id=current_user.id,
        dex=dex,
        symbol=symbol
    )
    
    return [
        PositionResponse(
            id=pos.id,
            symbol=pos.symbol,
            side=pos.side,
            size=pos.size,
            entry_price=pos.entry_price,
            mark_price=pos.mark_price,
            liquidation_price=pos.liquidation_price,
            unrealized_pnl=pos.unrealized_pnl,
            realized_pnl=pos.realized_pnl,
            margin=pos.margin,
            leverage=pos.leverage,
            status=pos.status,
            dex=pos.dex,
            account_name=pos.account_name
        )
        for pos in positions
    ]


@router.get("/positions/{position_id}", response_model=PositionResponse)
async def get_position(
    position_id: int,
    current_user: Account = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """Get a specific position."""
    tracker = PositionTracker(session=session)
    
    try:
        position = await tracker.get_position(
            account_id=current_user.id,
            position_id=position_id
        )
        
        return PositionResponse(
            id=position.id,
            symbol=position.symbol,
            side=position.side,
            size=position.size,
            entry_price=position.entry_price,
            mark_price=position.mark_price,
            liquidation_price=position.liquidation_price,
            unrealized_pnl=position.unrealized_pnl,
            realized_pnl=position.realized_pnl,
            margin=position.margin,
            leverage=position.leverage,
            status=position.status,
            dex=position.dex,
            account_name=position.account_name
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Position not found"
        )


@router.post("/positions/{position_id}/close")
async def close_position(
    position_id: int,
    price: Optional[float] = Query(None),
    current_user: Account = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """Close a position."""
    tracker = PositionTracker(session=session)
    
    try:
        result = await tracker.close_position(
            account_id=current_user.id,
            position_id=position_id,
            price=price
        )
        
        return {
            "message": f"Position {position_id} closed successfully",
            "realized_pnl": result.realized_pnl
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/positions/sync")
async def sync_positions(
    dex: str,
    current_user: Account = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """Sync positions with DEX."""
    tracker = PositionTracker(session=session)
    
    try:
        synced = await tracker.sync_positions(
            account_id=current_user.id,
            dex=dex
        )
        
        return {"message": f"Synced {synced} positions from {dex}"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )