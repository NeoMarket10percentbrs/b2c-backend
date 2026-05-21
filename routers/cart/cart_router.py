from uuid import UUID
from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from services.b2b import get_b2b_client
from core.database import get_db
from core.dependencies import get_cart_identity, get_current_buyer
from models.buyer import Buyer
from schemas.cart import (
    CartItemAddRequest, CartItemUpdateRequest,
    CartResponse, CartValidationResponse,
)
from services import cart_service


cart_router = APIRouter(prefix="/cart", tags=["Cart"])


@cart_router.get("", response_model=CartResponse)
async def get_cart(
    response: Response,
    identity: dict = Depends(get_cart_identity),
    db: AsyncSession = Depends(get_db)
):
    cart = await cart_service.get_or_create_cart(
        db, identity.get("buyer_id"), identity.get("session_id")
    )
    if identity.get("buyer_id") is None and identity.get("session_id") is None:
        response.headers["X-Session-Id"] = str(cart.session_id)
    return await cart_service.build_cart_response(cart, get_b2b_client())


@cart_router.post("/items", response_model=CartResponse)
async def add_to_cart(
    response: Response,
    payload: CartItemAddRequest, identity: dict = Depends(get_cart_identity),
    db: AsyncSession = Depends(get_db)
):
    cart = await cart_service.add_item(
        db, identity.get("buyer_id"),
        identity.get("session_id"),
        payload.sku_id, payload.quantity,
        get_b2b_client()
    )
    if identity.get("buyer_id") is None and identity.get("session_id") is None:
        response.headers["X-Session-Id"] = str(cart.session_id)
    return await cart_service.build_cart_response(cart, get_b2b_client())


@cart_router.patch("/items/{sku_id}", response_model=CartResponse)
async def update_cart_item(
    sku_id: UUID, payload: CartItemUpdateRequest,
    identity: dict = Depends(get_cart_identity),
    db: AsyncSession = Depends(get_db)
):
    cart = await cart_service.update_item(
        db, identity.get("buyer_id"),
        identity.get("session_id"),
        sku_id, payload.quantity,
        get_b2b_client()
    )
    return await cart_service.build_cart_response(cart, get_b2b_client())


@cart_router.delete("/items/{sku_id}", response_model=CartResponse)
async def remove_cart_item(
    sku_id: UUID,
    identity: dict = Depends(get_cart_identity),
    db: AsyncSession = Depends(get_db)
):
    cart = await cart_service.remove_item(
        db, identity.get("buyer_id"),
        identity.get("session_id"),
        sku_id
    )
    return await cart_service.build_cart_response(cart, get_b2b_client())


@cart_router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_cart(
    identity: dict = Depends(get_cart_identity),
    db: AsyncSession = Depends(get_db)
):
    await cart_service.clear_cart(
        db, identity.get("buyer_id"), identity.get("session_id")
    )
    return None


@cart_router.post("/validate", response_model=CartValidationResponse)
async def validate_cart(
    identity: dict = Depends(get_cart_identity),
    db: AsyncSession = Depends(get_db),
):
    cart = await cart_service.get_or_create_cart(
        db, identity.get("buyer_id"), identity.get("session_id")
    )
    return await cart_service.validate_cart(cart, get_b2b_client())


@cart_router.post("/merge", response_model=CartResponse)
async def merge_cart(
    buyer: Buyer = Depends(get_current_buyer),
    x_session_id: str = Header(alias="X-Session-Id"),
    db: AsyncSession = Depends(get_db)
):
    await cart_service.merge_guest_cart(db, buyer.id, x_session_id)
    cart = await cart_service.get_or_create_cart(db, buyer.id, None)
    return await cart_service.build_cart_response(cart, get_b2b_client())
