from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from models.favorite import Favorite
from schemas.favorite import FavoriteAdd, FavoriteResponse, FavoriteUpdate
from services.b2b import get_b2b_client
from helpers.help import _enrich_favorite


async def get_favorites(db: AsyncSession, buyer_id: UUID) -> list[FavoriteResponse]:
    result = await db.execute(
        select(Favorite)
        .where(Favorite.buyer_id == buyer_id)
        .order_by(Favorite.created_at.desc())
    )
    favorites = list(result.scalars().all())
    
    if not favorites:
        return []

    products = await get_b2b_client().get_products_bulk(
        [f.product_id for f in favorites]
    )
    
    return [_enrich_favorite(f, products.get(f.product_id)) for f in favorites]


async def add_to_favorites(db: AsyncSession, buyer_id: UUID, data: FavoriteAdd) -> FavoriteResponse:
    try:
        product = await get_b2b_client().get_product(data.product_id)
    except HTTPException as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Товар не найден в каталоге")
        raise

    baseline_price = None
    if data.notify_price_down:
        baseline_price = product.get("min_price") or product.get("price")

    fav = Favorite(
        buyer_id=buyer_id,
        product_id=data.product_id,
        notify_in_stock=data.notify_in_stock,
        notify_price_down=data.notify_price_down,
        baseline_price=baseline_price,
    )
    db.add(fav)
    
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Товар уже находится в вашем списке избранного",
        )
    
    await db.refresh(fav)
    return _enrich_favorite(fav, product)


async def update_favorite(
    db: AsyncSession, buyer_id: UUID,
    favorite_id: UUID, data: FavoriteUpdate
) -> FavoriteResponse:
    fav = await db.get(Favorite, favorite_id)
    if not fav or fav.buyer_id != buyer_id:
        raise HTTPException(status_code=404, detail="Запись в избранном не найдена")

    update_data = data.model_dump(exclude_unset=True)
    
    if update_data.get("notify_price_down") and not fav.notify_price_down:
        try:
            product = await get_b2b_client().get_product(fav.product_id)
            fav.baseline_price = product.get("min_price") or product.get("price")
        except HTTPException:
            pass

    for key, value in update_data.items():
        setattr(fav, key, value)
        
    await db.commit()
    await db.refresh(fav)
    return FavoriteResponse.model_validate(fav)


async def remove_favorite(db: AsyncSession, buyer_id: UUID, favorite_id: UUID) -> None:
    fav = await db.get(Favorite, favorite_id)
    if not fav or fav.buyer_id != buyer_id:
        raise HTTPException(status_code=404, detail="Запись в избранном не найдена")
    
    await db.delete(fav)
    await db.commit()