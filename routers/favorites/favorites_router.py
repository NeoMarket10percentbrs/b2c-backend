from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.dependencies import get_current_buyer
from models.buyer import Buyer
from schemas.catalog import PaginatedCatalogProducts
from schemas.favorite import SubscribeRequest
from services import favorites_service

favorites_router = APIRouter(prefix="/favorites", tags=["Favorites"])


@favorites_router.get("", response_model=PaginatedCatalogProducts)
async def list_favorites(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db)
):
    return await favorites_service.get_favorites(db, buyer.id, limit, offset)


@favorites_router.put("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_favorite(
    product_id: UUID, buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db)
):
    await favorites_service.add_to_favorites(db, buyer.id, product_id)
    return None


@favorites_router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    product_id: UUID, buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db)
):
    await favorites_service.remove_favorite(db, buyer.id, product_id)


@favorites_router.post("/{product_id}/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def subscribe_to_product(
    product_id: UUID, payload: SubscribeRequest | None,
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db)
):
    await favorites_service.subscribe_to_product(db, buyer.id, product_id, payload)
    return None


@favorites_router.delete("/{product_id}/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe_from_product(
    product_id: UUID, buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db)
):
    await favorites_service.unsubscribe_from_product(db, buyer.id, product_id)
    return None