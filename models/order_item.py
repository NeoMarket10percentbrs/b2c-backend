import uuid
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, Integer, ForeignKey, String, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base

if TYPE_CHECKING:
	from models.order import Order


class OrderItem(Base):
	__tablename__ = "order_items"
	__table_args__ = (
		CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
		CheckConstraint("price >= 0", name="price_non_negative")
	)

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
	)
	order_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("orders.id", ondelete="CASCADE"),
		nullable=False, index=True
	)
	product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
	seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
	sku_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
	sku_name: Mapped[str] = mapped_column(String(255), nullable=False)
	image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
	price: Mapped[int] = mapped_column(BigInteger, nullable=False)
	quantity: Mapped[int] = mapped_column(Integer, nullable=False)

	# Relationships
	order: Mapped["Order"] = relationship(back_populates="items")
