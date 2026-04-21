import uuid
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base, TimestampMixin

if TYPE_CHECKING:
	from models.buyer import Buyer
	from models.cart_item import CartItem


class Cart(Base, TimestampMixin):
	__tablename__ = "carts"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
	)
	buyer_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("buyers.id", ondelete="CASCADE"),
		nullable=False, unique=True
	)

	# Relationships
	buyer: Mapped["Buyer"] = relationship(back_populates="cart")
	items: Mapped[list["CartItem"]] = relationship(
		back_populates="cart", cascade="all, delete-orphan"
	)
