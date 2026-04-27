from datetime import datetime, timezone
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from .b2b import B2BClient, B2BClientError, B2BConflictError
from models.address import Address
from models.order import Order, OrderStatus
from models.order_item import OrderItem
from services.cart_service import get_or_create_cart, validate_cart


async def create_order(
    db: AsyncSession, buyer_id: UUID,
    address_id: UUID, comment: str | None,
    b2b: B2BClient) -> Order:
    cart = await get_or_create_cart(db, buyer_id)
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

    sku_ids = [item.sku_id for item in cart.items]
    skus = await b2b.get_skus_bulk(sku_ids)

    order = Order(
        buyer_id=buyer_id,
        address_id=address.id,
        status=OrderStatus.CREATED,
        total_price=0,
        comment=comment,
    )
    db.add(order)
    await db.flush()

    total = 0
    reserve_payload: list[dict] = []
    for cart_item in cart.items:
        sku = skus.get(cart_item.sku_id)
        if sku is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"SKU {cart_item.sku_id} стал недоступен",
            )
        price = int(sku["price"])
        line_total = price * cart_item.quantity
        total += line_total

        db.add(
            OrderItem(
                order_id=order.id,
                sku_id=cart_item.sku_id,
                product_id=UUID(sku["product_id"]),
                seller_id=UUID(sku["seller_id"]),
                sku_name=sku.get("name", ""),
                image_url=sku.get("image_url"),
                price=price,
                quantity=cart_item.quantity,
            )
        )
        reserve_payload.append(
            {"sku_id": str(cart_item.sku_id), "quantity": cart_item.quantity}
        )

    order.total_price = total

    try:
        await b2b.reserve_stock(order.id, reserve_payload)
    except B2BConflictError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Не удалось зарезервировать товар: {exc.detail}",
        )
    except B2BClientError:
        await db.rollback()
        raise

    order.reserved_at = datetime.now(timezone.utc)

    for item in list(cart.items):
        await db.delete(item)

    try:
        await db.commit()
    except Exception:
        try:
            await b2b.release_reservation(order.id)
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
    order = await db.get(Order, order_id)
    if order is None or order.buyer_id != buyer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден"
        )

    if order.status in (OrderStatus.SHIPPED, OrderStatus.DELIVERED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Этот заказ уже нельзя отменить",
        )
    if order.status == OrderStatus.CANCELLED:
        return order

    try:
        await b2b.release_reservation(order.id)
    except B2BClientError as exc:
        if exc.status_code != status.HTTP_404_NOT_FOUND:
            raise

    order.status = OrderStatus.CANCELLED
    await db.commit()

    result = await db.execute(
        select(Order)
        .where(Order.id == order.id)
        .options(selectinload(Order.items), selectinload(Order.address))
    )
    return result.scalar_one()


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
