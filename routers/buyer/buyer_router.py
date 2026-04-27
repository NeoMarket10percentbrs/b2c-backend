from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.dependencies import get_current_buyer
from models import Buyer
from schemas.buyer import BuyerResponse, BuyerUpdate
from services import buyer_service

buyer_router = APIRouter(prefix="/me", tags=["Buyer"])


@buyer_router.get(
    "", response_model=BuyerResponse,
    summary="Получить профиль",
    description="Возвращает полную информацию о покупателе."
)
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    current_buyer: Buyer = Depends(get_current_buyer),
):
    return await buyer_service.get_buyer_by_id(db, current_buyer.id)


@buyer_router.patch(
    "", response_model=BuyerResponse,
    summary="Обновить профиль"
)
async def update_my_profile(
    payload: BuyerUpdate,
    db: AsyncSession = Depends(get_db),
    current_buyer: Buyer = Depends(get_current_buyer),
):
    return await buyer_service.update_buyer(db, current_buyer.id, payload)


@buyer_router.delete(
    "", status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить аккаунт"
)
async def delete_my_account(
    db: AsyncSession = Depends(get_db),
    current_buyer: Buyer = Depends(get_current_buyer),
):
    await buyer_service.delete_buyer(db, current_buyer.id)