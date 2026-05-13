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


async def get_or_create_cart(
    db: AsyncSession,
    buyer_id: UUID | None,
    session_id: str | None,
) -> Cart:
    if buyer_id is None and session_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MISSING_CART_IDENTITY",
        )

    filters = []
    if buyer_id is not None:
        filters.append(Cart.buyer_id == buyer_id)
    if session_id is not None:
        filters.append(Cart.session_id == session_id)

    result = await db.execute(
        select(Cart)
        .where(*filters)
        .options(selectinload(Cart.items))
    )
    cart = result.scalar_one_or_none()
    if cart is None:
        cart = Cart(buyer_id=buyer_id, session_id=session_id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart, attribute_names=["items"])
    return cart


async def add_item(
    db: AsyncSession, buyer_id: UUID | None, session_id: str | None,
    sku_id: UUID, quantity: int, b2b: B2BClient
) -> Cart:
    if quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Количество должно быть больше нуля",
        )

    try:
        sku = await b2b.get_sku(sku_id)
    except B2BNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="SKU не найден"
        )

    cart = await get_or_create_cart(db, buyer_id, session_id)

    existing = next((i for i in cart.items if i.sku_id == sku_id), None)
    new_qty = (existing.quantity if existing else 0) + quantity

    stock = int(sku.get("stock_quantity") or 0)
    if stock < new_qty:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Недостаточно товара. Доступно: {stock}",
        )

    if existing:
        existing.quantity = new_qty
        if existing.product_id is None:
            existing.product_id = UUID(sku["product_id"])
    else:
        db.add(
            CartItem(
                cart_id=cart.id,
                sku_id=sku_id,
                product_id=UUID(sku["product_id"]),
                quantity=quantity,
            )
        )

    await db.commit()
    await db.refresh(cart, attribute_names=["items"])
    return cart


async def update_item(
    db: AsyncSession, buyer_id: UUID | None, session_id: str | None, item_id: UUID,
    quantity: int, b2b: B2BClient
) -> Cart:
    if quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Количество должно быть больше нуля",
        )

    cart = await get_or_create_cart(db, buyer_id, session_id)
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

    stock = int(sku.get("stock_quantity") or 0)
    if stock < quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Недостаточно товара. Доступно: {stock}",
        )

    item.quantity = quantity
    await db.commit()
    await db.refresh(cart, attribute_names=["items"])
    return cart


async def remove_item(
    db: AsyncSession, buyer_id: UUID | None, session_id: str | None, item_id: UUID
) -> Cart:
    cart = await get_or_create_cart(db, buyer_id, session_id)
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


async def clear_cart(db: AsyncSession, buyer_id: UUID | None, session_id: str | None) -> Cart:
    cart = await get_or_create_cart(db, buyer_id, session_id)
    for item in list(cart.items):
        await db.delete(item)
    await db.commit()
    await db.refresh(cart, attribute_names=["items"])
    return cart


async def build_cart_response(cart: Cart, b2b: B2BClient) -> CartResponse:
    product_ids = [item.product_id for item in cart.items]
    products = await b2b.get_products_by_ids(product_ids) if product_ids else {}

    sku_index: dict[UUID, dict] = {}
    for product in products.values():
        for sku in product.get("skus", []) or []:
            sku_id = sku.get("id")
            if sku_id:
                try:
                    sku_index[UUID(sku_id)] = sku
                except ValueError:
                    continue

    items_resp: list[CartItemResponse] = []
    for item in cart.items:
        sku = sku_index.get(item.sku_id)
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
                product_id=item.product_id,
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
    product_ids = [item.product_id for item in cart.items]
    products = await b2b.get_products_by_ids(product_ids) if product_ids else {}

    sku_index: dict[UUID, dict] = {}
    for product in products.values():
        for sku in product.get("skus", []) or []:
            sku_id = sku.get("id")
            if sku_id:
                try:
                    sku_index[UUID(sku_id)] = sku
                except ValueError:
                    continue

    issues: list[CartValidationIssue] = []
    for item in cart.items:
        sku = sku_index.get(item.sku_id)
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


async def merge_guest_cart(
    db: AsyncSession,
    buyer_id: UUID,
    session_id: str,
) -> None:
    guest_cart_result = await db.execute(
        select(Cart)
        .where(Cart.session_id == session_id)
        .options(selectinload(Cart.items))
    )
    guest_cart = guest_cart_result.scalar_one_or_none()
    if guest_cart is None:
        return

    buyer_cart = await get_or_create_cart(db, buyer_id, None)

    buyer_items_by_sku = {item.sku_id: item for item in buyer_cart.items}
    for guest_item in guest_cart.items:
        existing = buyer_items_by_sku.get(guest_item.sku_id)
        if existing:
            existing.quantity = max(existing.quantity, guest_item.quantity)
            await db.delete(guest_item)
        else:
            guest_item.cart_id = buyer_cart.id

    await db.delete(guest_cart)
    await db.commit()
