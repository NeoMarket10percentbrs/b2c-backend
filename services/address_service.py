from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.address import Address
from schemas.address import AddressCreateRequest, AddressUpdateRequest
from helpers.help import _get_address_or_404, _unset_default_addresses, _get_address_or_404


async def get_address(db: AsyncSession, address_id: UUID, buyer_id: UUID) -> Address:
    return await _get_address_or_404(db, address_id, buyer_id)


async def list_addresses(db: AsyncSession, buyer_id: UUID) -> list[Address]:
    result = await db.execute(
        select(Address)
        .where(Address.buyer_id == buyer_id)
        .order_by(Address.is_default.desc(), Address.created_at.desc())
    )
    return list(result.scalars().all())


async def create_address(db: AsyncSession, buyer_id: UUID, data: AddressCreateRequest) -> Address:
    has_any = (
        await db.execute(
            select(Address.id).where
            (Address.buyer_id == buyer_id).limit(1)
        )
    ).first()
    
    is_default = data.is_default or not has_any
    if is_default:
        await _unset_default_addresses(db, buyer_id)

    address = Address(
        buyer_id=buyer_id,
        **data.model_dump(exclude={"is_default"}),
        is_default=is_default,
    )
    db.add(address)
    await db.commit()
    await db.refresh(address)
    return address

async def update_address(db: AsyncSession, address_id: UUID, buyer_id: UUID, data: AddressUpdateRequest) -> Address:
    address = await _get_address_or_404(db, address_id, buyer_id)
    
    update_data = data.model_dump(exclude_unset=True)
    if update_data.get("is_default") is True:
        await _unset_default_addresses(db, buyer_id, except_id=address.id)

    for key, value in update_data.items():
        setattr(address, key, value)
    
    await db.commit()
    await db.refresh(address)
    return address

async def delete_address(db: AsyncSession, address_id: UUID, buyer_id: UUID) -> None:
    address = await _get_address_or_404(db, address_id, buyer_id)
    try:
        await db.delete(address)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Адрес используется в существующих заказах и не может быть удалён",
        ) from exc