from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import UUID, select, func
from starlette import status
from starlette.exceptions import HTTPException
from helpers.help import _get_buyer_or_404
from models import Buyer
from schemas.buyer import BuyerRegisterRequest, BuyerUpdateRequest
from core.security import hash_password


def normalize_email(email: str) -> str:
	return email.strip().lower()


async def create_buyer(db: AsyncSession, data: BuyerRegisterRequest) -> Buyer:
    existing = await db.execute(
        select(Buyer.id).where(func.lower(Buyer.email) == normalize_email(data.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Покупатель с таким email уже существует"
        )

    buyer = Buyer(
        email=normalize_email(str(data.email)),
        password_hash=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        phone=data.phone,
    )
    
    db.add(buyer)
    
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ошибка при создании: данные уже используются (email или телефон)"
        )
    
    return buyer


async def get_buyer_by_id(db: AsyncSession, buyer_id: UUID) -> Buyer:
    return await _get_buyer_or_404(db, buyer_id)


async def get_buyer_by_email(db: AsyncSession, email: str) -> Buyer | None:
	normalized_email = normalize_email(email)
	result = await db.execute(
        select(Buyer).where(func.lower(Buyer.email) == normalized_email)
    )
	buyer = result.scalar_one_or_none()

	return buyer


async def update_buyer(db: AsyncSession, buyer_id: UUID, data: BuyerUpdateRequest) -> Buyer:
    buyer = await _get_buyer_or_404(db, buyer_id)
    
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "password":
            buyer.password_hash = hash_password(value)
        else:
            setattr(buyer, field, value)
            
    await db.commit()
    await db.refresh(buyer)
    return buyer


async def delete_buyer(db: AsyncSession, buyer_id: UUID) -> None:
    buyer = await _get_buyer_or_404(db, buyer_id)
    buyer.is_active = False
    buyer.email = f"deleted_{buyer_id.hex[:8]}@deleted.local"
    buyer.first_name = "Deleted"
    buyer.last_name = "User"
    buyer.phone = None
    await db.commit()
    from services import auth_service
    await auth_service.revoke_all_buyer_tokens(db, buyer_id)
