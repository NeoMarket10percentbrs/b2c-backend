from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.dependencies import get_current_buyer
from models.buyer import Buyer
from schemas.favorite import FavoriteAdd, FavoriteResponse, FavoriteUpdate
from services import favorites_service

favorites_router = APIRouter(prefix="/favorites", tags=["favorites"])


@favorites_router.get("", response_model=list[FavoriteResponse])
async def list_favorites(
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    return await favorites_service.get_favorites(db, buyer.id)


@favorites_router.post("", response_model=FavoriteResponse, status_code=status.HTTP_201_CREATED)
async def add_favorite(
    payload: FavoriteAdd,
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    return await favorites_service.add_to_favorites(db, buyer.id, payload)


@favorites_router.patch("/{favorite_id}", response_model=FavoriteResponse)
async def update_favorite(
    favorite_id: UUID,
    payload: FavoriteUpdate,
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    return await favorites_service.update_favorite(db, buyer.id, favorite_id, payload)


@favorites_router.delete("/{favorite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    favorite_id: UUID,
    buyer: Buyer = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    await favorites_service.remove_favorite(db, buyer.id, favorite_id)