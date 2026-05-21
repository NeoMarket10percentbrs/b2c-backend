from uuid import UUID
from alembic.util import status
from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from models import Address, Buyer, Favorite, PaymentMethod
from uuid import uuid4
from schemas.catalog import CatalogProductCard


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


def _catalog_card_from_b2b(product: dict) -> CatalogProductCard:
    images = product.get("images") or []
    if not images and product.get("image_url"):
        images = [
            {
                "id": str(uuid4()),
                "url": product.get("image_url"),
                "ordering": 0,
                "is_main": True,
            }
        ]

    payload = {
        "id": product.get("id"),
        "name": product.get("name") or product.get("title") or "",
        "slug": product.get("slug"),
        "category": product.get("category"),
        "min_price": product.get("min_price") or product.get("price") or 0,
        "old_price": product.get("old_price") or product.get("price_old"),
        "has_stock": bool(product.get("has_stock") or product.get("in_stock") or product.get("stock_quantity", 0)),
        "rating": product.get("rating"),
        "reviews_count": product.get("reviews_count") or 0,
        "images": images,
        "seller": product.get("seller"),
    }
    return CatalogProductCard.model_validate(payload)


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
