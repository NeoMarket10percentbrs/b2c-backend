import uuid
import enum
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base, TimestampMixin

if TYPE_CHECKING:
	from models.buyer import Buyer
	from models.address import Address
	from models.order_item import OrderItem


class OrderStatus(str, enum.Enum):
	CREATED = "CREATED"
	CONFIRMED = "CONFIRMED"
	SHIPPED = "SHIPPED"
	DELIVERED = "DELIVERED"
	CANCELLED = "CANCELLED"


class Order(Base, TimestampMixin):
	__tablename__ = "orders"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
	)
	buyer_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("buyers.id", ondelete="RESTRICT"),
		nullable=False, index=True
	)
	address_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("addresses.id", ondelete="RESTRICT"),
		nullable=False
	)
	status: Mapped[OrderStatus] = mapped_column(
		SAEnum(OrderStatus), nullable=False, default=OrderStatus.CREATED, index=True
	)
	total_price: Mapped[int] = mapped_column(BigInteger, nullable=False)
	comment: Mapped[str | None] = mapped_column(Text, nullable=True)

	# Relationships
	buyer: Mapped["Buyer"] = relationship(back_populates="orders")
	address: Mapped["Address"] = relationship(back_populates="orders")
	items: Mapped[list["OrderItem"]] = relationship(
		back_populates="order", cascade="all, delete-orphan"
	)
