from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from services.b2b import get_b2b_client
from core.database import get_db
from core.dependencies import get_current_buyer
from models.buyer import Buyer
from schemas.cart import (
    CartItemAdd, CartItemUpdate,
    CartResponse, CartValidationResponse,
)
from services import cart_service


cart_router = APIRouter(prefix="/cart", tags=["cart"])


@cart_router.get("", response_model=CartResponse)
async def get_cart(
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    cart = await cart_service.get_or_create_cart(db, buyer.id)
    return await cart_service.build_cart_response(cart, get_b2b_client())


@cart_router.post("/items", response_model=CartResponse, status_code=status.HTTP_201_CREATED)
async def add_to_cart(
    payload: CartItemAdd, buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    cart = await cart_service.add_item(
        db, buyer.id, payload.sku_id, payload.quantity, get_b2b_client()
    )
    return await cart_service.build_cart_response(cart, get_b2b_client())


@cart_router.patch("/items/{item_id}", response_model=CartResponse)
async def update_cart_item(
    item_id: UUID, payload: CartItemUpdate,
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    cart = await cart_service.update_item(
        db, buyer.id, item_id, payload.quantity, get_b2b_client()
    )
    return await cart_service.build_cart_response(cart, get_b2b_client())


@cart_router.delete("/items/{item_id}", response_model=CartResponse)
async def remove_cart_item(
    item_id: UUID,
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    cart = await cart_service.remove_item(db, buyer.id, item_id)
    return await cart_service.build_cart_response(cart, get_b2b_client())


@cart_router.delete("", response_model=CartResponse)
async def clear_cart(
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    cart = await cart_service.clear_cart(db, buyer.id)
    return await cart_service.build_cart_response(cart, get_b2b_client())


@cart_router.get("/validate", response_model=CartValidationResponse)
async def validate_cart(
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    cart = await cart_service.get_or_create_cart(db, buyer.id)
    return await cart_service.validate_cart(cart, get_b2b_client())
