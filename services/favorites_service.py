from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from models.favorite import Favorite
from models.product_subscription import ProductSubscription
from schemas.favorite import FavoriteListResponse, FavoriteResponse, SubscribeRequest
from services.b2b import get_b2b_client
from helpers.help import _enrich_favorite


async def get_favorites(
    db: AsyncSession, buyer_id: UUID, limit: int, offset: int
) -> FavoriteListResponse:
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
        return FavoriteListResponse(
            items=[], total_count=total_count, limit=limit, offset=offset
        )

    products = await get_b2b_client().get_products_by_ids(
        [f.product_id for f in favorites]
    )

    items = []
    for fav in favorites:
        product = products.get(fav.product_id)
        if product is None:
            continue
        items.append(_enrich_favorite(fav, product))

    return FavoriteListResponse(
        items=items, total_count=total_count, limit=limit, offset=offset
    )


async def add_to_favorites(
    db: AsyncSession, buyer_id: UUID, product_id: UUID
) -> tuple[FavoriteResponse, bool]:
    try:
        product = await get_b2b_client().get_product(product_id)
    except HTTPException as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Товар не найден в каталоге")
        raise

    result = await db.execute(
        select(Favorite).where(
            Favorite.buyer_id == buyer_id,
            Favorite.product_id == product_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return _enrich_favorite(existing, product), False

    fav = Favorite(buyer_id=buyer_id, product_id=product_id)
    db.add(fav)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        result = await db.execute(
            select(Favorite).where(
                Favorite.buyer_id == buyer_id,
                Favorite.product_id == product_id,
            )
        )
        existing = result.scalar_one()
        return _enrich_favorite(existing, product), False

    await db.refresh(fav)
    return _enrich_favorite(fav, product), True


async def remove_favorite(db: AsyncSession, buyer_id: UUID, product_id: UUID) -> None:
    result = await db.execute(
        select(Favorite).where(
            Favorite.buyer_id == buyer_id,
            Favorite.product_id == product_id,
        )
    )
    fav = result.scalar_one_or_none()
    if not fav:
        return

    await db.delete(fav)
    await db.commit()


async def subscribe_to_product(
    db: AsyncSession, user_id: UUID, product_id: UUID, data: SubscribeRequest
) -> ProductSubscription:
    existing = await db.execute(
        select(ProductSubscription).where(
            ProductSubscription.user_id == user_id,
            ProductSubscription.product_id == product_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Подписка уже существует",
        )

    subscription = ProductSubscription(
        user_id=user_id, product_id=product_id, notify_on=data.notify_on
    )
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)
    return subscription