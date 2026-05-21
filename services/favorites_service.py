from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from models.favorite import Favorite
from models.product_subscription import ProductSubscription
from schemas.catalog import PaginatedCatalogProducts, CatalogProductCard
from schemas.favorite import SubscribeRequest
from services.b2b import get_b2b_client
from helpers.help import _catalog_card_from_b2b


async def get_favorites(db: AsyncSession, buyer_id: UUID, limit: int, offset: int) -> PaginatedCatalogProducts:
    total_query = select(func.count(Favorite.id)).where(Favorite.buyer_id == buyer_id)
    total_count = (await db.execute(total_query)).scalar_one()

    result = await db.execute(
        select(Favorite)
        .where(Favorite.buyer_id == buyer_id)
        .order_by(Favorite.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    favorites = list(result.scalars().all())

    if not favorites:
        return PaginatedCatalogProducts(
            items=[], total_count=total_count, limit=limit, offset=offset
        )
    try:
        products = await get_b2b_client().get_products_by_ids(
            [f.product_id for f in favorites]
        )
    except HTTPException:
        products = {}

    items: list[CatalogProductCard] = []
    for fav in favorites:
        product = products.get(fav.product_id)
        if product is None:
            continue
        items.append(_catalog_card_from_b2b(product))

    return PaginatedCatalogProducts(
        items=items, total_count=total_count, limit=limit, offset=offset
    )


async def add_to_favorites(db: AsyncSession, buyer_id: UUID, product_id: UUID) -> None:
    try:
        product = await get_b2b_client().get_product(product_id)
    except HTTPException as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Товар не найден в каталоге")
        raise

    result = await db.execute(
        select(Favorite).where(
            Favorite.buyer_id == buyer_id,
            Favorite.product_id == product_id
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return None

    fav = Favorite(buyer_id=buyer_id, product_id=product_id)
    db.add(fav)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        result = await db.execute(
            select(Favorite).where(
                Favorite.buyer_id == buyer_id,
                Favorite.product_id == product_id
            )
        )
        return None

    await db.refresh(fav)
    return None


async def remove_favorite(db: AsyncSession, buyer_id: UUID, product_id: UUID) -> None:
    result = await db.execute(
        select(Favorite).where(
            Favorite.buyer_id == buyer_id,
            Favorite.product_id == product_id
        )
    )
    fav = result.scalar_one_or_none()
    if not fav:
        return

    await db.delete(fav)
    await db.commit()


async def subscribe_to_product(db: AsyncSession, user_id: UUID, product_id: UUID, data: SubscribeRequest | None) -> ProductSubscription:
    try:
        await get_b2b_client().get_product(product_id)
    except HTTPException as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Товар не найден в каталоге")
        raise

    if data is not None:
        if data.events is not None and len(data.events) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Список событий не может быть пустым"
            )
        events = data.events if data.events else ["BACK_IN_STOCK", "PRICE_DROP"]
    else:
        events = ["BACK_IN_STOCK", "PRICE_DROP"]

    existing = await db.execute(
        select(ProductSubscription).where(
            ProductSubscription.user_id == user_id,
            ProductSubscription.product_id == product_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Подписка уже существует",
        )

    subscription = ProductSubscription(
        user_id=user_id, product_id=product_id, notify_on=events
    )
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)
    return subscription


async def unsubscribe_from_product(db: AsyncSession, user_id: UUID, product_id: UUID) -> None:
    result = await db.execute(
        select(ProductSubscription).where(
            ProductSubscription.user_id == user_id,
            ProductSubscription.product_id == product_id
        )
    )
    subscription = result.scalar_one_or_none()
    if subscription is None:
        return
    await db.delete(subscription)
    await db.commit()