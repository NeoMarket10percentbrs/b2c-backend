from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from .b2b import B2BClient, B2BNotFoundError
from models.cart import Cart
from models.cart_item import CartItem
from schemas.cart import (
    CartItemResponse, CartResponse,
    CartValidationIssue, CartValidationResponse,
)


async def get_or_create_cart(db: AsyncSession, buyer_id: UUID) -> Cart:
    result = await db.execute(
        select(Cart)
        .where(Cart.buyer_id == buyer_id)
        .options(selectinload(Cart.items))
    )
    cart = result.scalar_one_or_none()
    if cart is None:
        cart = Cart(buyer_id=buyer_id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart, attribute_names=["items"])
    return cart


async def add_item(
    db: AsyncSession, buyer_id: UUID,
    sku_id: UUID, quantity: int, b2b: B2BClient
) -> Cart:
    try:
        sku = await b2b.get_sku(sku_id)
    except B2BNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="SKU не найден"
        )

    cart = await get_or_create_cart(db, buyer_id)

    existing = next((i for i in cart.items if i.sku_id == sku_id), None)
    new_qty = (existing.quantity if existing else 0) + quantity

    if sku.get("stock_quantity", 0) < new_qty:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Недостаточно товара. Доступно: {sku.get('stock_quantity', 0)}",
        )

    if existing:
        existing.quantity = new_qty
    else:
        db.add(CartItem(cart_id=cart.id, sku_id=sku_id, quantity=quantity))

    await db.commit()
    await db.refresh(cart, attribute_names=["items"])
    return cart


async def update_item(
    db: AsyncSession, buyer_id: UUID, item_id: UUID,
    quantity: int, b2b: B2BClient
) -> Cart:
    cart = await get_or_create_cart(db, buyer_id)
    item = next((i for i in cart.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Позиция корзины не найдена",
        )

    try:
        sku = await b2b.get_sku(item.sku_id)
    except B2BNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SKU больше не доступен в каталоге",
        )

    if sku.get("stock_quantity", 0) < quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Недостаточно товара. Доступно: {sku.get('stock_quantity', 0)}",
        )

    item.quantity = quantity
    await db.commit()
    await db.refresh(cart, attribute_names=["items"])
    return cart


async def remove_item(db: AsyncSession, buyer_id: UUID, item_id: UUID) -> Cart:
    cart = await get_or_create_cart(db, buyer_id)
    item = next((i for i in cart.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Позиция корзины не найдена",
        )
    await db.delete(item)
    await db.commit()
    await db.refresh(cart, attribute_names=["items"])
    return cart


async def clear_cart(db: AsyncSession, buyer_id: UUID) -> Cart:
    cart = await get_or_create_cart(db, buyer_id)
    for item in list(cart.items):
        await db.delete(item)
    await db.commit()
    await db.refresh(cart, attribute_names=["items"])
    return cart


async def build_cart_response(cart: Cart, b2b: B2BClient) -> CartResponse:
    sku_ids = [item.sku_id for item in cart.items]
    skus = await b2b.get_skus_bulk(sku_ids) if sku_ids else {}

    items_resp: list[CartItemResponse] = []
    for item in cart.items:
        sku = skus.get(item.sku_id)
        if sku is None:
            items_resp.append(
                CartItemResponse(
                    id=item.id,
                    sku_id=item.sku_id,
                    quantity=item.quantity,
                    is_available=False,
                )
            )
            continue
        stock = int(sku.get("stock_quantity", 0))
        items_resp.append(
            CartItemResponse(
                id=item.id,
                sku_id=item.sku_id,
                quantity=item.quantity,
                product_id=sku.get("product_id"),
                sku_name=sku.get("name"),
                sku_price=sku.get("price"),
                image_url=sku.get("image_url"),
                stock_quantity=stock,
                is_available=stock >= item.quantity,
            )
        )

    return CartResponse(id=cart.id, items=items_resp)


async def validate_cart(cart: Cart, b2b: B2BClient) -> CartValidationResponse:
    # валидируем что всё ещё в наличии
    sku_ids = [item.sku_id for item in cart.items]
    skus = await b2b.get_skus_bulk(sku_ids) if sku_ids else {}

    issues: list[CartValidationIssue] = []
    for item in cart.items:
        sku = skus.get(item.sku_id)
        if sku is None:
            issues.append(
                CartValidationIssue(
                    sku_id=item.sku_id,
                    reason="not_found",
                    requested=item.quantity,
                )
            )
            continue
        stock = int(sku.get("stock_quantity", 0))
        if stock <= 0:
            issues.append(
                CartValidationIssue(
                    sku_id=item.sku_id,
                    reason="out_of_stock",
                    requested=item.quantity,
                    available=stock,
                )
            )
        elif stock < item.quantity:
            issues.append(
                CartValidationIssue(
                    sku_id=item.sku_id,
                    reason="insufficient_stock",
                    requested=item.quantity,
                    available=stock,
                )
            )

    return CartValidationResponse(is_valid=not issues, issues=issues)
