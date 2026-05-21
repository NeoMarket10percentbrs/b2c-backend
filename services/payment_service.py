from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.payment_method import PaymentMethod
from schemas.payment_method import PaymentMethodCreateRequest
from helpers.help import _unset_default_payment_methods, _get_method_or_404


async def list_payment_methods(db: AsyncSession, buyer_id: UUID) -> list[PaymentMethod]:
    result = await db.execute(
        select(PaymentMethod)
        .where(PaymentMethod.buyer_id == buyer_id)
        .order_by(PaymentMethod.is_default.desc(), PaymentMethod.created_at.desc())
    )
    return list(result.scalars().all())


async def create_payment_method(db: AsyncSession, buyer_id: UUID, data: PaymentMethodCreateRequest) -> PaymentMethod:
    has_any = (
        await db.execute(
            select(PaymentMethod.id)
            .where(PaymentMethod.buyer_id == buyer_id)
            .limit(1)
        )
    ).first()
    
    is_default = data.is_default or not has_any

    if is_default:
        await _unset_default_payment_methods(db, buyer_id, model=PaymentMethod)

    method = PaymentMethod(
        buyer_id=buyer_id,
        type=data.type,
        card_last4=data.card_last4,
        card_brand=data.card_brand,
        is_default=is_default,
    )
    db.add(method)
    await db.commit()
    await db.refresh(method)
    return method


async def delete_payment_method(db: AsyncSession, buyer_id: UUID, method_id: UUID) -> None:
    method = await _get_method_or_404(db, method_id, buyer_id)
    await db.delete(method)
    await db.commit()