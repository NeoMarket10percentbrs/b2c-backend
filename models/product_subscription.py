import uuid
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from models.buyer import Buyer


class ProductSubscription(Base, TimestampMixin):
    __tablename__ = "product_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="user_product_subscription"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("buyers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    notify_on: Mapped[list[str]] = mapped_column(ARRAY(String(50)), nullable=False)

    user: Mapped["Buyer"] = relationship()
