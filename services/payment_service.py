from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.payment_method import PaymentMethod
from schemas.payment_method import PaymentMethodCreate, PaymentMethodUpdate
from helpers.help import _unset_other_defaults, _get_method_or_404


async def list_payment_methods(db: AsyncSession, buyer_id: UUID) -> list[PaymentMethod]:
    result = await db.execute(
        select(PaymentMethod)
        .where(PaymentMethod.buyer_id == buyer_id)
        .order_by(PaymentMethod.is_default.desc(), PaymentMethod.created_at.desc())
    )
    return list(result.scalars().all())


async def create_payment_method(
    db: AsyncSession, buyer_id: UUID, data: PaymentMethodCreate
) -> PaymentMethod:
    has_any = (
        await db.execute(
            select(PaymentMethod.id)
            .where(PaymentMethod.buyer_id == buyer_id)
            .limit(1)
        )
    ).first()
    
    is_default = data.is_default or not has_any

    if is_default:
        from helpers.help import _unset_other_defaults
        await _unset_other_defaults(db, buyer_id, model=PaymentMethod)

    method = PaymentMethod(
        buyer_id=buyer_id,
        cardholder_name=data.cardholder_name,
        last4=data.card_number[-4:],
        exp_month=data.exp_month,
        exp_year=data.exp_year,
        is_default=is_default,
    )
    db.add(method)
    await db.commit()
    await db.refresh(method)
    return method


async def update_payment_method(
    db: AsyncSession, buyer_id: UUID,
    method_id: UUID, data: PaymentMethodUpdate
) -> PaymentMethod:
    method = await _get_method_or_404(db, method_id, buyer_id)
    update_data = data.model_dump(exclude_unset=True)
    if update_data.get("is_default") is True:
        from helpers.help import _unset_other_defaults
        await _unset_other_defaults(db, buyer_id, except_id=method.id, model=PaymentMethod)

    for key, value in update_data.items():
        setattr(method, key, value)
        
    await db.commit()
    await db.refresh(method)
    return method


async def delete_payment_method(db: AsyncSession, buyer_id: UUID, method_id: UUID) -> None:
    method = await _get_method_or_404(db, method_id, buyer_id)
    await db.delete(method)
    await db.commit()