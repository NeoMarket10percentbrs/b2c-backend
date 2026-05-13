from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from services.b2b import get_b2b_client
from core.database import get_db
from core.dependencies import get_current_buyer
from models.buyer import Buyer
from schemas.order import (
    OrderCreate, OrderListResponse,
    OrderResponse, OrderShortResponse
)
from services import order_service


order_router = APIRouter(prefix="/orders", tags=["orders"])


@order_router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate,
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    order = await order_service.create_order(
        db, buyer.id, payload.idempotency_key, payload.address_id,
        payload.comment, get_b2b_client()
    )
    return order


@order_router.get("", response_model=OrderListResponse)
async def list_orders(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    total, orders = await order_service.list_orders(db, buyer.id, page, size)
    items = [OrderShortResponse.model_validate(o) for o in orders]
    return OrderListResponse(total=total, items=items)


@order_router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    return await order_service.get_order(db, buyer.id, order_id)


@order_router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: UUID,
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    return await order_service.cancel_order(
        db, buyer.id, order_id, get_b2b_client()
    )
