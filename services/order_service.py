from datetime import datetime, timezone
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from .b2b import B2BClient, B2BClientError
from models.address import Address
from models.order import Order, OrderStatus
from models.order_item import OrderItem
from services.cart_service import get_or_create_cart, validate_cart


async def create_order(
    db: AsyncSession, buyer_id: UUID,
    idempotency_key: UUID, address_id: UUID, comment: str | None,
    b2b: B2BClient) -> Order:
    existing = await db.execute(
        select(Order)
        .where(Order.idempotency_key == idempotency_key)
        .options(selectinload(Order.items), selectinload(Order.address))
    )
    if existing_order := existing.scalar_one_or_none():
        return existing_order

    cart = await get_or_create_cart(db, buyer_id, None)
    if not cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Корзина пуста"
        )

    address = await db.get(Address, address_id)
    if address is None or address.buyer_id != buyer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Адрес не найден"
        )

    validation = await validate_cart(cart, b2b)
    if not validation.is_valid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Часть товаров недоступна",
                "issues": [issue.model_dump(mode="json") for issue in validation.issues],
            },
        )

    product_ids = [item.product_id for item in cart.items]
    products = await b2b.get_products_by_ids(product_ids)
    sku_index: dict[UUID, dict] = {}
    for product in products.values():
        for sku in product.get("skus", []) or []:
            sku_id = sku.get("id")
            if sku_id:
                try:
                    sku_index[UUID(sku_id)] = sku
                except ValueError:
                    continue

    total = 0
    reserve_payload: list[dict] = []
    order_items: list[OrderItem] = []
    for cart_item in cart.items:
        sku = sku_index.get(cart_item.sku_id)
        if sku is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"SKU {cart_item.sku_id} стал недоступен",
            )
        price = int(sku["price"])
        line_total = price * cart_item.quantity
        total += line_total

        order_items.append(
            OrderItem(
                sku_id=cart_item.sku_id,
                product_id=UUID(sku["product_id"]),
                product_title=sku.get("product_title") or sku.get("name", ""),
                seller_id=UUID(sku["seller_id"]),
                sku_name=sku.get("name", ""),
                image_url=sku.get("image_url"),
                unit_price=price,
                line_total=line_total,
                quantity=cart_item.quantity,
            )
        )
        reserve_payload.append(
            {"sku_id": str(cart_item.sku_id), "quantity": cart_item.quantity}
        )

    reserve_result = await b2b.reserve(idempotency_key, reserve_payload)
    if not reserve_result.get("reserved", False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Часть товаров недоступна",
                "failed_items": reserve_result.get("failed_items", []),
            },
        )

    order = Order(
        idempotency_key=idempotency_key,
        buyer_id=buyer_id,
        address_id=address.id,
        status=OrderStatus.PAID,
        total_price=total,
        comment=comment,
        reserved_at=datetime.now(timezone.utc),
    )
    db.add(order)
    await db.flush()
    for item in order_items:
        item.order_id = order.id
        db.add(item)

    for item in list(cart.items):
        await db.delete(item)

    try:
        await db.commit()
    except Exception:
        try:
            await b2b.unreserve(order.id, reserve_payload)
        except Exception:
            pass
        raise

    result = await db.execute(
        select(Order)
        .where(Order.id == order.id)
        .options(selectinload(Order.items), selectinload(Order.address))
    )
    return result.scalar_one()


async def cancel_order(db: AsyncSession, buyer_id: UUID, order_id: UUID, b2b: B2BClient) -> Order:
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items), selectinload(Order.address))
    )
    order = result.scalar_one_or_none()
    if order is None or order.buyer_id != buyer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден"
        )

    if order.status == OrderStatus.CANCELLED:
        return order
    if order.status == OrderStatus.CANCEL_PENDING:
        return order
    if order.status in (OrderStatus.ASSEMBLING, OrderStatus.DELIVERING, OrderStatus.DELIVERED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="CANCEL_NOT_ALLOWED",
        )

    unreserve_payload = [
        {"sku_id": str(item.sku_id), "quantity": item.quantity}
        for item in order.items
    ]

    try:
        await b2b.unreserve(order.id, unreserve_payload)
        order.status = OrderStatus.CANCELLED
    except B2BClientError as exc:
        if exc.status_code in (
            status.HTTP_502_BAD_GATEWAY,
            status.HTTP_504_GATEWAY_TIMEOUT,
        ):
            order.status = OrderStatus.CANCEL_PENDING
        else:
            raise
    await db.commit()

    return order


async def list_orders(db: AsyncSession, buyer_id: UUID, page: int, size: int):
    total_q = select(func.count(Order.id)).where(Order.buyer_id == buyer_id)
    total = (await db.execute(total_q)).scalar_one()

    items_q = (
        select(Order)
        .where(Order.buyer_id == buyer_id)
        .order_by(Order.created_at.desc())
        .limit(size)
        .offset((page - 1) * size)
    )
    result = await db.execute(items_q)
    return total, list(result.scalars().all())


async def get_order(db: AsyncSession, buyer_id: UUID, order_id: UUID) -> Order:
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id, Order.buyer_id == buyer_id)
        .options(selectinload(Order.items), selectinload(Order.address))
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден"
        )
    return order
