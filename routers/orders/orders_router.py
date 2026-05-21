from uuid import UUID
from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from services.b2b import get_b2b_client
from core.database import get_db
from core.dependencies import get_current_buyer
from models.buyer import Buyer
from schemas.order import (
    OrderCreateRequest, PaginatedOrders,
    OrderResponse, OrderShortResponse,
    OrderCancelRequest
)
from services import order_service


order_router = APIRouter(prefix="/orders", tags=["Orders"])


@order_router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreateRequest,
    idempotency_key: UUID = Header(alias="Idempotency-Key"),
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db)
):
    order = await order_service.create_order(
        db, buyer.id, idempotency_key, payload, get_b2b_client()
    )
    return order


@order_router.get("", response_model=PaginatedOrders)
async def list_orders(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db)
):
    total, orders = await order_service.list_orders(db, buyer.id, limit, offset, status)
    items = [OrderShortResponse.model_validate(o) for o in orders]
    return PaginatedOrders(total_count=total, limit=limit, offset=offset, items=items)


@order_router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID, buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db)
):
    return await order_service.get_order(db, buyer.id, order_id)


@order_router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: UUID, payload: OrderCancelRequest | None = None,
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db)
):
    return await order_service.cancel_order(
        db, buyer.id, order_id, payload, get_b2b_client()
    )
