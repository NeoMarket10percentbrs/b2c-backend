import uuid
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base, TimestampMixin


if TYPE_CHECKING:
    from models.buyer import Buyer


class PaymentMethod(Base, TimestampMixin):
    __tablename__ = "payment_methods"
    __table_args__ = (
        CheckConstraint("char_length(last4) = 4", name="last4_length"),
        CheckConstraint("exp_month BETWEEN 1 AND 12", name="exp_month_range"),
        CheckConstraint("exp_year BETWEEN 2000 AND 2100", name="exp_year_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    buyer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("buyers.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    cardholder_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    exp_month: Mapped[int] = mapped_column(Integer, nullable=False)
    exp_year: Mapped[int] = mapped_column(Integer, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    buyer: Mapped["Buyer"] = relationship(back_populates="payment_methods")
