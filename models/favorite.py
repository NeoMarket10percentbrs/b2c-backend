import enum
import uuid
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base, TimestampMixin


if TYPE_CHECKING:
    from models.buyer import Buyer


class SubscriptionEvent(str, enum.Enum):
    IN_STOCK = "IN_STOCK"
    PRICE_DOWN = "PRICE_DOWN"


class Favorite(Base, TimestampMixin):
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("buyer_id", "product_id", name="buyer_product"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    buyer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("buyers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    notify_in_stock: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    notify_price_down: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    baseline_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    buyer: Mapped["Buyer"] = relationship(back_populates="favorites")
