import uuid
from typing import TYPE_CHECKING
from sqlalchemy import Integer, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base, TimestampMixin

if TYPE_CHECKING:
	from models.cart import Cart


class CartItem(Base, TimestampMixin):
	__tablename__ = "cart_items"
	__table_args__ = (
		CheckConstraint("quantity > 0", name="ck_cart_items_quantity_positive"),
		UniqueConstraint("cart_id", "sku_id", name="uq_cart_items_cart_sku"),
	)

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
	)
	cart_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("carts.id", ondelete="CASCADE"),
		nullable=False, index=True
	)
	sku_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
	quantity: Mapped[int] = mapped_column(Integer, nullable=False)

	# Relationships
	cart: Mapped["Cart"] = relationship(back_populates="items")
