from uuid import UUID, uuid4
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from .b2b import B2BClient, B2BNotFoundError
from models.cart import Cart
from models.cart_item import CartItem as CartItemModel
from schemas.cart import (
    CartItem, CartResponse, CartValidationIssue, CartValidationResponse
)


def _error_detail(code: str, message: str) -> dict:
    return {"code": code, "message": message}


async def get_or_create_cart(db: AsyncSession, buyer_id: UUID | None, session_id: str | None) -> Cart:
    if buyer_id is None and session_id is None:
        session_id = str(uuid4())

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
            detail=_error_detail("INVALID_REQUEST", "Quantity must be greater than zero"),
        )

    try:
        sku = await b2b.get_sku(sku_id)
    except B2BNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error_detail("SKU_NOT_FOUND", "SKU not found"),
        )

    cart = await get_or_create_cart(db, buyer_id, session_id)

    existing = next((i for i in cart.items if i.sku_id == sku_id), None)
    new_qty = (existing.quantity if existing else 0) + quantity

    stock = int(sku.get("stock_quantity") or 0)
    if stock < new_qty:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_error_detail(
                "OUT_OF_STOCK",
                f"Insufficient stock. Available: {stock}",
            ),
        )

    if existing:
        existing.quantity = new_qty
        if existing.product_id is None:
            existing.product_id = UUID(sku["product_id"])
    else:
        db.add(
            CartItemModel(
                cart_id=cart.id,
                sku_id=sku_id,
                product_id=UUID(sku["product_id"]),
                quantity=quantity
            )
        )

    await db.commit()
    await db.refresh(cart, attribute_names=["items"])
    return cart


async def update_item(
    db: AsyncSession, buyer_id: UUID | None, session_id: str | None,
    sku_id: UUID, quantity: int, b2b: B2BClient
) -> Cart:
    if quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail("INVALID_REQUEST", "Quantity must be greater than zero"),
        )

    cart = await get_or_create_cart(db, buyer_id, session_id)
    item = next((i for i in cart.items if i.sku_id == sku_id), None)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error_detail("CART_ITEM_NOT_FOUND", "Cart item not found"),
        )

    try:
        sku = await b2b.get_sku(item.sku_id)
    except B2BNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_error_detail("SKU_UNAVAILABLE", "SKU is no longer available in catalog"),
        )

    stock = int(sku.get("stock_quantity") or 0)
    if stock < quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_error_detail(
                "OUT_OF_STOCK",
                f"Insufficient stock. Available: {stock}",
            ),
        )

    item.quantity = quantity
    await db.commit()
    await db.refresh(cart, attribute_names=["items"])
    return cart


async def remove_item(
    db: AsyncSession, buyer_id: UUID | None, session_id: str | None, sku_id: UUID
) -> Cart:
    cart = await get_or_create_cart(db, buyer_id, session_id)
    item = next((i for i in cart.items if i.sku_id == sku_id), None)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error_detail("CART_ITEM_NOT_FOUND", "Cart item not found"),
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

    items_resp: list[CartItem] = []
    subtotal = 0
    items_count = 0
    is_valid = True
    for item in cart.items:
        items_count += item.quantity
        sku = sku_index.get(item.sku_id)
        if sku is None:
            items_resp.append(
                CartItem(
                    sku_id=item.sku_id,
                    quantity=item.quantity,
                    is_available=False,
                    line_total=0,
                    unit_price=0,
                )
            )
            is_valid = False
            continue
        stock = int(sku.get("stock_quantity", 0))
        unit_price = int(sku.get("price") or 0)
        available = stock >= item.quantity
        line_total = unit_price * item.quantity if available else 0
        if not available:
            is_valid = False
        
        subtotal += line_total

        items_resp.append(
            CartItem(
                sku_id=item.sku_id,
                quantity=item.quantity,
                product_id=item.product_id,
                name=sku.get("product_title") or sku.get("name"),
                sku_code=sku.get("sku_code"),
                unit_price=unit_price,
                unit_price_at_add=None,
                line_total=line_total,
                available_quantity=stock,
                is_available=available,
                image=None,
            )
        )

    return CartResponse(
        id=cart.id,
        items=items_resp,
        items_count=items_count,
        subtotal=subtotal,
        is_valid=is_valid,
        updated_at=getattr(cart, "updated_at", None),
    )


async def validate_cart(cart: Cart, b2b: B2BClient) -> CartValidationResponse:
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
                    type="PRODUCT_DELETED",
                    message="Product was removed from catalog",
                )
            )
            continue
        stock = int(sku.get("stock_quantity", 0))
        if stock <= 0:
            issues.append(
                CartValidationIssue(
                    sku_id=item.sku_id,
                    type="OUT_OF_STOCK",
                    message="Product is out of stock",
                    old_value=item.quantity,
                    new_value=stock,
                )
            )
        elif stock < item.quantity:
            issues.append(
                CartValidationIssue(
                    sku_id=item.sku_id,
                    type="QUANTITY_REDUCED",
                    message="Available quantity is lower",
                    old_value=item.quantity,
                    new_value=stock,
                )
            )

    cart_response = await build_cart_response(cart, b2b)
    return CartValidationResponse(is_valid=not issues, cart=cart_response, issues=issues)


async def merge_guest_cart(db: AsyncSession, buyer_id: UUID, session_id: str) -> None:
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
