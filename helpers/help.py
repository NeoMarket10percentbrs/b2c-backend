from uuid import UUID
from alembic.util import status
from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from models import Address, Buyer, Favorite, PaymentMethod
from schemas.favorite import FavoriteResponse


async def _unset_default_addresses(db: AsyncSession, buyer_id: UUID, except_id: UUID | None = None):
    stmt = (
        update(Address)
        .where(Address.buyer_id == buyer_id, Address.is_default.is_(True))
        .values(is_default=False)
    )
    if except_id is not None:
        stmt = stmt.where(Address.id != except_id)
    await db.execute(stmt)

    
async def _get_address_or_404(db: AsyncSession, address_id: UUID, buyer_id: UUID) -> Address:
    address = await db.get(Address, address_id)
    if not address or address.buyer_id != buyer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Адрес не найден"
        )
    return address

    
async def _get_buyer_or_404(db: AsyncSession, buyer_id: UUID) -> Buyer:
    buyer = await db.get(Buyer, buyer_id)
    if not buyer or not buyer.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    return buyer


def _enrich_favorite(fav: Favorite, product: dict | None) -> FavoriteResponse:
    base = FavoriteResponse.model_validate(fav)
    if product:
        base.product_name = product.get("name")
        base.current_price = product.get("min_price") or product.get("price")
        base.image_url = product.get("image_url")
        base.in_stock = bool(product.get("in_stock", False))
    return base


async def _get_method_or_404(db: AsyncSession, method_id: UUID, buyer_id: UUID) -> PaymentMethod:
    method = await db.get(PaymentMethod, method_id)
    if not method or method.buyer_id != buyer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Способ оплаты не найден"
        )
    return method


async def _unset_default_payment_methods(db: AsyncSession, buyer_id: UUID, except_id: UUID | None = None) -> None:
    stmt = (
        update(PaymentMethod)
        .where(
            PaymentMethod.buyer_id == buyer_id,
            PaymentMethod.is_default.is_(True),
        )
        .values(is_default=False)
    )
    if except_id is not None:
        stmt = stmt.where(PaymentMethod.id != except_id)
    await db.execute(stmt)
