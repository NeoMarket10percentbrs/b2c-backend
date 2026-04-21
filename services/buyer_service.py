from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from models import Buyer
from schemas.buyer import BuyerCreate, BuyerUpdate
from core.security import hash_password


def normalize_email(email: str) -> str:
	return email.strip().lower()


async def get_buyer_by_id(db: AsyncSession, buyer_id) -> Buyer | None:
	result = await db.execute(select(Buyer).where(Buyer.id == buyer_id))
	return result.scalar_one_or_none()


async def get_buyer_by_email(db: AsyncSession, email: str) -> Buyer | None:
	normalized_email = normalize_email(email)
	result = await db.execute(
		select(Buyer).where(func.lower(Buyer.email) == normalized_email)
	)
	return result.scalar_one_or_none()


async def create_buyer(db: AsyncSession, data: BuyerCreate) -> Buyer:
	buyer = Buyer(
		email=normalize_email(str(data.email)),
		password_hash=hash_password(data.password),
		first_name=data.first_name,
		last_name=data.last_name,
		phone=data.phone,
	)
	db.add(buyer)
	await db.flush()
	return buyer


async def update_buyer(db: AsyncSession, buyer: Buyer, data: BuyerUpdate) -> Buyer:
	for field, value in data.model_dump(exclude_unset=True).items():
		setattr(buyer, field, value)
	await db.commit()
	await db.refresh(buyer)
	return buyer


# TODO: сделать флаг is_deleted для того чтобы не удалять пользователей
async def delete_buyer(db: AsyncSession, buyer: Buyer) -> None:
	await db.delete(buyer)
	await db.commit()
