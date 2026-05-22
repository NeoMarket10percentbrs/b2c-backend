from datetime import datetime, timezone, timedelta
import hashlib
import json
from uuid import UUID, uuid4
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from .b2b import B2BClient, B2BClientError
from models.address import Address
from models.order import Order, OrderStatus
from models.payment_method import PaymentMethod
from models.order_item import OrderItem
from services.cart_service import get_or_create_cart, validate_cart
from schemas.order import OrderCreateRequest


async def create_order(
    db: AsyncSession, buyer_id: UUID,
    idempotency_key: UUID, payload: OrderCreateRequest,
    b2b: B2BClient
) -> Order:
    request_hash = _hash_idempotency_payload(payload)
    existing = await db.execute(
        select(Order)
        .where(Order.idempotency_key == idempotency_key)
        .order_by(Order.created_at.desc())
        .options(
            selectinload(Order.items),
            selectinload(Order.address),
            selectinload(Order.payment_method)   # ← добавить
        )
    )
    existing_order = existing.scalars().first()
    if existing_order:
        ttl_deadline = datetime.now(timezone.utc) - timedelta(hours=1)
        if existing_order.created_at >= ttl_deadline:
            if existing_order.idempotency_body_hash != request_hash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="IDEMPOTENCY_KEY_CONFLICT",
                )
            return existing_order

    cart = await get_or_create_cart(db, buyer_id, None)
    if not cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Корзина пуста"
        )

    address = await db.get(Address, payload.address_id)
    if address is None or address.buyer_id != buyer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Адрес не найден"
        )

    payment_method = await db.get(PaymentMethod, payload.payment_method_id)
    if payment_method is None or payment_method.buyer_id != buyer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Способ оплаты не найден"
        )

    validation = await validate_cart(cart, b2b)
    if not validation.is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=validation.model_dump(mode="json"),
        )

    product_ids = [item.product_id for item in cart.items]
    products = await b2b.get_products_by_ids(product_ids)
    products_by_id = products
    sku_index: dict[UUID, dict] = {}
    for product in products.values():
        for sku in product.get("skus", []) or []:
            sku_id = sku.get("id")
            if sku_id:
                try:
                    sku_index[UUID(sku_id)] = sku
                except ValueError:
                    continue

    if payload.items_snapshot:
        snapshot_issues = []
        snapshot_by_sku = {item.sku_id: item for item in payload.items_snapshot}
        cart_by_sku = {item.sku_id: item for item in cart.items}
        for sku_id, snap in snapshot_by_sku.items():
            cart_item = cart_by_sku.get(sku_id)
            sku = sku_index.get(sku_id)
            if cart_item is None or sku is None:
                snapshot_issues.append(
                    {
                        "sku_id": str(sku_id),
                        "type": "PRODUCT_DELETED",
                        "message": "Позиция отсутствует в корзине",
                    }
                )
                continue
            if cart_item.quantity != snap.quantity:
                snapshot_issues.append(
                    {
                        "sku_id": str(sku_id),
                        "type": "QUANTITY_REDUCED",
                        "message": "Количество изменилось",
                        "old_value": snap.quantity,
                        "new_value": cart_item.quantity,
                    }
                )
            current_price = int(sku.get("price") or 0)
            if current_price != snap.unit_price:
                snapshot_issues.append(
                    {
                        "sku_id": str(sku_id),
                        "type": "PRICE_CHANGED",
                        "message": "Цена изменилась",
                        "old_value": snap.unit_price,
                        "new_value": current_price,
                    }
                )
        if snapshot_issues:
            validation = await validate_cart(cart, b2b)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    **validation.model_dump(mode="json"),
                    "issues": snapshot_issues,
                },
            )

    subtotal = 0
    reserve_payload: list[dict] = []
    order_items: list[OrderItem] = []
    for cart_item in cart.items:
        product = products_by_id.get(cart_item.product_id)
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Продукт {cart_item.product_id} не найден"
            )
        sku = sku_index.get(cart_item.sku_id)
        if sku is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"SKU {cart_item.sku_id} стал недоступен",
            )
        price = int(sku["price"])
        line_total = price * cart_item.quantity
        subtotal += line_total

        order_items.append(
            OrderItem(
                sku_id=cart_item.sku_id,
                product_id=UUID(sku["product_id"]),
                name=sku.get("product_title") or sku.get("name", ""),
                seller_id=UUID(product["seller_id"]),
                sku_code=sku.get("sku_code"),
                image_url=sku.get("image_url"),
                unit_price=price,
                line_total=line_total,
                quantity=cart_item.quantity
            )
        )
        reserve_payload.append(
            {"sku_id": str(cart_item.sku_id), "quantity": cart_item.quantity}
        )

    # Генерируем order_id заранее
    order_id = uuid4()
    reserve_result = await b2b.reserve(idempotency_key, order_id, reserve_payload)
    if not reserve_result.get("reserved", False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Часть товаров недоступна",
                "failed_items": reserve_result.get("failed_items", []),
            },
        )

    delivery_cost = 0
    order = Order(
        id=order_id,
        idempotency_key=idempotency_key,
        idempotency_body_hash=request_hash,
        buyer_id=buyer_id,
        address_id=address.id,
        payment_method_id=payment_method.id,
        status=OrderStatus.PAID,
        subtotal=subtotal,
        delivery_cost=delivery_cost,
        total=subtotal + delivery_cost,
        comment=payload.comment,
        reserved_at=datetime.now(timezone.utc),
        paid_at=datetime.now(timezone.utc)
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
        .options(
            selectinload(Order.items),
            selectinload(Order.address),
            selectinload(Order.payment_method)
        )
    )
    return result.scalar_one()


async def cancel_order(db: AsyncSession, buyer_id: UUID, order_id: UUID, payload, b2b: B2BClient) -> Order:
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.items),
            selectinload(Order.address),
            selectinload(Order.payment_method)
        )
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
        order.cancel_reason = payload.reason if payload else None
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


async def list_orders(db: AsyncSession, buyer_id: UUID, limit: int, offset: int, status_filter: str | None):
    total_q = select(func.count(Order.id)).where(Order.buyer_id == buyer_id)
    status_value = None
    if status_filter:
        try:
            status_value = OrderStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="INVALID_STATUS",
            )
        total_q = total_q.where(Order.status == status_value)
    total = (await db.execute(total_q)).scalar_one()

    items_q = (
        select(Order)
        .where(Order.buyer_id == buyer_id)
        .order_by(Order.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status_value:
        items_q = items_q.where(Order.status == status_value)
    result = await db.execute(items_q)
    return total, list(result.scalars().all())


def _hash_idempotency_payload(payload: OrderCreateRequest) -> str:
    payload_dict = payload.model_dump(mode="json")
    encoded = json.dumps(payload_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


async def get_order(db: AsyncSession, buyer_id: UUID, order_id: UUID) -> Order:
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id, Order.buyer_id == buyer_id)
        .options(
            selectinload(Order.items),
            selectinload(Order.address),
            selectinload(Order.payment_method),
        )
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден"
        )
    return order