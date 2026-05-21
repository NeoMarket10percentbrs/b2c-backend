from datetime import datetime
import uuid
import enum
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base, TimestampMixin

if TYPE_CHECKING:
	from models.buyer import Buyer
	from models.address import Address
	from models.order_item import OrderItem
	from models.payment_method import PaymentMethod


class OrderStatus(str, enum.Enum):
	CREATED = "CREATED"
	PAID = "PAID"
	ASSEMBLING = "ASSEMBLING"
	DELIVERING = "DELIVERING"
	DELIVERED = "DELIVERED"
	CANCELLED = "CANCELLED"
	CANCEL_PENDING = "CANCEL_PENDING"


class Order(Base, TimestampMixin):
	__tablename__ = "orders"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
	)
	idempotency_key: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), nullable=False, index=True
	)
	idempotency_body_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
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
	payment_method_id: Mapped[uuid.UUID | None] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("payment_methods.id", ondelete="SET NULL"),
		nullable=True
	)
	status: Mapped[OrderStatus] = mapped_column(
		SAEnum(OrderStatus),
		nullable=False, 
		default=OrderStatus.CREATED, index=True
	)
	number: Mapped[str | None] = mapped_column(Text, nullable=True)
	subtotal: Mapped[int] = mapped_column(BigInteger, nullable=False)
	delivery_cost: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
	total: Mapped[int] = mapped_column(BigInteger, nullable=False)
	comment: Mapped[str | None] = mapped_column(Text, nullable=True)
	cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
	status_history: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
	reserved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
	paid_at: Mapped[datetime | None] = mapped_column(
		DateTime(timezone=True), nullable=True
	)
	delivered_at: Mapped[datetime | None] = mapped_column(
		DateTime(timezone=True), nullable=True
	)
	# Relationships
	buyer: Mapped["Buyer"] = relationship(back_populates="orders")
	address: Mapped["Address"] = relationship(back_populates="orders")
	payment_method: Mapped["PaymentMethod"] = relationship()
	items: Mapped[list["OrderItem"]] = relationship(
		back_populates="order", cascade="all, delete-orphan"
	)
