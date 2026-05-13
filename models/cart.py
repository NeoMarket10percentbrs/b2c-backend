import uuid
from typing import TYPE_CHECKING
from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base, TimestampMixin

if TYPE_CHECKING:
	from models.buyer import Buyer
	from models.cart_item import CartItem


class Cart(Base, TimestampMixin):
	__tablename__ = "carts"
	__table_args__ = (
		CheckConstraint(
			"buyer_id IS NOT NULL OR session_id IS NOT NULL",
			name="cart_identity_present",
		),
	)

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
	)
	buyer_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("buyers.id", ondelete="CASCADE"),
		nullable=True
	)
	session_id: Mapped[str | None] = mapped_column(
		String(100), nullable=True, index=True
	)

	# Relationships
	buyer: Mapped["Buyer"] = relationship(back_populates="cart")
	items: Mapped[list["CartItem"]] = relationship(
		back_populates="cart", cascade="all, delete-orphan"
	)
