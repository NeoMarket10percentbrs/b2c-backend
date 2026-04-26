import uuid
from typing import TYPE_CHECKING
from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base, TimestampMixin

if TYPE_CHECKING:
	from models.buyer import Buyer
	from models.order import Order


class Address(Base, TimestampMixin):
	__tablename__ = "addresses"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
	)
	buyer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("buyers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
	)
	label: Mapped[str | None] = mapped_column(String(100), nullable=True)
	country: Mapped[str] = mapped_column(String(100), nullable=False)
	city: Mapped[str] = mapped_column(String(100), nullable=False)
	street: Mapped[str] = mapped_column(String(255), nullable=False)
	building: Mapped[str] = mapped_column(String(20), nullable=False)
	apartment: Mapped[str | None] = mapped_column(String(20), nullable=True)
	postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
	is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

	# Relationships
	buyer: Mapped["Buyer"] = relationship(back_populates="addresses")
	orders: Mapped[list["Order"]] = relationship(back_populates="address")
